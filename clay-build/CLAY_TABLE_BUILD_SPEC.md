# Clay Table Build Spec — CPA Firm Outbound (Franklin Alliance model)

**Purpose:** Rebuild the client's Clay enrichment + qualification + routing table in your own Clay
workspace, with contacts sourced from **Clay directly** (not their HubSpot), and write qualified
leads **back into their HubSpot** at the end.

**Decisions locked:**
- Classification granularity: **all 5 messaging angles** (matches their copy library 1:1)
- Copy method: **route-to-template** (assign the matching pre-written sequence; only `{{firstName}}` personalizes)
- This document is the **build blueprint** — execute it column-by-column in Clay.

> **Two inputs still needed from you before this is 100% executable:**
> 1. The **"Is it an accounting firm?"** classifier prompt (full text).
> 2. The **"Gate status"** prompt (full text).
> Slots for both are reserved below (Columns 8 and 9). Paste them and I'll port them verbatim.

---

## 0. The three jobs this table does

Keep these mentally separate — different failure modes:

1. **Resolve & enrich** — name → domain → normalized domain/URL → industry, description, headcount, address
2. **Qualify (two gates)** — (a) Is it an accounting firm? (b) Gate status: does a human need to review before send?
3. **Route & write back** — pick the messaging angle → attach the matching template → push to HubSpot

The **only** structural difference from the client's table is the front door: they ingest from HubSpot,
you ingest from Clay. Everything downstream is identical.

---

## 1. Column-by-column build

Build in this order. "Type" = the kind of Clay column.

| # | Column | Type | Detail |
|---|--------|------|--------|
| 1 | `company_name` | Source | Clay import / Find Companies. Your front door. |
| 2 | `domain` | Enrich | Clay "Find Company" → domain. |
| 3 | `normalized_domain` | Formula | Lowercase, strip `http(s)://`, `www.`, trailing slash, path. (formula below) |
| 4 | `normalized_url` | Formula | `https://` + `normalized_domain`. |
| 5 | `industry` | Enrich | Clay company enrichment. |
| 6 | `company_description` | Enrich/AI | Clay description, or AI summary of the homepage. |
| 7 | `employee_count` | Enrich | LinkedIn headcount. **Also a classifier signal (see §3).** |
| 8 | `address` / `country` / `state` | Enrich | Clay HQ location. |
| 9 | `is_accounting_firm` (+ `confidence` + `reasoning` + `evidence_url`) | AI (their prompt) | **PASTE PROMPT.** Gate 0. |
| 10 | `gate_status` (`REQUIRED` / `CLEAR`) | AI (their prompt) | **PASTE PROMPT.** Human-review flag. |
| 11 | `n_partners` | Enrich/AI | Count partners/owners from team page or LinkedIn. Classifier signal. |
| 12 | `leadership_tenure_years` | Enrich/AI | Years since founder/lead partner started. Classifier signal. |
| 13 | `messaging_angle` (+ `confidence` + `reasoning`) | AI | **NEW — the routing column. Prompt in §3.** |
| 14 | `campaign_template` | Lookup | Maps angle → template + Lemlist campaign ID (§4). |
| 15 | `ready_to_load` | Formula | TRUE only if all gates pass (§5). |
| 16 | HubSpot write-back | Integration | Maps to their `ai_*` properties (§6). |

### Normalization formula (Column 3)

```
lower(
  replace(
    replace(
      replace(
        replace({{domain}}, "https://", ""),
      "http://", ""),
    "www.", ""),
  "/", "")
)
```
Adjust to Clay's formula syntax; the logic is: lowercase → drop protocol → drop `www.` → drop trailing slash/path.

---

## 2. Gate sequence (the qualification spine)

Run gates in order; a fail short-circuits downstream cost.

```
Gate 0  is_accounting_firm == "No"           → STOP (disqualify, don't enrich further)
Gate 1  gate_status == "REQUIRED"            → HOLD for human review (don't auto-load)
Gate 2  messaging_angle assigned + confidence → route to template
        ↓
        ready_to_load == TRUE → write to HubSpot + (optionally) load to Lemlist
```

Order matters for credits: don't run partner-count / tenure / angle enrichments on rows that already
failed Gate 0.

---

## 3. The classification column (Column 13) — the new piece

This is the column that makes the table worth building. It mirrors the **same output shape as the
accounting-firm classifier**: a label + confidence + reasoning.

### Inputs the prompt reads
- `company_description`
- `employee_count`
- `n_partners`
- `leadership_tenure_years`
- `industry`
- (optionally) homepage / about-page text

### The 5 angles and their signals

| Angle | Opportunity ID | Trigger signals |
|-------|---------------|-----------------|
| **SUCCESSION** | AGING_PARTNER_LIQUIDITY | Solo/co-founder, 20+ yr tenure, name on the door, no visible successor |
| **SUCCESSION_PLANNING** | (transition) | Founder actively stepping back, transition in progress, some bench |
| **EQUITY_PATHWAY** | RISING_LEADER | Multi-partner, rising leaders/managers present, retention is the risk |
| **GROWTH_INFRASTRUCTURE** | (scaling) | Actively scaling, hiring, acquiring, growth-mode signals |
| **EXPLORATORY** | NO_VISIBLE | Weak/mixed signals — **default fallback so nothing is mis-routed** |

