# Working agreements

## Always ask before spending credits

Never run anything that consumes Clay credits or plan allowance without first
showing the estimated cost and the remaining balance, then waiting for explicit
approval. This applies even when it seems obviously helpful or is a small amount.

Requires approval first:

- Running any routine or enrichment (work email, phone, firmographics, tech stack)
- Running or testing a workflow
- Any Clay search — results count against the plan allowance whether or not
  they are later enriched

Free, no approval needed:

- Workspace reads: counts, fill rates, id enumeration, field values
- Cost estimates (`clay routines get <id>`) and balance checks (`clay credits`)
- Listing routines and the action catalog
- Building, editing, validating, and diagramming workflows without running them
- Reading and exporting existing tables

Check cost with `clay routines get <id>` (`estimatedCreditCost`) against
`clay credits` before proposing any run.

## Credit balances

Clay bills two separate balances. Data credits are the scarce one — that is what
enrichment and paid providers draw down. Action executions are effectively
unlimited on this workspace, so deterministic code nodes, filtering, and routing
can run at volume without touching data credits.
