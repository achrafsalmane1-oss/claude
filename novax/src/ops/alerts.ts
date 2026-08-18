import { env } from '@/config/env';
import { fetchWithLimits } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { buildHealthReport } from './health';

/**
 * Alerting (spec §11).
 *
 * "Alert if the CT stream is silent for more than 10 minutes or the daily feed
 * fails." Delivery is a plain webhook POST rather than a vendor SDK, because
 * that works with Slack, Discord, PagerDuty and a shell script equally well.
 *
 * Alerts deduplicate on the problem text: a CT outage lasting an hour should be
 * one message, not twelve.
 */

const log = createLogger('ops.alerts');

const RE_ALERT_AFTER_MS = 3_600_000;
const sent = new Map<string, number>();

export interface AlertResult {
  fired: string[];
  suppressed: string[];
  status: string;
}

export async function sendAlert(text: string): Promise<boolean> {
  if (!env.ALERT_WEBHOOK_URL) {
    log.warn('alert not delivered: ALERT_WEBHOOK_URL is not set', { alert: text });
    return false;
  }

  try {
    await fetchWithLimits(env.ALERT_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      // `text` is what Slack and Discord both read; `content` is Discord's key.
      body: JSON.stringify({ text: `[novaX] ${text}`, content: `[novaX] ${text}` }),
      timeoutMs: 10_000,
      maxBytes: 4096,
    });
    return true;
  } catch (err) {
    log.error('failed to deliver alert', err, { alert: text });
    return false;
  }
}

/** Check health and fire alerts for anything new. */
export async function checkAndAlert(): Promise<AlertResult> {
  const report = await buildHealthReport();
  const fired: string[] = [];
  const suppressed: string[] = [];
  const now = Date.now();

  for (const problem of report.problems) {
    const lastSent = sent.get(problem);
    if (lastSent !== undefined && now - lastSent < RE_ALERT_AFTER_MS) {
      suppressed.push(problem);
      continue;
    }
    await sendAlert(problem);
    sent.set(problem, now);
    fired.push(problem);
  }

  // Clear the memory of problems that have resolved, so a recurrence alerts
  // again immediately rather than waiting out the dedupe window.
  for (const key of sent.keys()) {
    if (!report.problems.includes(key)) {
      sent.delete(key);
      log.info('problem resolved', { problem: key });
    }
  }

  if (fired.length > 0) {
    log.warn('alerts fired', { count: fired.length, problems: fired });
  }

  return { fired, suppressed, status: report.status };
}
