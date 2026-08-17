import { lookupMxRule, type MxProviderKind } from './data/mx-providers';

/**
 * MX classification.
 *
 * The rule the whole filter leans on (spec §6.2): business email configured on
 * a brand-new domain means a human deliberately set this domain up to be a
 * company. Parked-domain MX, or no MX at all, means almost certainly noise.
 */

export interface MxRecord {
  exchange: string;
  priority: number;
}

export interface MxClassification {
  provider: string | null;
  kind: MxProviderKind;
  /** True when a real business mail provider is configured. */
  isBusinessEmail: boolean;
  /** True when the MX itself is evidence of parking. */
  isParkingMx: boolean;
  /** All distinct providers seen, when a domain mixes them. */
  allProviders: string[];
}

const NONE: MxClassification = {
  provider: null,
  kind: 'none',
  isBusinessEmail: false,
  isParkingMx: false,
  allProviders: [],
};

/**
 * Classify a domain's MX records.
 *
 * Records are considered in priority order (lowest number = highest priority),
 * because the primary exchange is the one that actually receives mail. A domain
 * with Google as primary and some hosting fallback is a Google Workspace domain.
 */
export function classifyMx(records: readonly MxRecord[]): MxClassification {
  if (!records || records.length === 0) return NONE;

  // A "null MX" (RFC 7505) is an explicit statement that the domain accepts no
  // mail. It is a deliberate configuration, but not a business-email signal.
  const meaningful = records.filter((r) => r.exchange && r.exchange.trim() !== '' && r.exchange.trim() !== '.');
  if (meaningful.length === 0) {
    return { ...NONE, provider: 'null MX', kind: 'none' };
  }

  const sorted = [...meaningful].sort((a, b) => a.priority - b.priority);

  const providers: string[] = [];
  let primary: { name: string; kind: MxProviderKind } | null = null;
  let sawParking = false;

  for (const record of sorted) {
    const rule = lookupMxRule(record.exchange);
    if (rule) {
      if (!providers.includes(rule.name)) providers.push(rule.name);
      if (rule.kind === 'parking') sawParking = true;
      if (!primary) primary = { name: rule.name, kind: rule.kind };
    } else if (!primary) {
      // Self-hosted or an unrecognised provider. Someone still configured
      // *something*, which is weakly positive, but we do not claim to know what.
      primary = { name: null as unknown as string, kind: 'unknown' };
    }
  }

  if (!primary) return NONE;

  return {
    provider: primary.name ?? null,
    kind: primary.kind,
    isBusinessEmail: primary.kind === 'business' || primary.kind === 'security',
    isParkingMx: sawParking,
    allProviders: providers,
  };
}

/**
 * Whether the domain looks self-hosted: MX records that point at the domain
 * itself. Rare on a genuinely new registration, and mildly positive when seen —
 * somebody is running infrastructure.
 */
export function isSelfHostedMx(apex: string, records: readonly MxRecord[]): boolean {
  if (records.length === 0) return false;
  return records.every((r) => {
    const host = r.exchange.toLowerCase().replace(/\.$/, '');
    return host === apex || host.endsWith(`.${apex}`);
  });
}
