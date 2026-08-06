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

## Stop-on-reply

The agent works the lead in GHL from there. Because each prospect is added to
`state.json` after the first automated reply, the pipeline never sends a second
automated message to the same person — once the conversation is human, it stays
human.
