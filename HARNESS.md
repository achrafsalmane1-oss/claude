# HARNESS — loop-engineer operator guide

This repo has the [loop-engineer](https://github.com/LeadGrowGTM/loop-engineer) five-agent
harness installed (source: `LeadGrowGTM/loop-engineer@c19bd5b`). It separates planning,
execution, live proof, verification, and shipping into isolated agents with structural
enforcement — not prompt trust.

## Core principle

The model that wrote the code is too generous grading its own homework. Self-eval is an
agreement loop, not an improvement loop. The fix is structural: **harness-checker** has
`tools: Read, Glob, Write` only — it cannot run Bash, spawn agents, or see the Maker's
reasoning. Nothing ships unless it passes, and a Checker PASS still doesn't ship anything:
shipping requires separate explicit approval.

## The 5-agent loop

```
Goal agent (depth 0)
  └── harness-planner (depth 1)  → BRIEF.md, PLAN.md, issues/NN-<slug>.md
  └── harness-maker   (depth 2)  → artifacts + PROGRESS.md (with proof)
  └── harness-prover  (depth 3)  → PROOF verdict (running-app goals only)
  └── harness-checker (depth 4)  → CYCLE_LOG.md (scores + verdict)
  └── harness-shipper (depth 1)  → after PASS + separate shipping approval → PR
       ↑ repeat until PASS or plateau (max 3 cycles)
```

| Agent | Tools | Role |
|---|---|---|
| `harness-planner` | Read, Glob, Write | Decomposes the goal into phases, writes BRIEF.md, PLAN.md, and durable `issues/` slices. Never executes work. |
| `harness-maker` | full tools | Executes phases, commits, appends proof to PROGRESS.md. |
| `harness-prover` | Read, Bash | Drives the live feature (CLI, API, UI) and returns a binary works/broken verdict. Skip for static-artifact goals. |
| `harness-checker` | Read, Glob, Write | Scores artifacts fresh against the rubric, cites `file:line` evidence for every score. Cannot grade its own homework — it wrote none of it. |
| `harness-shipper` | Read, Bash | Runs the ship pipeline exactly once, only after PASS + explicit shipping approval. Prepares a PR for human merge; never merges. |

Depth budget: goal=0, planner=1, maker=2, prover=3, checker=4, sub-skills max=5.

Agent definitions live in `.claude/agents/` (project-level, committed with this repo).
`harness-inbounds-checker` and `harness-novelty-checker` belong to the second goal path,
the benchmarking loop (`/benchmarking-loop` in `.claude/commands/`, engines in
`.claude/workflows/`).

## What's installed where

| Path | What |
|---|---|
| `.claude/agents/` | The 5 harness agents + 2 benchmarking checkers |
| `.claude/skills/write-goal-prompt/` | Goal authoring skill — the front door for build goals |
| `.claude/commands/benchmarking-loop.md` | Front door for metric-optimization goals |
| `.claude/workflows/` | Benchmark sweep/climb engines, red-team workflow |
| `.harness/skill-routing.md` | Task type → skill routing table (edit to tune for this repo) |
| `.harness/goals/<slug>/` | Working directory per goal: BRIEF, PLAN, issues/, PROGRESS, CYCLE_LOG, HANDOFF |
| `scripts/guard-protected-work.ts` | Protected-work guard (run with `bun`) |
| `.tasks.toml` | Project-scoped backlog → `.claude/backlog.md` |
| `treehouse.toml` | Project-scoped worktree pool (pool dir `.tmp/treehouse/` is gitignored) |

## Running a goal

1. **Author the goal** — invoke `/write-goal-prompt` and answer the clarity-gate grill.
   It produces a goal prompt plus a per-goal `HARNESS.md` under
   `.harness/goals/<slug>/` customized for the task (see template below).
2. **Readiness** — start from a clean tree on a non-default feature branch. Upstream's
   `prepare-harness-run.ps1` readiness check is PowerShell/Windows-oriented and was not
   copied here; in this environment, session-per-branch isolation covers the same need.
3. **Run the loop** — the goal agent invokes planner → maker → (prover) → checker in the
   current session. Only explicitly approved scope enters planning or execution; newly
   discovered scope waits for a new approval.
4. **Iterate** — ITERATE verdicts loop back to the maker (max 3 cycles, then PLATEAU).
5. **Ship** — after a Checker PASS **and** your separate explicit shipping approval, the
   shipper prepares the PR. It never merges; that's yours.

## Per-goal HARNESS.md sections

Each goal's `HARNESS.md` (written by the write-goal-prompt Harness Architect phase) carries:

- `PLANNER_BRIEF` — what to read first, phase table with real dependency ordering, turn budget
- `MAKER_ROUTING` — per-phase skill routing or `direct`, with expected artifacts
- `PROVER_BRIEF` — how to drive the live feature, or `N/A` for static-artifact goals
- `CHECKER_BRIEF` — the exact artifacts to evaluate, a 1–5 rubric per dimension, and the
  PASS threshold (default: mean ≥ 4.0/5.0 and no dimension < 3)
- `SHIP_BRIEF` — intent paragraph + decisions a reviewer can't infer from the diff
- `PROOF_PROTOCOL` — every phase completion needs pasted command output, not assertion
- `LOOP_TRACKER` — checkbox ledger of planner/cycles/verdict/ship state

## Proof protocol

Every phase completion requires actual command output, not assertion:

- "47 passed, 0 failed" — not "tests pass"
- "312 lines" — not "file written"
- "34 grep matches" — not "well-sourced"

Checker cites `file:line` evidence for every dimension score. Scores without citations
are invalid.

## First goal ideas for this repo

Point the harness at one goal. Candidates for the scraper:

- Add unit tests for `scraper.py` (title cycling, dedup, CSV output) — static-artifact
  goal, no Prover.
- Add a retry/backoff + rate-limit layer for the Apollo API — running-app goal, Prover
  drives the CLI against a mocked API.
- Benchmarking loop: maximize email-fill rate per Apollo credit spent — `/benchmarking-loop`
  with an instant, programmatic KPI.
