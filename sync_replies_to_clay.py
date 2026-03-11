"""
sync_replies_to_clay.py
━━━━━━━━━━━━━━━━━━━━━━━
Polls the EmailBison /replies endpoint for new replies, enriches each one
with lead + campaign data, and forwards the full payload to a Clay webhook.

State is persisted in .sync_state.json so every run only processes replies
newer than the last successful send.

Usage:
  python3 sync_replies_to_clay.py           # run once (new replies only)
  python3 sync_replies_to_clay.py --all     # backfill ALL replies
  python3 sync_replies_to_clay.py --dry-run # print payloads, don't send

Cron (every 5 min):
  */5 * * * * cd /home/user/claude && python3 sync_replies_to_clay.py >> sync_replies.log 2>&1
"""

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
BISON_API_KEY  = '22|NRB2d09ACUZrCn0CdSZb8VCf6kVKOV6TddvXkblD024e9b76'
BISON_BASE_URL = 'https://send.breakoutcreatives.com/api'
CLAY_WEBHOOK   = ('https://api.clay.com/v3/sources/webhook/'
                  'pull-in-data-from-a-webhook-2dfb6667-e51c-451f-8f2e-80a70809bd7a')
STATE_FILE      = Path(__file__).parent / '.sync_state.json'
PER_PAGE        = 100   # replies per Bison page
CLAY_WORKERS    = 3     # concurrent Clay sends
CLAY_SEND_DELAY = 0.3   # seconds between each Clay send (avoid 429s)
BISON_DELAY     = 0.05  # seconds between Bison API calls

def is_positive_reply(reply: dict) -> bool:
    """
    Positive = genuine human reply.
    Excludes: OOO / auto-responders, bounces, delivery failure notifications.
    """
    if reply.get('automated_reply'):
        return False
    if reply.get('folder', '').lower() == 'bounced':
        return False
    return True

BISON_H = {'Authorization': f'Bearer {BISON_API_KEY}', 'Accept': 'application/json'}
CLAY_H  = {'Content-Type': 'application/json'}

# ── State helpers ─────────────────────────────────────────────────────────────
_state_lock = threading.Lock()

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {'last_reply_id': 0, 'last_run': None}

def save_state(state: dict):
    with _state_lock:
        STATE_FILE.write_text(json.dumps(state, indent=2))

