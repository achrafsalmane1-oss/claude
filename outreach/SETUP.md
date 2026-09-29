# Start here

This is a cold outreach tool that runs **on your own computer**. Nothing is hosted,
there's no account to create, no subscription, and no company in the middle — your
leads and your inbox stay on your machine.

## 1. Start it

**Mac** — double-click `start-mac.command`.
The first time, macOS may say it can't verify the developer: **right-click** the file
→ **Open** → **Open** again. You only do that once.

**Windows** — double-click `start-windows.bat`.
If a blue "Windows protected your PC" box appears: **More info** → **Run anyway**.

A black terminal window opens and your browser goes to `http://127.0.0.1:8000`.
**Leave the terminal window open while you work** — that window *is* the app.
Closing it stops everything. To stop on purpose, just close it.

If it says Python isn't installed: get it from [python.org/downloads](https://www.python.org/downloads/).
On Windows, tick **"Add python.exe to PATH"** on the first install screen. Then
double-click the start file again.

## 2. Try it without sending anything

It starts in **DRY RUN** (you'll see the orange badge, bottom-left). Everything works —
sequences run, tasks appear, the inbox fills — but no email actually leaves your
computer. Play with it in this mode first.

1. **Contacts → Import CSV → Load sample data → Continue → Import contacts.**
   Five fake leads with deliberate gaps: one has no email, one has no phone.
2. **Sequences → Use starter waterfall.** Six steps, already written. Close it.
3. **Campaigns → New campaign.** Pick the starter sequence. Set "Send from" to `0` and
   "Send until" to `24`, untick weekdays-only (so it runs right now while you test).
   Save → pick the sample list → Add to campaign.
4. Hit **Start**, then **Run scheduler** in the bottom-left corner.
5. **Today's queue** — the lead with no email has already dropped to the LinkedIn step.
   That's the waterfall working.
6. **Master inbox** and **Reports** now have data in them.

When you've finished playing: **Contacts → select all → Delete**, and delete the test
campaign. Or just delete the `data` folder to wipe everything and start clean.

## 3. Import your real leads

**Contacts → Import CSV.** Any export works — Clay, Apollo, Sales Nav, a spreadsheet.
Column names are matched automatically (`Email Address`, `Mobile`, `LinkedIn Profile`
and so on); fix anything it got wrong on the mapping screen.

Columns it doesn't recognise are kept and become personalisation tags. If your CSV has
a `Recent Funding` column, you can write `{{recent_funding}}` in an email and it fills
in per person. Duplicates are merged automatically.

## 4. Connect your email (when you're ready to send for real)

Until you do this, nothing sends. **Settings**, then:

**Gmail**
1. Your Google account needs 2-step verification turned on.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
   create a password called "Outreach", copy the 16 characters.
3. In Settings: SMTP host `smtp.gmail.com`, port `587`, security `starttls`,
   username = your Gmail address, password = that 16-character app password.
4. For replies to show up in the inbox: IMAP host `imap.gmail.com`, port `993`, same
   username and app password.
5. Fill in **From name** and **From email**, write a **Signature**.
6. Click **Send test email**. Check it arrived.
7. Untick **Dry run**. Save. The badge turns green: LIVE SENDING.

**Outlook / Microsoft 365** — same thing with `smtp.office365.com` (587) and
`outlook.office365.com` (993).

Your password is stored in the app's local database file on your own machine and is
never shown back in the browser.

## 5. How to actually use it day to day

**Morning:** open **Today's queue**. It's your call list and LinkedIn list for the day —
the app decided who, when, and what to say. For each one: dial the number or open the
profile, do the thing, click the outcome. The lead moves to their next step instantly.

**Then:** open **Master inbox**. Every reply, on any channel, one thread per person.
Email replies appear on their own. LinkedIn replies and callbacks you log with
**"Log their reply"** — that stops their sequence so nobody gets a follow-up after
they've already answered you.

**Weekly:** **Reports**. The step-by-step table is the useful one: "skipped" tells you
how many people you couldn't reach on a channel because the data wasn't in your CSV.

### Things worth knowing

- **Email sends by itself. LinkedIn and calls don't** — no tool can do those for free
  or safely, so the app schedules them, writes the message, and hands it to you with a
  copy button. You send it, you log it, it moves on.
- **The app only runs while that terminal window is open.** Nothing sends overnight if
  your laptop is closed — it picks up where it left off when you start it again.
- **Start slow on a new mailbox.** 30–50 emails a day, business hours, weekdays. The
  daily cap is set per campaign. Blasting from a personal Gmail gets it flagged.
- **Keep `{{unsubscribe_url}}` in your first email.** Anyone who clicks it is
  suppressed from everything, permanently.
- **Your data lives in the `data` folder.** Back it up by copying that folder.
