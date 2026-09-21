# Outreach — local multichannel sequencer

A self-hosted outreach MVP: import a CSV of leads, run them through a **waterfall**
of email → LinkedIn → cold call steps, work the manual touches from a queue, and
read every reply in one master inbox with reporting on top.

**Costs nothing and talks to no third-party service.** Pure Python standard
library, SQLite on disk, a vanilla-JS front end served from the same process.
No pip install, no npm install, no API keys, no vendor account.

```bash
python3 outreach/app.py --open        # http://127.0.0.1:8000
```

That's the whole setup. First run creates `outreach/data/outreach.db` and starts
in **dry run** — the full waterfall executes and every email is recorded, but
nothing leaves your machine until you configure SMTP.

---

## What it actually does about each channel

Being blunt about this, because it decides how you use the tool:

| Channel | How it works here | Why |
|---|---|---|
| **Email** | Sends for real through **your own mailbox** over SMTP (Gmail app password, Outlook, any host). Opens tracked by a pixel served by this app. Replies pulled back over IMAP. | Your mailbox is not a paid API. SMTP/IMAP are in the Python stdlib. |
| **LinkedIn** | Scheduled as a **task**: the app writes the message, renders the merge tags, gives you a copy button and a link to the profile. You send it, then log the outcome in one click. | There is no free, legal LinkedIn send API. Automating the site risks the account. |
| **Cold call** | Scheduled as a **task**: script rendered with their details, a `tel:` click-to-dial link, one-click dispositions and notes. | Placing real calls needs a paid carrier. |

So email is automated end to end; LinkedIn and calls are *orchestrated* — the
tool decides who to touch, when, and with what, and records what happened. The
sequence advances the moment you log the outcome.

## The waterfall

A sequence is an ordered list of steps. Each step has a channel, a wait time, the
message, and a **gate**: the contact field it needs.

```
1. Email        day 0   needs email        →  auto-sent
2. LinkedIn     day 1   needs linkedin_url →  queued for you
3. Email        day 3   needs email        →  auto-sent
4. Call         day 4   needs phone        →  queued for you
5. LinkedIn     day 5   needs linkedin_url →  queued for you
6. Email        day 8   needs email        →  auto-sent
```

If a contact is missing what a step needs — no phone, no LinkedIn URL, no email —
that step is **skipped immediately** and the next one runs without waiting out its
delay. A lead with only a phone number drops straight to the call step; a lead with
only an email never sits in your call queue. That fall-through is the waterfall, and
it's counted in the reports so you can see how much data coverage is costing you.

Per step you can switch the gate to **stop the sequence** instead of skipping, and
you can turn off auto-send on an email step to review it in the queue before it goes.

A reply on *any* channel — an IMAP-detected email reply, a LinkedIn DM you log, a
callback you note — stops every running sequence for that person (when the campaign
has "stop on reply" set) and cancels their pending tasks.

## Day-to-day flow

1. **Contacts → Import CSV.** Any export works — Clay, Apollo, Sales Nav scrapes, a
   spreadsheet. Headers are auto-mapped (`Email Address` → email, `Mobile` → phone,
   `LinkedIn Profile` → linkedin_url); fix anything it got wrong on the mapping
   screen. Unmapped columns are kept as custom fields and become merge tags. Emails
   are lowercased, phones normalised, bare `linkedin.com/in/...` URLs fixed, and
   duplicates merged by email + LinkedIn URL.
2. **Sequences → Use starter waterfall**, then edit the copy. Merge tags:
   `{{first_name}}`, `{{company}}`, `{{title}}`, `{{signature}}`, `{{unsubscribe_url}}`,
   any custom CSV column, and `{{first_name|there}}` for a fallback. "Preview with a
   real contact" renders a step against a real row and warns about tags that would
   render blank.
3. **Campaigns.** Pick the sequence, set a daily email cap, sending hours and
   weekdays-only, then add contacts from a list or a filter. Start it.
4. **Today's queue.** Everything the scheduler assigned to a human. Call tasks show
   the script and dispositions; LinkedIn tasks show the message and a copy button.
   Mark done → the contact advances immediately.
5. **Master inbox.** One thread per person across all three channels. Reply by email,
   or log a LinkedIn reply / callback manually. Set status, opt people out.
6. **Reports.** Sent / open / reply rates, call dispositions, the step-by-step
   waterfall with skip counts, campaign comparison, CSV exports.

The scheduler runs every 20 seconds in the background. "Run scheduler" in the sidebar
forces a pass — useful when testing with zero-day delays.

## Going live with email

Settings → uncheck **Dry run** and fill in SMTP:

| | Gmail | Outlook / M365 |
|---|---|---|
| SMTP host | `smtp.gmail.com` | `smtp.office365.com` |
| Port / security | 587 / starttls | 587 / starttls |
| Password | [App password](https://myaccount.google.com/apppasswords) (2FA required) | account or app password |
| IMAP host | `imap.gmail.com` : 993 | `outlook.office365.com` : 993 |

Hit **Send test email** before starting a campaign. IMAP is optional but without it
replies won't stop sequences automatically — you'd log them by hand in the inbox.

Sane defaults for a personal mailbox: 30–50 sends/day, business hours, weekdays only,
and keep `{{unsubscribe_url}}` in the first email. Opt-outs and bounces are added to a
suppression list that every future send checks.

## Layout

```
outreach/
├── app.py          HTTP server, JSON API, CSV import/export, tracking pixel
├── engine.py       waterfall scheduler, task lifecycle, reply/bounce handling
├── mailer.py       SMTP send, IMAP reply capture, merge-tag rendering
├── db.py           SQLite schema and helpers
├── static/         index.html, app.js, styles.css (no build step, no CDN)
└── data/           outreach.db — your data, gitignored
```

Options: `--port 8000`, `--host 127.0.0.1`, `--open`, `--no-engine` (API only, no
background scheduler). `OUTREACH_DB=/path/to.db` points at a different database.

The database is a plain SQLite file — back it up by copying it, inspect it with
`sqlite3 outreach/data/outreach.db`.

## Limits worth knowing

- Bound to `127.0.0.1` with no authentication. It's a local tool; don't expose it.
- Open tracking only registers once the recipient loads images, and can't work in
  dry run (nothing is delivered).
- Reply detection matches inbound mail by the sender's address, so a reply from an
  alias won't auto-match — log it in the inbox instead.
- Sending volume is limited by your own mailbox's reputation and daily caps, not by
  this tool. It's built for a human-scale sending pace.