# ── Bison API ─────────────────────────────────────────────────────────────────
def bison_get(path: str, params: dict = None) -> dict:
    r = requests.get(f'{BISON_BASE_URL}{path}', headers=BISON_H,
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# Pre-loaded caches (populated at startup)
_campaign_cache: dict[int, dict] = {}
_lead_cache:     dict[int, dict] = {}
_lead_lock = threading.Lock()

def preload_campaigns():
    """Fetch all campaigns once at startup — only ~15 records."""
    r = bison_get('/campaigns', params={'per_page': 200})
    for c in r.get('data', []):
        _campaign_cache[c['id']] = c
    print(f'  Cached {len(_campaign_cache)} campaigns.')

def get_lead(lead_id: int) -> dict:
    with _lead_lock:
        if lead_id in _lead_cache:
            return _lead_cache[lead_id]
    try:
        data = bison_get(f'/leads/{lead_id}').get('data', {})
        time.sleep(BISON_DELAY)
    except Exception as exc:
        print(f'    [warn] lead {lead_id}: {exc}')
        data = {}
    with _lead_lock:
        _lead_cache[lead_id] = data
    return data

# ── Payload builder ───────────────────────────────────────────────────────────
def build_payload(reply: dict) -> dict:
    lead_id     = reply.get('lead_id')
    campaign_id = reply.get('campaign_id')
    lead        = get_lead(lead_id)          if lead_id     else {}
    campaign    = _campaign_cache.get(campaign_id, {}) if campaign_id else {}

    custom_vars = {cv['name']: cv['value']
                   for cv in lead.get('custom_variables', [])}

    lead_camp_stats = next(
        (s for s in lead.get('lead_campaign_data', [])
         if s.get('campaign_id') == campaign_id),
        {}
    )

    return {
        # ── Reply ─────────────────────────────────────────────────────────
        'reply_id':                 reply.get('id'),
        'reply_uuid':               reply.get('uuid'),
        'reply_folder':             reply.get('folder'),
        'reply_subject':            reply.get('subject'),
        'reply_text_body':          reply.get('text_body'),
        'reply_html_body':          reply.get('html_body'),
        'reply_date_received':      reply.get('date_received'),
        'reply_created_at':         reply.get('created_at'),
        'reply_updated_at':         reply.get('updated_at'),
        'reply_type':               reply.get('type'),
        'reply_tracked':            reply.get('tracked_reply'),
        'reply_automated':          reply.get('automated_reply'),
        'reply_read':               reply.get('read'),
        'reply_interested':         reply.get('interested'),
        'reply_from_name':          reply.get('from_name'),
        'reply_from_email':         reply.get('from_email_address'),
        'reply_to_email':           reply.get('primary_to_email_address'),
        'reply_to':                 reply.get('to'),
        'reply_cc':                 reply.get('cc'),
        'reply_bcc':                reply.get('bcc'),
        'reply_message_id':         reply.get('raw_message_id'),
        'reply_scheduled_email_id': reply.get('scheduled_email_id'),
        'reply_parent_id':          reply.get('parent_id'),
        'reply_attachments':        reply.get('attachments'),

        # ── Campaign ──────────────────────────────────────────────────────
        'campaign_id':              campaign_id,
        'campaign_name':            campaign.get('name'),
        'campaign_type':            campaign.get('type'),
        'campaign_status':          campaign.get('status'),
        'campaign_uuid':            campaign.get('uuid'),
        'campaign_emails_sent':     campaign.get('emails_sent'),
        'campaign_opened':          campaign.get('opened'),
        'campaign_unique_opens':    campaign.get('unique_opens'),
        'campaign_replied':         campaign.get('replied'),
        'campaign_unique_replies':  campaign.get('unique_replies'),
        'campaign_bounced':         campaign.get('bounced'),
        'campaign_unsubscribed':    campaign.get('unsubscribed'),
        'campaign_interested':      campaign.get('interested'),
        'campaign_total_leads':     campaign.get('total_leads'),
        'campaign_completion_pct':  campaign.get('completion_percentage'),
        'campaign_created_at':      campaign.get('created_at'),

        # ── Lead ──────────────────────────────────────────────────────────
        'lead_id':                  lead_id,
        'lead_first_name':          lead.get('first_name'),
        'lead_last_name':           lead.get('last_name'),
        'lead_full_name':           (f"{lead.get('first_name','')} {lead.get('last_name','')}".strip() or None),
        'lead_email':               lead.get('email'),
        'lead_title':               lead.get('title'),
        'lead_company':             lead.get('company'),
        'lead_notes':               lead.get('notes'),
        'lead_status':              lead.get('status'),
        'lead_created_at':          lead.get('created_at'),
        'lead_updated_at':          lead.get('updated_at'),
        'lead_tags':                [t['name'] for t in lead.get('tags', [])],
        'lead_custom_variables':    custom_vars,

        # ── Lead × Campaign stats ──────────────────────────────────────────
        'lead_camp_status':         lead_camp_stats.get('status'),
        'lead_camp_emails_sent':    lead_camp_stats.get('emails_sent'),
        'lead_camp_replies':        lead_camp_stats.get('replies'),
        'lead_camp_opens':          lead_camp_stats.get('opens'),
        'lead_camp_interested':     lead_camp_stats.get('interested'),

        # ── Lead overall stats ────────────────────────────────────────────
        'lead_total_emails_sent':   lead.get('overall_stats', {}).get('emails_sent'),
        'lead_total_opens':         lead.get('overall_stats', {}).get('opens'),
        'lead_total_replies':       lead.get('overall_stats', {}).get('replies'),

        # ── Meta ──────────────────────────────────────────────────────────
        'synced_at': datetime.now(timezone.utc).isoformat(),
    }

# ── Clay sender ───────────────────────────────────────────────────────────────
def send_to_clay(payload: dict, dry_run: bool) -> bool:
    if dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return True
    time.sleep(CLAY_SEND_DELAY)
    for attempt in range(4):
        try:
            r = requests.post(CLAY_WEBHOOK, headers=CLAY_H, json=payload, timeout=30)
            if r.ok:
                return True
            if r.status_code == 429 or r.status_code >= 500:
                wait = 2 ** attempt
                print(f'    [retry] Clay {r.status_code} — waiting {wait}s')
                time.sleep(wait)
                continue
            print(f'    [error] Clay {r.status_code}: {r.text[:120]}')
            return False
        except Exception as exc:
            wait = 2 ** attempt
            print(f'    [retry] Clay exception: {exc} — waiting {wait}s')
            time.sleep(wait)
    return False

# ── Reply page iterator (oldest → newest) ─────────────────────────────────────
def iter_reply_pages(since_id: int):
    """
    Yields individual reply dicts with id > since_id, in ascending id order.
    Streams page-by-page so memory stays constant.

    Strategy: sort newest-first, find last page that might contain since_id,
    then walk pages from newest toward that boundary collecting replies > since_id.
    For --all (since_id=0) we walk every page oldest-first (reverse pagination).
    """
    # First, discover total pages
    first = bison_get('/replies', params={'per_page': PER_PAGE, 'page': 1, 'sort': '-id'})
    last_page = first.get('meta', {}).get('last_page', 1)

    # Walk from oldest page → newest (last_page → 1) so we process chronologically
    # and can checkpoint after each page.
    for page in range(last_page, 0, -1):
        resp = bison_get('/replies', params={'per_page': PER_PAGE, 'page': page, 'sort': '-id'})
        items = resp.get('data', [])
        if not items:
            continue
        # Page is oldest-first when reversed (since we fetched newest-first)
        for item in reversed(items):
            if item['id'] > since_id and is_positive_reply(item):
                yield item
        time.sleep(BISON_DELAY)

# ── Incremental mode (new replies only, page 1 only) ─────────────────────────
def iter_new_replies(since_id: int):
    """Walk page 1 (newest) and stop as soon as we hit since_id."""
    page = 1
    while True:
        resp = bison_get('/replies', params={'per_page': PER_PAGE, 'page': page, 'sort': '-id'})
        items = resp.get('data', [])
        if not items:
            break
        found_boundary = False
        batch = []
        for item in items:
            if item['id'] <= since_id:
                found_boundary = True
                break
            if is_positive_reply(item):
                batch.append(item)
        yield from reversed(batch)   # oldest-first within batch
        if found_boundary or page >= resp.get('meta', {}).get('last_page', 1):
            break
        page += 1
        time.sleep(BISON_DELAY)

# ── Process a batch with thread-pool Clay sends ───────────────────────────────
def process_batch(replies: list[dict], state: dict, dry_run: bool) -> tuple[int, int]:
    """Build payloads (lead fetch is serial/cached), send to Clay in parallel."""
    # Build payloads serially (lead API calls must be serial to avoid hammering Bison)
    payloads = [(r['id'], build_payload(r)) for r in replies]

    sent = failed = 0
    with ThreadPoolExecutor(max_workers=CLAY_WORKERS) as pool:
        futures = {pool.submit(send_to_clay, p, dry_run): rid for rid, p in payloads}
        for fut in as_completed(futures):
            rid = futures[fut]
            ok = fut.result()
            if ok:
                sent += 1
                state['last_reply_id'] = max(state.get('last_reply_id', 0), rid)
                if not dry_run:
                    save_state(state)
            else:
                failed += 1
                print(f'    [error] reply {rid} failed Clay send')
    return sent, failed

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all',     action='store_true', help='Backfill ALL replies')
    parser.add_argument('--dry-run', action='store_true', help='Print payloads, no HTTP send')
    args = parser.parse_args()

    state    = load_state()
    since_id = 0 if args.all else state.get('last_reply_id', 0)

    print(f'[{datetime.now().isoformat()}] Starting sync  since_id={since_id}  dry_run={args.dry_run}')

    preload_campaigns()

    source = iter_reply_pages(since_id) if args.all else iter_new_replies(since_id)

    total_sent = total_failed = 0
    batch: list[dict] = []
    BATCH_SIZE = 50   # process in chunks of 50

    for reply in source:
        batch.append(reply)
        if len(batch) >= BATCH_SIZE:
            s, f = process_batch(batch, state, args.dry_run)
            total_sent += s; total_failed += f
            print(f'  [{datetime.now().strftime("%H:%M:%S")}] '
                  f'sent={total_sent} failed={total_failed} '
                  f'checkpoint={state["last_reply_id"]}')
            batch.clear()

    if batch:
        s, f = process_batch(batch, state, args.dry_run)
        total_sent += s; total_failed += f

    state['last_run'] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f'[done] sent={total_sent} failed={total_failed} checkpoint={state["last_reply_id"]}')


if __name__ == '__main__':
    main()
