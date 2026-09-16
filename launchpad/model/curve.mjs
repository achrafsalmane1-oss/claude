/**
 * Constant-product bonding curve with virtual reserves.
 *
 * Price is quote-per-token = x / y, where x is the quote reserve and y the
 * token reserve. Both start as virtual (no real deposits); buyers move along
 * the curve by adding quote and removing tokens, holding x * y = k.
 *
 * Calibration is the inverse problem: given the market caps a launch should
 * start and graduate at, and how many tokens the curve is allowed to sell,
 * derive the virtual reserves. Deriving them (rather than picking reserves and
 * seeing where they land) is what makes tiers designable — you state the
 * economics you want and the curve follows.
 */

/** Market cap is always priced off total supply, including unsold reserves. */
export const priceFromMarketCap = (marketCap, totalSupply) => marketCap / totalSupply;
export const marketCapFromPrice = (price, totalSupply) => price * totalSupply;

/**
 * Derive virtual reserves from the economics a tier is supposed to produce.
 *
 * Holding k constant across the whole sale gives p0*y0^2 = p1*(y0-inventory)^2,
 * which solves to a closed form for y0. No search, no tuning constants.
 */
export function calibrate({ totalSupply, startMarketCap, graduationMarketCap, curveInventory }) {
  if (!(totalSupply > 0)) throw new RangeError('totalSupply must be positive');
  if (!(curveInventory > 0)) throw new RangeError('curveInventory must be positive');
  if (!(startMarketCap > 0)) throw new RangeError('startMarketCap must be positive');
  if (graduationMarketCap <= startMarketCap) {
    throw new RangeError('graduationMarketCap must exceed startMarketCap');
  }
  if (curveInventory > totalSupply) {
    throw new RangeError('curveInventory cannot exceed totalSupply');
  }

  const startPrice = priceFromMarketCap(startMarketCap, totalSupply);
  const graduationPrice = priceFromMarketCap(graduationMarketCap, totalSupply);

  const rootStart = Math.sqrt(startPrice);
  const rootGraduation = Math.sqrt(graduationPrice);

  // y0 = inventory * sqrt(p1) / (sqrt(p1) - sqrt(p0))
  const virtualTokenReserve = (curveInventory * rootGraduation) / (rootGraduation - rootStart);
  const virtualQuoteReserve = startPrice * virtualTokenReserve;

  const endTokenReserve = virtualTokenReserve - curveInventory;
  const endQuoteReserve = graduationPrice * endTokenReserve;

  return {
    virtualTokenReserve,
    virtualQuoteReserve,
    invariant: virtualQuoteReserve * virtualTokenReserve,
    startPrice,
    graduationPrice,
    /** Quote raised across the full sale — the graduation threshold. */
    raiseTarget: endQuoteReserve - virtualQuoteReserve,
    /** Blended price across the sale. Always well below the midpoint: the
     *  curve is convex, so early buyers get most of the discount. */
    averagePrice: (endQuoteReserve - virtualQuoteReserve) / curveInventory,
    priceMultiple: graduationPrice / startPrice,
  };
}

/** Reserve state after `tokensSold` tokens have left the curve. */
export function stateAt(curve, tokensSold) {
  const { virtualTokenReserve, invariant } = curve;
  if (tokensSold < 0) throw new RangeError('tokensSold cannot be negative');
  const tokenReserve = virtualTokenReserve - tokensSold;
  if (tokenReserve <= 0) throw new RangeError('tokensSold exceeds curve capacity');
  const quoteReserve = invariant / tokenReserve;
  return {
    tokenReserve,
    quoteReserve,
    price: quoteReserve / tokenReserve,
    quoteRaised: quoteReserve - curve.virtualQuoteReserve,
  };
}

/** Quote cost to buy `tokenAmount` more tokens from `tokensSold`. Excludes fees. */
export function costToBuy(curve, tokensSold, tokenAmount) {
  const before = stateAt(curve, tokensSold);
  const after = stateAt(curve, tokensSold + tokenAmount);
  return after.quoteReserve - before.quoteReserve;
}

/** Tokens received for `quoteAmount` at position `tokensSold`. Excludes fees. */
export function tokensForQuote(curve, tokensSold, quoteAmount) {
  const before = stateAt(curve, tokensSold);
  const quoteReserve = before.quoteReserve + quoteAmount;
  const tokenReserve = curve.invariant / quoteReserve;
  return before.tokenReserve - tokenReserve;
}

/**
 * Effective price paid vs. the quoted spot price before the trade.
 *
 * This is the number a buyer actually feels and no launchpad surfaces. On a
 * thin curve a modest buy can clear several percent above the displayed price.
 */
export function priceImpact(curve, tokensSold, quoteAmount) {
  const spot = stateAt(curve, tokensSold).price;
  const tokens = tokensForQuote(curve, tokensSold, quoteAmount);
  const effective = quoteAmount / tokens;
  return { spot, effective, impactPct: (effective / spot - 1) * 100, tokens };
}
