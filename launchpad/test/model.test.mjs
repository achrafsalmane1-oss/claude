import test from 'node:test';
import assert from 'node:assert/strict';

import { calibrate, stateAt, tokensForQuote, priceImpact } from '../model/curve.mjs';
import { solveTier, auditTier, resolveReserves } from '../model/allocation.mjs';

/**
 * Star's published Micro tier, used as a fixture.
 *
 * These figures were read off their launch UI. If the model reproduces them
 * from founder proceeds alone, the engine matches a launchpad already holding
 * real money — which is a far stronger check than any self-consistent test we
 * could write against our own assumptions.
 */
const STAR_MICRO = {
  totalSupply: 1e9,
  startMarketCap: 25_000,
  graduationMarketCap: 190_000,
  founderProceeds: 10_000,
  entityCost: 7_500,
  published: {
    curveInventory: 507.9e6,
    liquidityTokens: 92.1e6,
    founderLock: 200e6,
    compensation: 150e6,
    launchRewards: 50e6,
    raiseTarget: 35_000,
  },
};

const withinPct = (actual, expected, pct) =>
  Math.abs(actual - expected) / expected <= pct / 100;

test('curve calibration reproduces Star Micro reserves', () => {
  const curve = calibrate({
    totalSupply: STAR_MICRO.totalSupply,
    startMarketCap: STAR_MICRO.startMarketCap,
    graduationMarketCap: STAR_MICRO.graduationMarketCap,
    curveInventory: STAR_MICRO.published.curveInventory,
  });

  assert.ok(withinPct(curve.raiseTarget, 35_000, 0.5), `raise ${curve.raiseTarget}`);
  assert.ok(withinPct(curve.priceMultiple, 7.6, 0.1), `multiple ${curve.priceMultiple}`);
  assert.equal(curve.startPrice, 0.000025);
  assert.equal(curve.graduationPrice, 0.00019);
});

test('invariant holds across the whole sale', () => {
  const curve = calibrate({
    totalSupply: 1e9,
    startMarketCap: 25_000,
    graduationMarketCap: 190_000,
    curveInventory: 507.9e6,
  });

  for (const sold of [0, 1e6, 100e6, 300e6, 507.9e6]) {
    const s = stateAt(curve, sold);
    assert.ok(withinPct(s.quoteReserve * s.tokenReserve, curve.invariant, 0.0001));
  }
});

test('price rises monotonically and ends at graduation price', () => {
  const curve = calibrate({
    totalSupply: 1e9,
    startMarketCap: 25_000,
    graduationMarketCap: 190_000,
    curveInventory: 507.9e6,
  });

  let previous = 0;
  for (let sold = 0; sold <= 507.9e6; sold += 25e6) {
    const { price } = stateAt(curve, sold);
    assert.ok(price > previous, `price fell at ${sold}`);
    previous = price;
  }
  assert.ok(withinPct(stateAt(curve, 507.9e6).price, 0.00019, 0.01));
});

test('solves Star Micro from founder proceeds alone', () => {
  const tier = solveTier(STAR_MICRO);
  const { published } = STAR_MICRO;

  assert.ok(
    withinPct(tier.allocation.curveInventory, published.curveInventory, 0.5),
    `curve inventory ${Math.round(tier.allocation.curveInventory).toLocaleString()}`
  );
  assert.ok(
    withinPct(tier.allocation.liquidityTokens, published.liquidityTokens, 2),
    `liquidity ${Math.round(tier.allocation.liquidityTokens).toLocaleString()}`
  );
  assert.ok(withinPct(tier.proceeds.raiseTarget, published.raiseTarget, 0.5));

  assert.equal(tier.allocation.founderLock, published.founderLock);
  assert.equal(tier.allocation.compensation, published.compensation);
  assert.equal(tier.allocation.launchRewards, published.launchRewards);
});

test('solved tiers conserve supply and quote exactly', () => {
  for (const mcaps of [
    { startMarketCap: 25_000, graduationMarketCap: 190_000, founderProceeds: 10_000 },
    { startMarketCap: 47_000, graduationMarketCap: 352_000, founderProceeds: 25_000 },
    { startMarketCap: 83_000, graduationMarketCap: 622_000, founderProceeds: 50_000 },
  ]) {
    const tier = solveTier({ totalSupply: 1e9, entityCost: 7_500, ...mcaps });
    const audit = auditTier(tier);
    assert.ok(audit.supplyBalanced, `supply drift ${audit.supplyDrift}`);
    assert.ok(audit.quoteBalanced, `quote drift ${audit.quoteDrift}`);
  }
});

test('disabling reserves returns supply to the float, not the void', () => {
  const base = { totalSupply: 1e9, startMarketCap: 25_000, graduationMarketCap: 190_000, founderProceeds: 10_000, entityCost: 7_500 };

  const both = solveTier(base);
  const noRewards = solveTier({ ...base, toggles: { launchRewards: false } });
  const neither = solveTier({ ...base, toggles: { compensation: false, launchRewards: false } });

  assert.ok(noRewards.allocation.curveInventory > both.allocation.curveInventory);
  assert.ok(neither.allocation.curveInventory > noRewards.allocation.curveInventory);

  // Supply still conserved in every mode.
  for (const tier of [both, noRewards, neither]) {
    assert.ok(auditTier(tier).supplyBalanced);
  }

  // Toggling reserves must not change what the founder is paid.
  assert.equal(neither.proceeds.founderProceeds, both.proceeds.founderProceeds);
});

test('reserve resolution accounts for every token', () => {
  const { reserved, float } = resolveReserves(1e9, {});
  assert.equal(reserved + float, 1e9);
  assert.equal(reserved, 400e6);
});

test('founder share of raise is surfaced and is well under half', () => {
  const tier = solveTier(STAR_MICRO);
  // The headline is "$10K raise"; buyers actually pay ~$35K.
  assert.ok(tier.proceeds.founderShareOfRaise < 0.30);
  assert.ok(tier.proceeds.founderShareOfRaise > 0.25);
});

test('price impact grows with order size on a thin curve', () => {
  const curve = calibrate({
    totalSupply: 1e9,
    startMarketCap: 25_000,
    graduationMarketCap: 190_000,
    curveInventory: 507.9e6,
  });

  const small = priceImpact(curve, 250e6, 100);
  const large = priceImpact(curve, 250e6, 10_000);
  assert.ok(large.impactPct > small.impactPct);
  assert.ok(small.impactPct > 0);
});

test('rejects tiers that cannot physically close', () => {
  assert.throws(
    () => solveTier({
      totalSupply: 1e9,
      startMarketCap: 25_000,
      graduationMarketCap: 190_000,
      founderProceeds: 500_000, // more than the curve can ever raise
      entityCost: 7_500,
    }),
    /cannot close/
  );
});

test('rejects incoherent curve inputs', () => {
  const bad = { totalSupply: 1e9, startMarketCap: 100_000, graduationMarketCap: 50_000, curveInventory: 500e6 };
  assert.throws(() => calibrate(bad), /must exceed/);
  assert.throws(() => calibrate({ ...bad, graduationMarketCap: 200_000, curveInventory: 2e9 }), /cannot exceed/);
});
