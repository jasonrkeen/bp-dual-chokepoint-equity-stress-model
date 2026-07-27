# Methodology

## Purpose

The BP Dual-Chokepoint Energy Shock Equity Stress Model is a conditional
scenario engine. It translates a physical energy disruption into market,
corporate, and equity-valuation outcomes without claiming to forecast whether
the disruption will occur.

## Baseline

The published run is pinned to July 27, 2026:

- BP NYSE ADR: $42.86;
- Brent: $90.93/bbl;
- BP 2025 underlying replacement-cost profit: $7.5 billion;
- BP 2025 operating cash flow: $24.5 billion;
- BP Q1 2026 net debt: $25.3 billion;
- BP Q1 2026 upstream production reference: 2.344 mmboe/d; and
- BP Q1 2026 refining-throughput reference: more than 1.5 mmbbl/d.

TTF and the composite crack spread are transparent modeled references because
the project does not use licensed real-time market feeds.

## Physical supply layer

For each scenario:

```text
Hormuz loss
  = Hormuz oil flow × Hormuz disruption share

Effective Bab loss
  = Bab oil flow × Bab disruption share × (1 - reroutable share)

Offsets
  = available bypass × bypass utilization
  + policy offset
  + demand response

Net supply gap
  = max(0, Hormuz loss + effective Bab loss + other product loss - offsets)
```

Bab al-Mandeb is not treated as a fully additive physical loss because many
cargoes can reroute around the Cape of Good Hope. The model captures its
remaining effect through effective delays, freight, insurance, and security
costs.

## Market layer

Let `g` be the net oil supply gap divided by global liquids demand.

```text
Brent multiplier
  = [1 + sentiment + 5g + 18g²]
  × [1 - 1.2 × demand destruction]
```

The quadratic term represents the nonlinear short-run price response when
spare supply and logistical flexibility are constrained. Brent is bounded to
prevent invalid simulated values.

TTF responds to:

- the scenario's exogenous gas-price shock; and
- the modeled Hormuz LNG interruption.

The composite refining crack responds to:

- Russian and other product losses;
- crude disruption affecting feedstock availability;
- Bab al-Mandeb logistics pressure; and
- demand destruction.

## Corporate layer

### Upstream

```text
Upstream earnings change
  = BP liquids volume
  × change in Brent
  × after-tax capture rate
  × (1 - BP volume loss)
```

### Gas and LNG

The model applies a bounded price-capture rate to a transparent gas-earnings
reference pool. This avoids treating BP's gas and LNG portfolio as a pure spot
TTF position.

### Refining

```text
Refining earnings change
  = throughput
  × change in composite crack
  × after-tax capture rate
  × refinery availability
```

### Other channels

The corporate layer separately models:

- bounded trading opportunity;
- inventory gains;
- upstream and cargo-volume losses;
- customer demand loss;
- freight and security expense;
- working-capital requirements;
- operating cash flow;
- free cash flow; and
- net debt.

## Valuation layer

Three valuation methods are combined:

### Earnings method

The baseline ADR price scales with scenario earnings using a sublinear exponent,
then applies risk-premium, demand-destruction, and net-debt adjustments.

### Free-cash-flow method

The baseline ADR price scales with scenario free cash flow using a sublinear
exponent, then applies risk-premium and net-debt adjustments.

### Market-factor method

The factor estimate includes:

- BP oil beta: 0.35;
- broad-market beta: 0.90;
- gas and refining factors;
- GBP/USD pass-through; and
- the scenario equity risk premium.

The central weights are 35% earnings, 35% free cash flow, and 30% market
factor. Monte Carlo draws vary these weights with a Dirichlet distribution.

## Monte Carlo uncertainty

Each scenario uses 10,000 draws. The simulation varies:

- Hormuz and Bab disruption severity;
- bypass utilization;
- policy and demand offsets;
- Russian product losses;
- duration;
- BP volume loss;
- refinery availability;
- market return;
- equity risk premium;
- gas and currency shocks;
- upstream and refining capture rates;
- trading outcomes;
- working capital;
- valuation exponents and weights; and
- model-form uncertainty.

A 12% lognormal model-error term explicitly represents the gap between a
transparent public-data model and BP's internal planning information.

The reported P10, median, P90, and probability above baseline are conditional
on the scenario.

## Threshold map

The threshold map varies Hormuz and Bab al-Mandeb disruption while holding the
other Dual-Chokepoint Crisis assumptions fixed. The contour identifies the
combination where the deterministic ADR estimate equals the observed baseline.

It is not a forecast boundary. Moving demand destruction, risk premium, volume
loss, or valuation assumptions will move the contour.

## Governance

The project separates:

1. observed public data;
2. modeled reference values;
3. transparent assumptions; and
4. stochastic uncertainty.

The pipeline records its version, seed, draw count, market-data status, output
inventory, and validation checks in `outputs/run_manifest.json`.

## Interpretation guardrails

- Do not interpret conditional probabilities as event probabilities.
- Do not interpret implied values as price targets.
- Do not assume high commodity prices automatically benefit BP.
- Recalibrate the model when BP filings or disruption data change.
- Treat trading estimates as bounded uncertainty, not reported results.
- Use the output as structured scenario research, not investment advice.

