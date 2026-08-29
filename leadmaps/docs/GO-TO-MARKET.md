# Go to market

The product is built. This is the commercial reasoning behind it and what to do
in the first weeks. Treat the numbers as starting hypotheses, not forecasts.

## Who this is for

Not "anyone who needs leads". The buyers who convert on a tool like this are
people whose *job* is contacting local businesses:

| Segment | Why they buy | Where they are |
|---|---|---|
| Digital agencies selling to local businesses | Need a fresh prospect list per service area and vertical | Agency Facebook groups, r/agency, LinkedIn |
| SDR / outbound teams with a local ICP | Top-of-funnel volume, filtered by category and rating | LinkedIn, RevGenius, Pavilion |
| Field sales & franchise development | Territory lists with coordinates | Industry associations |
| Data resellers / platforms | Embed lead data via the API | Cold outreach, marketplaces |

The sharpest wedge is the first row. Agencies buy tools monthly, decide fast,
and talk to each other.

## Why the pricing is shaped this way

- **Metered by lead delivered, sold as a flat plan.** Customers hate per-lead
  meters that make every search a decision; you need cost control because
  scraping burns real compute. A flat plan with an allowance gives both.
- **$49 entry.** Below the threshold where an agency owner needs approval.
- **$149 is the target.** It is the featured plan, and email enrichment is the
  gate — that is the feature people actually upgrade for.
- **Annual is deliberately absent.** Do not sell annual plans until retention
  past month three is proven. Selling a year of a product nobody has stuck with
  is buying refund liability.

Check your unit economics before launch: measure what one search of typical
depth costs you in worker time and proxy traffic, multiply by the plan
allowance, and confirm the worst case (a customer who uses 100% of their
allowance) still leaves margin. If it does not, cut the allowance, not the
price — allowances are easier to change later than headline prices.

## First 30 days

**Week 1 — prove it works, on you.**
Run the searches you would sell. Twenty real lists in your own target verticals.
If the data is not good enough for you to sell from, it is not good enough to
charge for. Fix the engine (proxies, depth, worker count) before marketing.

**Week 2 — ten design partners.**
Not a launch. Hand-pick ten agencies, give them Growth free for a month, and ask
one question a week. What you want is the sentence they use to describe the
product to someone else — that sentence becomes your headline.

**Week 3 — one channel, done properly.**
Pick the channel where your buyers already complain about lead lists. For
agencies that is a handful of Facebook and Slack groups. Post the thing itself:
a real list for a real vertical, free, with the tool named once. Do not spread
across five channels.

**Week 4 — turn on payment.**
Convert the design partners first, at a founding price you honour forever. Ten
paying customers at $149 is $1,490 MRR and, more importantly, ten reference
calls.

## What to say

The headline that works is not "Google Maps scraper" — that is a category with
free competitors and a whiff of grey-hat. It is the outcome:

> Every business on Google Maps, as a clean lead list.

Lead with the fields, because that is what makes a list usable: name, category,
address, phone, website, rating, review count, coordinates, and email. The
rating and review count matter more than people expect — they are how a good
SDR qualifies a local business before dialling.

## Objections you will actually get

**"Is this legal?"** You collect publicly listed business information. The
customer's *use* of it is what carries obligations — GDPR/PECR in the UK and EU,
CAN-SPAM in the US. Say that plainly, point at `/terms`, and do not oversell it.
Being straight about this closes more deals than dodging it.

**"How is this different from Apollo/ZoomInfo?"** Different data. Those are
built on company and B2B contact databases; local businesses are thin in them.
You have the plumber with 40 reviews and no LinkedIn presence.

**"Can I get emails?"** Yes, on Growth and above, crawled from the business
website. Be honest that coverage is partial — a lot of local businesses only
publish a contact form. Overpromising here generates refunds.

**"What if I need more than 100,000?"** That is a conversation, not a plan
button. The pricing page says so.

## Instrument these four things

Everything else is vanity:

1. **Signup → first completed search.** If someone signs up and never runs a
   search, your dashboard failed, not your marketing.
2. **First search → second search.** The single best predictor of conversion.
3. **Trial → paid.**
4. **Month-1 → month-3 retention.** Below ~70% you have a churn problem no
   amount of top-of-funnel will fix — do not scale spend until it is fixed.

## What to build next, in order

1. **Scheduled recurring searches.** "Re-run this list monthly." This is the
   single strongest retention feature for this product — it turns a tool into a
   subscription.
2. **Deduplication across searches.** Customers running overlapping areas get
   the same business repeatedly and it makes the data feel cheap.
3. **CRM push** (HubSpot, Pipedrive). Removes the CSV round-trip.
4. **Team seats in the UI.** The plans already carry seat limits; the invite
   flow is not built.
5. **Annual billing** — only once month-3 retention is proven.

Resist building all four at once. Ship the scheduler.
