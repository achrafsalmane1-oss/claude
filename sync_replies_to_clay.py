"""
sync_replies_to_clay.py
━━━━━━━━━━━━━━━━━━━━━━━
Polls the EmailBison /replies endpoint for new replies, enriches each one
with lead + campaign data, and forwards the full payload to a Clay webhook.

State is persisted in .sync_state.json so every run only processes replies
newer than the last successful send.

Usage:
  python3 sync_replies_to_clay.py           # run once
  python3 sync_replies_to_clay.py --all     # re-process ALL replies (ignore state)
  python3 sync_replies_to_clay.py --dry-run # print payloads, don't send

Cron (every 5 min):
  */5 * * * * cd /home/user/claude && python3 sync_replies_to_clay.py >> sync_replies.log 2>&1
"""

import argparse
import json
import os
import sys
import time
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
STATE_FILE     = Path(__file__).parent / '.sync_state.json'
PER_PAGE       = 100          # max per request
INTER_REQ_DELAY = 0.15        # seconds between Bison API calls (rate-limit safety)

BISON_H = {
    'Authorization': f'Bearer {BISON_API_KEY}',
    'Accept': 'application/json',
}
CLAY_H = {'Content-Type': 'application/json'}


# ── State helpers ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {'last_reply_id': 0, 'last_run': None}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Bison API helpers ─────────────────────────────────────────────────────────
def bison_get(path: str, params: dict = None) -> dict:
    url = f'{BISON_BASE_URL}{path}'
    r = requests.get(url, headers=BISON_H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


_lead_cache: dict[int, dict] = {}
_campaign_cache: dict[int, dict] = {}


def get_lead(lead_id: int) -> dict:
    if lead_id in _lead_cache:
        return _lead_cache[lead_id]
    try:
        data = bison_get(f'/leads/{lead_id}').get('data', {})
        time.sleep(INTER_REQ_DELAY)
    except Exception as exc:
        print(f'    [warn] lead {lead_id} fetch failed: {exc}')
        data = {}
    _lead_cache[lead_id] = data
    return data


def get_campaign(campaign_id: int) -> dict:
    if campaign_id in _campaign_cache:
        return _campaign_cache[campaign_id]
    try:
        data = bison_get(f'/campaigns/{campaign_id}').get('data', {})
        time.sleep(INTER_REQ_DELAY)
    except Exception as exc:
        print(f'    [warn] campaign {campaign_id} fetch failed: {exc}')
        data = {}
    _campaign_cache[campaign_id] = data
    return data


# ── Payload builder ───────────────────────────────────────────────────────────
def build_payload(reply: dict) -> dict:
    lead_id     = reply.get('lead_id')
    campaign_id = reply.get('campaign_id')

    lead     = get_lead(lead_id)     if lead_id     else {}
    campaign = get_campaign(campaign_id) if campaign_id else {}

    # Flatten custom_variables → dict
    custom_vars = {cv['name']: cv['value']
                   for cv in lead.get('custom_variables', [])}

    # Lead campaign stats for THIS campaign
    lead_camp_stats = next(
        (s for s in lead.get('lead_campaign_data', [])
         if s.get('campaign_id') == campaign_id),
        {}
    )

    return {
        # ── Reply core ────────────────────────────────────────────────────
        'reply_id':               reply.get('id'),
        'reply_uuid':             reply.get('uuid'),
        'reply_folder':           reply.get('folder'),
        'reply_subject':          reply.get('subject'),
        'reply_text_body':        reply.get('text_body'),
        'reply_html_body':        reply.get('html_body'),
        'reply_date_received':    reply.get('date_received'),
        'reply_created_at':       reply.get('created_at'),
        'reply_updated_at':       reply.get('updated_at'),
        'reply_type':             reply.get('type'),
        'reply_tracked':          reply.get('tracked_reply'),
        'reply_automated':        reply.get('automated_reply'),
        'reply_read':             reply.get('read'),
        'reply_interested':       reply.get('interested'),
        'reply_from_name':        reply.get('from_name'),
        'reply_from_email':       reply.get('from_email_address'),
        'reply_to_email':         reply.get('primary_to_email_address'),
        'reply_to':               reply.get('to'),
        'reply_cc':               reply.get('cc'),
        'reply_bcc':              reply.get('bcc'),
        'reply_message_id':       reply.get('raw_message_id'),
        'reply_scheduled_email_id': reply.get('scheduled_email_id'),
        'reply_parent_id':        reply.get('parent_id'),
        'reply_attachments':      reply.get('attachments'),

        # ── Campaign ──────────────────────────────────────────────────────
        'campaign_id':            campaign_id,
        'campaign_name':          campaign.get('name'),
        'campaign_type':          campaign.get('type'),
        'campaign_status':        campaign.get('status'),
        'campaign_uuid':          campaign.get('uuid'),
        'campaign_emails_sent':   campaign.get('emails_sent'),
        'campaign_opened':        campaign.get('opened'),
        'campaign_unique_opens':  campaign.get('unique_opens'),
        'campaign_replied':       campaign.get('replied'),
        'campaign_unique_replies': campaign.get('unique_replies'),
        'campaign_bounced':       campaign.get('bounced'),
        'campaign_unsubscribed':  campaign.get('unsubscribed'),
        'campaign_interested':    campaign.get('interested'),
        'campaign_total_leads':   campaign.get('total_leads'),
        'campaign_completion_pct': campaign.get('completion_percentage'),
        'campaign_created_at':    campaign.get('created_at'),

        # ── Lead ──────────────────────────────────────────────────────────
        'lead_id':                lead_id,
        'lead_first_name':        lead.get('first_name'),
        'lead_last_name':         lead.get('last_name'),
        'lead_full_name':         f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or None,
        'lead_email':             lead.get('email'),
        'lead_title':             lead.get('title'),
        'lead_company':           lead.get('company'),
        'lead_notes':             lead.get('notes'),
        'lead_status':            lead.get('status'),
        'lead_created_at':        lead.get('created_at'),
        'lead_updated_at':        lead.get('updated_at'),
        'lead_tags':              [t['name'] for t in lead.get('tags', [])],
        'lead_custom_variables':  custom_vars,

        # ── Lead × Campaign stats ──────────────────────────────────────────
        'lead_camp_status':       lead_camp_stats.get('status'),
        'lead_camp_emails_sent':  lead_camp_stats.get('emails_sent'),
        'lead_camp_replies':      lead_camp_stats.get('replies'),
        'lead_camp_opens':        lead_camp_stats.get('opens'),
        'lead_camp_interested':   lead_camp_stats.get('interested'),

        # ── Lead overall stats ────────────────────────────────────────────
        'lead_total_emails_sent': lead.get('overall_stats', {}).get('emails_sent'),
        'lead_total_opens':       lead.get('overall_stats', {}).get('opens'),
        'lead_total_replies':     lead.get('overall_stats', {}).get('replies'),

        # ── Meta ──────────────────────────────────────────────────────────
        'synced_at': datetime.now(timezone.utc).isoformat(),
    }


# ── Clay sender ───────────────────────────────────────────────────────────────
def send_to_clay(payload: dict, dry_run: bool) -> bool:
    if dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return True
    try:
        r = requests.post(CLAY_WEBHOOK, headers=CLAY_H,
                          json=payload, timeout=30)
        if r.ok:
            return True
        print(f'    [error] Clay {r.status_code}: {r.text[:200]}')
        return False
    except Exception as exc:
        print(f'    [error] Clay request failed: {exc}')
        return False


# ── Fetch new replies ─────────────────────────────────────────────────────────
def fetch_new_replies(since_id: int) -> list[dict]:
    """
    Returns replies with id > since_id, newest-first → reversed to oldest-first
    so we process and checkpoint in chronological order.
    """
    collected = []
    page = 1
    done = False

    while not done:
        resp = bison_get('/replies', params={
            'per_page': PER_PAGE,
            'page': page,
            'sort': '-id',          # newest first
        })
        items = resp.get('data', [])
        if not items:
            break

        for item in items:
            if item['id'] <= since_id:
                done = True
                break
            collected.append(item)

        meta = resp.get('meta', {})
        if page >= meta.get('last_page', 1):
            break
        page += 1
        time.sleep(INTER_REQ_DELAY)

    # Return in chronological order so we checkpoint incrementally
    return list(reversed(collected))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all',     action='store_true', help='Re-process all replies')
    parser.add_argument('--dry-run', action='store_true', help='Print payloads, no HTTP send')
    args = parser.parse_args()

    state   = load_state()
    since_id = 0 if args.all else state.get('last_reply_id', 0)

    print(f'[{datetime.now().isoformat()}] Starting sync. since_reply_id={since_id}')

    replies = fetch_new_replies(since_id)
    print(f'  Found {len(replies)} new reply(ies) to process.')

    if not replies:
        state['last_run'] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    sent = 0
    failed = 0
    max_id = state.get('last_reply_id', 0)

    for reply in replies:
        rid = reply['id']
        print(f'  → reply {rid} | camp={reply.get("campaign_id")} '
              f'| lead={reply.get("lead_id")} | {reply.get("from_email_address")}')

        payload = build_payload(reply)
        ok = send_to_clay(payload, dry_run=args.dry_run)

        if ok:
            sent += 1
            max_id = max(max_id, rid)
            if not args.dry_run:
                state['last_reply_id'] = max_id
                state['last_run'] = datetime.now(timezone.utc).isoformat()
                save_state(state)
        else:
            failed += 1

        time.sleep(INTER_REQ_DELAY)

    print(f'[done] sent={sent} failed={failed} new_checkpoint={max_id}')


if __name__ == '__main__':
    main()
