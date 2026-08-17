import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { SCORING_VERSION, env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { applyRules, type RulesInput } from '@/score/rules';
import { computeScore } from '@/score/composite';
import { classifyBatch, type ClassifierInput, type Classification } from '@/score/classifier';

/**
 * Evaluation harness (spec §7).
 *
 * "Every scoring change gets measured against it. Without this you are tuning
 * blind, and precision is the entire product."
 *
 * The labelled set lives in `eval/labels.csv`, in-repo, so a scoring change and
 * its measured effect land in the same commit and can be reviewed together.
 *
 * Two modes:
 *   --rules-only   measures the deterministic layer alone. Free and instant, so
 *                  it can run on every change.
 *   (default)      measures the full pipeline including the classifier.
 *
 * The metric that matters is **precision on the "good" class at the delivery
 * threshold** — a customer who receives ten domains and finds three real ones
 * stops paying. Recall matters second: there are 300k domains a day and missing
 * some is survivable.
 */

const log = createLogger('eval');

export interface LabelledDomain extends RulesInput {
  /** Ground truth: is this a real business worth surfacing? */
  label: 'good' | 'garbage';
  notes?: string;
}

const LABELS_PATH = fileURLToPath(new URL('../../eval/labels.csv', import.meta.url));

/** Parse one CSV line, honouring quoted fields containing commas. */
function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i]!;
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        current += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ',') {
      fields.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

export function parseLabelsCsv(content: string): LabelledDomain[] {
  const lines = content.split('\n').filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];

  const header = parseCsvLine(lines[0]!).map((h) => h.trim());
  const index = (name: string) => header.indexOf(name);

  const out: LabelledDomain[] = [];

  for (const line of lines.slice(1)) {
    if (line.trim().startsWith('#')) continue;
    const fields = parseCsvLine(line);
    const get = (name: string) => {
      const i = index(name);
      return i >= 0 ? (fields[i] ?? '').trim() : '';
    };
    const bool = (name: string) => get(name).toLowerCase() === 'true';
    const num = (name: string) => {
      const v = get(name);
      return v === '' ? null : Number(v);
    };

    const apex = get('apex');
    if (!apex) continue;

    const label = get('label').toLowerCase();
    if (label !== 'good' && label !== 'garbage') continue;

    const ageDays = num('age_days');

    out.push({
      apex,
      tld: get('tld') || apex.split('.').slice(1).join('.'),
      label,
      notes: get('notes') || undefined,
      hasA: bool('has_a'),
      hasMx: bool('has_mx'),
      mxProvider: get('mx_provider') || null,
      mxProviderKind: get('mx_kind') || null,
      hasSpf: bool('has_spf'),
      hasDmarc: bool('has_dmarc'),
      httpStatus: num('http_status'),
      isParked: bool('is_parked'),
      parkingVendor: get('parking_vendor') || null,
      title: get('title') || null,
      metaDescription: get('meta_description') || null,
      bodySnippet: get('body_snippet') || null,
      tech: get('tech') ? get('tech').split('|').filter(Boolean) : [],
      redirectedOffDomain: bool('redirected_off_domain'),
      robotsAllowed: true,
      registrar: get('registrar') || null,
      registrationDate: ageDays === null ? null : new Date(Date.now() - ageDays * 86_400_000),
      source: get('source') || 'nrd_feed',
      ctHitCount: num('ct_hits') ?? 0,
      firstSeenAt: new Date(),
    });
  }

  return out;
}

export function loadLabels(path = LABELS_PATH): LabelledDomain[] {
  if (!existsSync(path)) {
    throw new Error(
      `no labelled set at ${path}. Build one with: npm run sample -- --date=YYYY-MM-DD --n=400 > eval/labels.csv, then label the rows by hand.`,
    );
  }
  return parseLabelsCsv(readFileSync(path, 'utf8'));
}

// --- Metrics ---------------------------------------------------------------

export interface ConfusionMatrix {
  truePositives: number;
  falsePositives: number;
  trueNegatives: number;
  falseNegatives: number;
}

export interface Metrics extends ConfusionMatrix {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  /** How many of the labelled set we would actually deliver. */
  deliveredCount: number;
}

export function computeMetrics(
  scored: { label: 'good' | 'garbage'; score: number }[],
  threshold: number,
): Metrics {
  let tp = 0;
  let fp = 0;
  let tn = 0;
  let fn = 0;

  for (const row of scored) {
    const delivered = row.score >= threshold;
    if (delivered && row.label === 'good') tp += 1;
    else if (delivered && row.label === 'garbage') fp += 1;
    else if (!delivered && row.label === 'garbage') tn += 1;
    else fn += 1;
  }

  const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
  const recall = tp + fn === 0 ? 0 : tp / (tp + fn);

  return {
    threshold,
    truePositives: tp,
    falsePositives: fp,
    trueNegatives: tn,
    falseNegatives: fn,
    precision,
    recall,
    f1: precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall),
    accuracy: scored.length === 0 ? 0 : (tp + tn) / scored.length,
    deliveredCount: tp + fp,
  };
}

// --- Runner ----------------------------------------------------------------

export interface EvalResult {
  scoringVersion: string;
  model: string | null;
  labelled: number;
  good: number;
  garbage: number;
  /** Rules layer measured on its own: how much does it kill, and correctly? */
  rulesKilled: number;
  rulesKilledCorrectly: number;
  rulesFalseKills: { apex: string; notes?: string }[];
  metricsByThreshold: Metrics[];
  scored: { apex: string; label: string; score: number; tier: string; reason: string }[];
}