### Prompt scaffold (fill against their DOC2 liquidity framework once you share it)

```
You are the messaging-angle classifier for [YOUR CLIENT].
Given a CPA/accounting firm's profile, assign exactly ONE messaging angle.

Inputs:
- Description: {{company_description}}
- Employees: {{employee_count}}
- Partners: {{n_partners}}
- Lead partner tenure (yrs): {{leadership_tenure_years}}
- Industry: {{industry}}

Angles (choose one):
1. SUCCESSION — solo/co-founder, 20+ yr tenure, no visible successor.
2. SUCCESSION_PLANNING — founder stepping back, transition underway, some bench depth.
3. EQUITY_PATHWAY — multi-partner, rising leaders who need an ownership path to stay.
4. GROWTH_INFRASTRUCTURE — actively scaling/acquiring, growth-mode.
5. EXPLORATORY — signals weak or mixed. USE THIS WHEN UNSURE. Do not guess.

Output JSON:
{ "messaging_angle": "...", "confidence": "high|medium|low", "reasoning": "1-2 sentences citing the signals" }
```

> Tuning note: bias toward **EXPLORATORY** on low confidence rather than forcing a high-intent angle.
> A mis-routed SUCCESSION email to a growth-mode firm reads worse than a neutral educational one.

---

## 4. Angle → template → campaign mapping (Column 14)

Route-to-template lookup. Only `{{firstName}}` personalizes — the body is the client's approved copy.

| `messaging_angle` | Template file | Lemlist campaign | ID |
|-------------------|--------------|------------------|----|
| SUCCESSION | `Campaign_1_SUCCESSION_Template.md` | SUCCESSION | `cam_GiinEna3h4Wac9rjt` |
| EQUITY_PATHWAY | `Campaign_2_EQUITY_PATHWAY_Template.md` | EQUITY_PATHWAY | `cam_uBj54uazGcpjaiHqv` |
| SUCCESSION_PLANNING | `Campaign_3_SUCCESSION_PLANNING_Template.md` | SUCCESSION_PLANNING | `cam_fwg3Zir6xMpBkeuxL` |
| GROWTH_INFRASTRUCTURE | `Campaign_4_GROWTH_INFRASTRUCTURE_Template.md` | GROWTH_INFRASTRUCTURE | `cam_NNRcdCc5GHQyCRnRX` |
| EXPLORATORY | `Campaign_5_EXPLORATORY_Template.md` | EXPLORATORY | `cam_YrFxCyToGNa5amZAP` |

> IDs are from the client's README. **Confirm they still match your own Lemlist workspace** — if you're
> running campaigns in your own seat, you'll create your own campaigns and swap these IDs.

---

## 5. `ready_to_load` formula (Column 15)

```
is_accounting_firm == "Yes"
AND gate_status == "CLEAR"
AND messaging_angle is not empty
AND messaging_angle confidence != "low"   // optional stricter gate
AND email is verified / present
```
Only TRUE rows write to HubSpot as load-ready. REQUIRED / low-confidence rows stay flagged for manual review.

---

## 6. HubSpot write-back mapping (Column 16)

The client exposes 8 custom AI properties (`HubSpot_AI_Properties_Reference.txt`). Map your columns to them:

| Clay column | HubSpot property |
|-------------|------------------|
| `messaging_angle` | `ai_messaging_angle` |
| Opportunity ID (from §3 table) | `ai_opportunity_id` |
| angle `confidence` | `ai_confidence` |
| (TRUE on write) | `ai_scored` |
| send date | `ai_scored_date` |
| `gate_status` | `ai_gate_status` |
| batch label | `ai_batch` |
| `reasoning` / research summary | `ai_research_summary` |

> **Decide with the client:** do you write into *their* HubSpot via a shared connection/API key, or stage
> in your own and hand off? That's an access/ownership question, not a technical one — confirm before wiring.

---

## 7. Build order checklist

- [ ] Columns 1–8: resolve & enrich spine
- [ ] Column 9: paste + port accounting-firm classifier (Gate 0)
- [ ] Column 10: paste + port gate-status prompt (Gate 1)
- [ ] Columns 11–12: partner count + tenure signals
- [ ] Column 13: messaging-angle classifier (§3)
- [ ] Column 14: angle → template/campaign lookup (§4)
- [ ] Column 15: `ready_to_load` formula
- [ ] Column 16: HubSpot write-back + field mapping (§6)
- [ ] Test on 5–10 known firms from the client's existing data (Campaign 1 & 2 firms are labeled — use them as ground truth)
- [ ] Validate classifier output against their known assignments before scaling

---

## 8. Open items / decisions

1. **The two prompts** (accounting-firm + gate-status) — needed to finalize Columns 9–10.
2. **Lemlist campaign IDs** — reuse client's or create your own.
3. **HubSpot access model** — write to their portal or stage and hand off.
4. **Confidence threshold** for auto-load vs. human review (currently "exclude low").
5. **Copy method is route-to-template today** — if you later want personalized openers, that's a separate
   AI column added on top; the templates become the style guide. Not in this build.
