/**
 * Certificate Transparency leaf parsing.
 *
 * We need one thing from a CT entry: the DNS names on the certificate. Getting
 * there means walking two binary formats.
 *
 * 1. RFC 6962 `MerkleTreeLeaf`, which is what `get-entries` returns as
 *    `leaf_input`:
 *
 *      version              1 byte
 *      leaf_type            1 byte
 *      TimestampedEntry:
 *        timestamp          8 bytes  (uint64, ms since epoch)
 *        entry_type         2 bytes  (0 = x509_entry, 1 = precert_entry)
 *        -- if x509_entry:
 *          length           3 bytes, then that many bytes of DER Certificate
 *        -- if precert_entry:
 *          issuer_key_hash 32 bytes
 *          length           3 bytes, then that many bytes of DER TBSCertificate
 *        extensions         2-byte length + bytes
 *
 * 2. The DER inside it. Note the asymmetry: an x509 entry gives a full
 *    Certificate, a precert entry gives a bare *TBSCertificate*. Most X.509
 *    libraries refuse to parse a bare TBS, which is why this file walks the DER
 *    itself looking for the subjectAltName extension — that extension lives
 *    inside the TBS, so the same code handles both shapes.
 *
 * Verified against live entries from `ct.googleapis.com/logs/us1/argon2026h2`:
 * both entry types parse, wildcards and multi-SAN certs included.
 */

export type CtEntryType = 'x509' | 'precert';

export interface ParsedLeaf {
  entryType: CtEntryType;
  /** Certificate timestamp (SCT time), ms since epoch. */
  timestamp: number;
  /** DER bytes: a full Certificate for x509, a TBSCertificate for precert. */
  certBytes: Buffer;
}

export class CtParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CtParseError';
  }
}

/** Parse a base64 `leaf_input` from `get-entries`. */
export function parseMerkleTreeLeaf(leafInputB64: string): ParsedLeaf {
  const b = Buffer.from(leafInputB64, 'base64');
  // 1 version + 1 leaf_type + 8 timestamp + 2 entry_type = 12 bytes minimum.
  if (b.length < 12) throw new CtParseError(`leaf too short: ${b.length} bytes`);

  const timestamp = Number(b.readBigUInt64BE(2));
  const entryTypeCode = b.readUInt16BE(10);

  let offset = 12;
  let entryType: CtEntryType;

  if (entryTypeCode === 0) {
    entryType = 'x509';
  } else if (entryTypeCode === 1) {
    entryType = 'precert';
    offset += 32; // skip issuer_key_hash
  } else {
    throw new CtParseError(`unknown entry_type ${entryTypeCode}`);
  }

  if (offset + 3 > b.length) throw new CtParseError('truncated before certificate length');
  const certLen = (b[offset]! << 16) | (b[offset + 1]! << 8) | b[offset + 2]!;
  offset += 3;

  if (offset + certLen > b.length) {
    throw new CtParseError(`certificate length ${certLen} exceeds leaf (${b.length - offset} left)`);
  }

  return { entryType, timestamp, certBytes: b.subarray(offset, offset + certLen) };
}

// --- Minimal DER walking ---------------------------------------------------

interface Tlv {
  tag: number;
  contentStart: number;
  end: number;
}

/**
 * Read one DER tag-length-value header at `offset`.
 * Handles short form and multi-byte long form lengths.
 */
function readTlv(buf: Buffer, offset: number): Tlv | null {
  if (offset + 2 > buf.length) return null;
  const tag = buf[offset]!;
  let p = offset + 1;
  let len = buf[p]!;
  p += 1;

  if (len & 0x80) {
    const numBytes = len & 0x7f;
    // 0x80 is indefinite length, illegal in DER; >4 length bytes is absurd here.
    if (numBytes === 0 || numBytes > 4 || p + numBytes > buf.length) return null;
    len = 0;
    for (let i = 0; i < numBytes; i++) len = (len << 8) | buf[p + i]!;
    p += numBytes;
  }

  const end = p + len;
  if (end > buf.length || len < 0) return null;
  return { tag, contentStart: p, end };
}

/** DER encoding of OID 2.5.29.17 (subjectAltName): tag 06, length 03, 55 1d 11. */
const SAN_OID = Buffer.from([0x06, 0x03, 0x55, 0x1d, 0x11]);

/** GeneralName CHOICE tag for dNSName: context-specific, primitive, index 2. */
const TAG_DNS_NAME = 0x82;

/**
 * Extract dNSName entries from a certificate's subjectAltName extension.
 *
 * Rather than fully decoding the certificate, this scans for the SAN extension
 * OID and decodes forward from it:
 *
 *   Extension ::= SEQUENCE { extnID OID, critical BOOLEAN DEFAULT FALSE,
 *                            extnValue OCTET STRING }
 *
 * so after the OID we may see an optional BOOLEAN, then the OCTET STRING whose
 * content is `GeneralNames ::= SEQUENCE OF GeneralName`.
 *
 * A false-positive OID match inside some other field is possible in principle;
 * the structural checks below (BOOLEAN?, OCTET STRING, SEQUENCE) reject it and
 * the scan continues to the next occurrence.
 */
export function extractDnsNames(certDer: Buffer): string[] {
  let searchFrom = 0;

  while (searchFrom < certDer.length) {
    const oidIndex = certDer.indexOf(SAN_OID, searchFrom);
    if (oidIndex < 0) return [];
    searchFrom = oidIndex + SAN_OID.length;

    let p = searchFrom;

    // Optional `critical` BOOLEAN.
    if (certDer[p] === 0x01) {
      const boolTlv = readTlv(certDer, p);
      if (!boolTlv) continue;
      p = boolTlv.end;
    }

    // extnValue must be an OCTET STRING.
    if (certDer[p] !== 0x04) continue;
    const octet = readTlv(certDer, p);
    if (!octet) continue;

    // Its content is a SEQUENCE of GeneralName.
    const seq = readTlv(certDer, octet.contentStart);
    if (!seq || seq.tag !== 0x30 || seq.end > octet.end) continue;

    const names: string[] = [];
    let q = seq.contentStart;
    while (q < seq.end) {
      const item = readTlv(certDer, q);
      if (!item) break;
      if (item.tag === TAG_DNS_NAME) {
        // dNSName is IA5String: ASCII only. Anything else is malformed.
        const value = certDer.toString('latin1', item.contentStart, item.end);
        if (value) names.push(value);
      }
      q = item.end;
    }

    // An empty SAN sequence is legal but useless; keep scanning in case the OID
    // matched spurious bytes earlier in the certificate.
    if (names.length > 0) return names;
  }

  return [];
}

/**
 * Full path: base64 `leaf_input` → DNS names.
 * Returns an empty array rather than throwing when a single entry is malformed —
 * one bad entry must never stall a log's poll loop.
 */
export function dnsNamesFromLeafInput(leafInputB64: string): {
  names: string[];
  entryType: CtEntryType | null;
  timestamp: number | null;
  error?: string;
} {
  try {
    const leaf = parseMerkleTreeLeaf(leafInputB64);
    return {
      names: extractDnsNames(leaf.certBytes),
      entryType: leaf.entryType,
      timestamp: leaf.timestamp,
    };
  } catch (err) {
    return {
      names: [],
      entryType: null,
      timestamp: null,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