export async function runEval(options: { useClassifier?: boolean; labels?: LabelledDomain[] } = {}): Promise<EvalResult> {
  const labels = options.labels ?? loadLabels();
  const useClassifier =
    options.useClassifier ?? (env.CLASSIFIER_ENABLED && Boolean(env.ANTHROPIC_API_KEY));

  if (labels.length === 0) throw new Error('labelled set is empty');

  // --- Rules layer ---
  const verdicts = labels.map((l) => ({ label: l, verdict: applyRules(l) }));
  const killed = verdicts.filter((v) => v.verdict.verdict === 'kill');
  const survivors = verdicts.filter((v) => v.verdict.verdict === 'pass');

  /**
   * A false kill is the expensive error: the domain silently never surfaces and
   * nobody ever finds out it was missed. These are listed individually so they
   * can be looked at, not just counted.
   */
  const falseKills = killed
    .filter((k) => k.label.label === 'good')
    .map((k) => ({ apex: k.label.apex, notes: k.label.notes }));

  // --- Classifier on survivors only, exactly as production does it ---
  let classifications = new Map<string, Classification>();
  if (useClassifier && survivors.length > 0) {
    const inputs: ClassifierInput[] = survivors.map((s) => ({
      apex: s.label.apex,
      tld: s.label.tld,
      title: s.label.title,
      metaDescription: s.label.metaDescription,
      bodySnippet: s.label.bodySnippet,
      mxProvider: s.label.mxProvider,
      tech: s.label.tech,
      registrar: s.label.registrar,
      country: null,
    }));
    const batch = await classifyBatch(inputs);
    classifications = batch.results;
  }

  // --- Composite ---
  const scored = verdicts.map(({ label, verdict }) => {
    const composite = computeScore({
      verdict,
      classification: classifications.get(label.apex) ?? null,
      mxProvider: label.mxProvider,
    });
    return {
      apex: label.apex,
      label: label.label,
      score: composite.score,
      tier: composite.tier,
      reason: composite.reason,
    };
  });

  const forMetrics = scored.map((s) => ({ label: s.label as 'good' | 'garbage', score: s.score }));

  return {
    scoringVersion: SCORING_VERSION,
    model: useClassifier ? env.CLASSIFIER_MODEL : null,
    labelled: labels.length,
    good: labels.filter((l) => l.label === 'good').length,
    garbage: labels.filter((l) => l.label === 'garbage').length,
    rulesKilled: killed.length,
    rulesKilledCorrectly: killed.filter((k) => k.label.label === 'garbage').length,
    rulesFalseKills: falseKills,
    metricsByThreshold: [40, 50, 60, 70, 80].map((t) => computeMetrics(forMetrics, t)),
    scored,
  };
}

// --- CLI -------------------------------------------------------------------

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

async function main() {
  const rulesOnly = process.argv.includes('--rules-only');
  const verbose = process.argv.includes('--verbose');

  const result = await runEval(rulesOnly ? { useClassifier: false } : {});

  const lines: string[] = [];
  lines.push('');
  lines.push(`novaX evaluation — scoring ${result.scoringVersion}${result.model ? ` + ${result.model}` : ' (rules only)'}`);
  lines.push('='.repeat(72));
  lines.push(`Labelled set: ${result.labelled} domains (${result.good} good, ${result.garbage} garbage)`);
  lines.push('');
  lines.push('Rules layer');
  lines.push(
    `  killed ${result.rulesKilled}/${result.labelled} (${pct(result.rulesKilled / result.labelled)}), ` +
      `of which ${result.rulesKilledCorrectly} were genuinely garbage ` +
      `(${result.rulesKilled === 0 ? 'n/a' : pct(result.rulesKilledCorrectly / result.rulesKilled)} correct)`,
  );
  lines.push(`  false kills (a real business silently dropped): ${result.rulesFalseKills.length}`);
  for (const fk of result.rulesFalseKills) {
    lines.push(`    - ${fk.apex}${fk.notes ? ` (${fk.notes})` : ''}`);
  }
  lines.push('');
  lines.push('Composite score, by delivery threshold');
  lines.push('  thresh  delivered  precision   recall       f1');
  for (const m of result.metricsByThreshold) {
    lines.push(
      `  ${String(m.threshold).padStart(6)}  ${String(m.deliveredCount).padStart(9)}  ` +
        `${pct(m.precision).padStart(9)}  ${pct(m.recall).padStart(7)}  ${pct(m.f1).padStart(7)}`,
    );
  }
  lines.push('');
  lines.push('Precision is the number to watch: it is what a customer experiences.');

  if (verbose) {
    lines.push('');
    lines.push('Misclassified at threshold 60:');
    for (const s of result.scored) {
      const delivered = s.score >= 60;
      if ((delivered && s.label === 'garbage') || (!delivered && s.label === 'good')) {
        lines.push(`  [${s.label.padEnd(7)} scored ${String(s.score).padStart(3)}] ${s.apex}`);
        lines.push(`      ${s.reason.slice(0, 160)}`);
      }
    }
  }

  lines.push('');
  process.stdout.write(lines.join('\n'));
}

// Only run the CLI when invoked directly, not when imported by tests.
if (process.argv[1] && process.argv[1].includes('eval/run')) {
  main().catch((err) => {
    log.error('eval failed', err);
    process.exit(1);
  });
}
