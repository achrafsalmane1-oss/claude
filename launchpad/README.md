# launchpad — economic core

Model layer for an equity-linked token launchpad. Framework-free ESM, no
runtime dependencies, `node --test`.

## Why this exists first

Everything downstream — the Solana programs, the backend preflight, the launch
wizard copy — is a rendering of these numbers. Getting the model right before
writing Rust means design errors are caught in a test run rather than in an
audit or, worse, on mainnet.

## Validation approach

The suite is calibrated against Star's published Micro tier rather than against
our own assumptions. Given only founder proceeds ($10K) and the entity cost
($7.5K), the solver reproduces their allocation to within 0.5%:

| | derived | Star published |
|---|---|---|
| Curve inventory | 507.9M | 507.9M |
| Liquidity tokens | 92.1M | 92.1M |
| Graduation threshold | $35,003 | $35,000 |

This confirms the curve is constant-product with virtual reserves, and that
liquidity is the residual quote after the founder and entity are paid, valued
at graduation price.

## Modules

- `model/curve.mjs` — constant-product curve with virtual reserves. Calibrates
  from target market caps rather than hand-tuned reserves, so tiers are
  designable. Includes `priceImpact`, which no launchpad currently surfaces.
- `model/allocation.mjs` — solves a tier from founder proceeds. Toggleable
  reserves return supply to the float rather than being burned. `auditTier`
  asserts conservation of both supply and quote.

## Tier economics

Founder share of buyer money rises with tier size, because the $7.5K entity
cost is fixed:

| Tier | Founder gets | Buyers pay | Founder share |
|---|---|---|---|
| Micro | $10K | $35.0K | 28.6% |
| Standard | $25K | $65.2K | 38.3% |
| Pro | $50K | $115.2K | 43.4% |

Micro is the worst deal for a founder. Worth surfacing in the wizard.
