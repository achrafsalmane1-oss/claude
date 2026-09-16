/**
 * Supply allocation and tier solving.
 *
 * A tier is defined by what the founder should walk away with, not by token
 * counts. Everything else — how many tokens the curve sells, how many seed the
 * pool, what the graduation threshold is — falls out of that. Token counts are
 * an output of the design, which is why reserves can be toggled without
 * redesigning the tier: unreserved tokens simply return to the float.
 *
 * The closing condition is that the float is fully consumed:
 *
 *     curveInventory + liquidityTokens === float
 *
 * where liquidityTokens is whatever quote is left after the founder and the
 * entity are paid, valued at the graduation price. Raise depends on inventory
 * and inventory depends on raise, so this is solved rather than computed.
 */

import { calibrate, priceFromMarketCap } from './curve.mjs';

/** Fixed reserves as a fraction of total supply. Toggleable ones are flagged. */
export const DEFAULT_RESERVES = {
  founderLock: { fraction: 0.20, toggleable: false, label: 'Founder & team lock' },
  compensation: { fraction: 0.15, toggleable: true, label: 'Team compensation' },
  launchRewards: { fraction: 0.05, toggleable: true, label: 'Launch rewards' },
};

/**
 * Tokens held back from the float, given which toggleable reserves are on.
 * Anything switched off is not burned — it widens the float, so the public
 * simply buys more supply for the same money.
 */
export function resolveReserves(totalSupply, { compensation = true, launchRewards = true } = {}, table = DEFAULT_RESERVES) {
  const enabled = { founderLock: true, compensation, launchRewards };
  const reserves = {};
  let reserved = 0;

  for (const [key, spec] of Object.entries(table)) {
    const on = spec.toggleable ? enabled[key] !== false : true;
    const tokens = on ? spec.fraction * totalSupply : 0;
    reserves[key] = { ...spec, enabled: on, tokens };
    reserved += tokens;
  }

  return { reserves, reserved, float: totalSupply - reserved };
}

/**
 * Solve for the curve inventory that makes a tier balance.
 *
 * Both sides of the closing condition move with inventory, but the residual is
 * strictly increasing in it, so bisection converges without needing a good
 * starting guess.
 */
export function solveTier({
  totalSupply,
  startMarketCap,
  graduationMarketCap,
  founderProceeds,
  entityCost,
  toggles = {},
  reserveTable = DEFAULT_RESERVES,
  tolerance = 1,
  maxIterations = 200,
}) {
  const { reserves, float } = resolveReserves(totalSupply, toggles, reserveTable);
  const graduationPrice = priceFromMarketCap(graduationMarketCap, totalSupply);
  const founderSide = founderProceeds + entityCost;

  // Residual is negative when inventory is too small to fill the float.
  const residual = (curveInventory) => {
    const curve = calibrate({ totalSupply, startMarketCap, graduationMarketCap, curveInventory });
    const liquidityQuote = curve.raiseTarget - founderSide;
    const liquidityTokens = liquidityQuote / graduationPrice;
    return { curve, liquidityQuote, liquidityTokens, gap: curveInventory + liquidityTokens - float };
  };

  let low = 1;
  let high = float;
  let result = residual(high);

  if (result.gap < 0) {
    throw new RangeError(
      'Tier cannot close: even selling the entire float does not cover founder proceeds plus entity cost. ' +
      'Raise the graduation market cap or lower the target proceeds.'
    );
  }

  for (let i = 0; i < maxIterations; i += 1) {
    const mid = (low + high) / 2;
    result = residual(mid);
    if (Math.abs(result.gap) < tolerance) break;
    if (result.gap > 0) high = mid; else low = mid;
  }

  const curveInventory = (low + high) / 2;
  const { curve, liquidityQuote, liquidityTokens } = residual(curveInventory);

  if (liquidityQuote <= 0) {
    throw new RangeError('Tier leaves no quote for liquidity; the pool would be unbacked.');
  }

  return {
    totalSupply,
    curve,
    allocation: {
      curveInventory,
      liquidityTokens,
      ...Object.fromEntries(Object.entries(reserves).map(([k, v]) => [k, v.tokens])),
    },
    reserves,
    proceeds: {
      raiseTarget: curve.raiseTarget,
      founderProceeds,
      entityCost,
      liquidityQuote,
      /** Share of buyer money that reaches the founder. Deliberately surfaced:
       *  it is the single most misread number on every launchpad. */
      founderShareOfRaise: founderProceeds / curve.raiseTarget,
    },
    graduationPrice,
  };
}

/** Verify a solved tier actually conserves supply and quote. */
export function auditTier(tier) {
  const allocated = Object.values(tier.allocation).reduce((a, b) => a + b, 0);
  const quoteOut = tier.proceeds.founderProceeds + tier.proceeds.entityCost + tier.proceeds.liquidityQuote;
  return {
    supplyBalanced: Math.abs(allocated - tier.totalSupply) < 1,
    quoteBalanced: Math.abs(quoteOut - tier.proceeds.raiseTarget) < 0.01,
    supplyDrift: allocated - tier.totalSupply,
    quoteDrift: quoteOut - tier.proceeds.raiseTarget,
  };
}
