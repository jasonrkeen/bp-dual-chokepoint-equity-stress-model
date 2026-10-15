# Production-parity review — October 14, 2026

**Scope:** computational validation and two related experimental market-factor variants. Production v1.0.1, its configuration, scenarios, and published outputs are unchanged.

## Seed correction

The earlier challenger package restarted every scenario with seed `20260727`. The production pipeline uses `20260727 + 101 * scenario_index`, starting the index at 1. The new runner uses the production schedule and verifies its source/input/output files against Git blob hashes from commit `df298da3b38ab68e862f66d25986d2b2a3cfe808`.

This explains the earlier differences between the paired-control and published tables. Common draws across architectures do not require the same seed across different scenarios.

## Executed checks

- All 50,000 Architecture A valuations matched the preserved production implementation exactly.
- All 40 production output arrays matched an instrumented in-memory copy exactly.
- The new runner's 150,000 A/B/C valuations matched the preserved challenger implementation exactly under the corrected seeds.
- All published summary values matched within `1e-12` absolute tolerance; maximum difference was `7.105427357601002e-15`.
- Eight focused computational tests passed, including rejection of the old seed schedule as an exact production match and refusal to overwrite production paths.

The detailed outputs and environment are in [the results manifest](../validation/results/run_manifest.json). These checks establish implementation agreement, not economic validity or independent scientific review.

## Corrected conditional medians

| Scenario | A | B | C | C versus A |
|---|---:|---:|---:|---:|
| Diplomatic De-escalation | $38.17 | $38.21 | $38.31 | +0.37% |
| Extended Hormuz Constraint | $60.40 | $60.11 | $59.70 | -1.16% |
| Dual-Chokepoint Crisis | $62.50 | $62.13 | $61.60 | -1.44% |
| Product and LNG Squeeze | $58.06 | $57.82 | $57.53 | -0.91% |
| Demand Destruction Threshold | $28.67 | $29.14 | $29.25 | +2.02% |

Values are modeled USD per ADR under the frozen $42.86 baseline, not current quotes, price targets, or event probabilities. See [the full paired results](../validation/results/paired_results.csv).

Demand destruction has the largest relative-percentage sensitivity: 48.06% of A/C pairs differ by more than 2%, versus 20.08% for Dual Crisis. Dual Crisis has the larger mean absolute dollar difference: about $0.92 versus $0.59. These descriptive criteria are not calibrated economic acceptance thresholds.

## Interpretation limits

B and C are related variants, not independent confirmations. They share earnings, FCF, valuation weights, and model-error draws; high correlations and small final differences are partly mechanical. Averaging alternative valuation estimates is not automatically double counting. This test neither establishes double counting nor proves either challenger economically superior.

The rounded B/C coefficients are frozen experimental assumptions. Their original fitting data and estimation code are not reproduced in this test. Historical daily coefficients, the daily intercept, and simple scenario-scale changes are not interchangeable without a validated horizon/return mapping.

C removes only the direct incremental Brent term. Oil still enters the sector mapping and corporate fundamentals; indirect market-component oil loading remains `0.90 * 0.214 = 0.1926`. No coefficient or ensemble-weight optimality is claimed.

A clean-process rerun in the same environment is repeatability, not independent researcher or cross-platform validation. Earlier documentation using “independent reproduction” should be read in that narrower sense. NumPy's [random compatibility policy](https://numpy.org/doc/2.0/reference/random/compatibility.html) explains why the environment is recorded and pinned.

## Reproduce

```bash
python -m pip install -r validation/requirements-lock.txt
python validation/run_challengers.py --root . --out validation/rerun_results
python -m unittest discover -s validation -p test_parity.py -v
```

The runner instruments only an in-memory copy to expose shared values, executes the original production function separately, and compares every returned array. It does not edit production source or generate extra random draws for B/C. It fails closed if any frozen reference file changes.

**Disposition:** retain production unchanged; keep B/C experimental. Broader historical-regression and event-intelligence claims require separately traceable data, code, and validation before promotion to the public README.
