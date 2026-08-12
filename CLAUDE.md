# Philippines Founders Scraper

Python CLI that scrapes founders/CEOs of Philippines-based companies (10–500 employees) from Apollo.io (primary) and Hunter.io (email enrichment), and writes a CSV with first name, last name, company, and email.

## Repo Map

| Path | What |
|---|---|
| `scraper.py` | The entire scraper — Apollo search, Hunter enrichment, CSV output |
| `.env.example` | API key template (`APOLLO_API_KEY` required, `HUNTER_API_KEY` optional) |
| `requirements.txt` | Python deps (`requests`, `python-dotenv`) |
| `HARNESS.md` | Operator guide for the loop-engineer harness installed in this repo |
| `.claude/agents/` | Harness agents: planner, maker, prover, checker, shipper (+ benchmarking checkers) |
| `.claude/skills/write-goal-prompt/` | Goal-prompt authoring skill (entry point for harness goals) |
| `.harness/` | Skill routing + per-goal working directories (`.harness/goals/<slug>/`) |

## Running

```bash
pip install -r requirements.txt
cp .env.example .env   # add APOLLO_API_KEY
python3 scraper.py --target 5000 --output output/ph_founders.csv
```

Output lands in `output/` (gitignored). Never commit `.env` or CSV output.

## Harness
Installed: 2026-08-12. Source: LeadGrowGTM/loop-engineer@c19bd5b.
Routing: `.harness/skill-routing.md`. Goals: `.harness/goals/<slug>/`. Backlog: `.tasks.toml` → `.claude/backlog.md` (project-scoped). Worktrees: `treehouse.toml` (project-scoped). Readiness: start from a clean tree on a non-default feature branch before goal work. Agents: project-level (`.claude/agents/`, committed with this repo). Operator guide: `HARNESS.md`.
