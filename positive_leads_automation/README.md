# Positive-leads automation (PlusVibe → GHL → reply+CC)

Automates, going forward, exactly what was done manually for the 133 recovered
Otto positives: every **new** positive (INTERESTED) reply in the PlusVibe unibox
(both workspaces, Cold-B2B + Warm-B2C) is:

1. **Created in GHL** — source `PlusVibe`, tags `NEW LEAD` + `Investor LQ` +
   language + `positive-reply`, **round-robin assigned by language**
   (FR → 8 agents, PT/BR → 3, EN → Mathieu/Pierre/Kevin/Sophie, ES → Carlos).
   GHL notifies the assigned agent automatically.
2. **Replied to** from PlusVibe, in the prospect's language (phone number +
   availability request, the template Thibaut validated), **CC the assigned
   agent + Thibaut**.
3. **Recorded** in `state.json` so it is never processed twice.

## How it runs

`.github/workflows/positive-leads.yml` runs `pipeline.py` every 15 minutes.
Dedup and round-robin position live in `state.json`, which the workflow commits
back after each run — so re-runs are idempotent and assignment stays even.
`concurrency: cancel-in-progress: false` guarantees two runs never overlap
(no double-sends).

`state.json` is **seeded with the 133 leads already handled**, so the automation
will not re-contact any of them; it only picks up genuinely new positives.

## Activation — one manual step (repo secrets)

The workflow is inert until these repository secrets are added
(Settings → Secrets and variables → Actions → New repository secret):

| Secret | Value |
|---|---|
| `PLUSVIBE_API_KEY` | the PlusVibe API key |
| `GHL_TOKEN` | the GHL v2 Private Integration Token (`pit-…`) |
| `GHL_LOCATION_ID` | the GHL location id (default `bu3JqdsMUIMYcVSRBSXs`) |
| `THIBAUT_EMAIL` | `tgueant@landquire.com` (optional; this is the default) |

Keys are **never** committed — they are read from the environment only.

## Test before going live

Trigger manually with a dry run (Actions → *Positive leads pipeline* → Run
workflow → set **dry_run = 1**). It logs what it *would* do — no contacts
created, no mail sent, no state change.

Locally:

```bash
export PLUSVIBE_API_KEY=... GHL_TOKEN=... DRY_RUN=1
python positive_leads_automation/pipeline.py
```

## Assignment safety (important)

The pipeline **never round-robins a lead that already has an owner**. For each
positive it first looks the contact up in GHL:

- **Already owned** → the existing owner is kept, `assignedTo` is *not* sent on
  the upsert, and the reply CCs that existing owner.
- **New / unassigned** → a round-robin agent is assigned and CC'd.

This fixes a bug in the first run where the round-robin overwrote existing owners
on ~70 pre-existing leads. To restore ownership that was already overwritten, use
`restore_owners.py` with a CSV (`email,owner`) taken from a pre-overwrite CRM
export or GHL's per-contact activity log:

```bash
DRY_RUN=1 GHL_TOKEN=... python positive_leads_automation/restore_owners.py owners.csv
```

## Real names in the greeting

The greeting uses the prospect's real first name from the reply's display name
(`from_address_json[0].name`), MIME-decoded and cleaned (handles "LASTNAME First"
and "- Company" suffixes). When there is no usable name it falls back to a plain
"Bonjour," — **never** the email prefix (the old bug that produced "Pfpelletier"
for `pfpelletier@outlook.com`, whose real name is Félix).

## Handoff = hard stop of all automation (per Thibaut)

Once a lead is handed to an agent (first positive reply → assigned + agent CC'd),
**all automation stops for that lead**:

1. The pipeline sends exactly one reply (the phone + availability ask) and CCs the
   agent — the single handoff touch.
2. It then calls `stop_lead_automation()`, which sets the lead to `COMPLETED` on
   **every campaign in both workspaces** where it is still active — so the prospect
   never receives another automated sequence email (a lead can sit in several
   campaigns at once; all are stopped).
3. The lead is recorded in `state.json > handoff`; it is never auto-replied to
   again, and the pipeline never books meetings — the agent runs it manually.

Retroactive one-off for leads already assigned before this rule existed:
`python stop_automation.py` (sets COMPLETED on every still-active campaign record
for the already-handed-off positives).

## Ongoing replies are forwarded to the agent (no auto-reply)

Because a prospect usually replies only to the sending mailbox (not "reply all"),
the CC does not carry their later replies to the agent. Each cycle,
`forward_new_replies()` scans inbound messages and, for any **new** reply on an
already-handed-off lead, logs it as a **GHL note on that lead's contact** (which is
assigned to the agent, so GHL notifies them). No emails are sent to prospects —
the agent picks up the conversation from GHL.

## Phone capture → GHL

`extract_phone()` pulls a phone number from the prospect's reply signature when
present and writes it to the GHL contact's `phone` field, so the agent has the
number without manual work. Falls back to blank when none is found (an enrichment
finder can be added here later).

## Stop-on-reply

Because each prospect is added to `state.json` after the first automated reply, the
pipeline never sends a second automated message to the same person — once the
conversation is human, it stays human.
