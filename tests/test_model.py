"""Model invariants and regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bp_stress_model.config import load_config, load_scenarios
from bp_stress_model.market_data import load_market_baseline
from bp_stress_model.model import (
    deterministic_model,
    monte_carlo,
    summarize_simulation,
)
from bp_stress_model.report import FONT_BOLD, FONT_REGULAR


class StressModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(ROOT)
        cls.scenarios = load_scenarios(ROOT)
        cls.baseline = load_market_baseline(cls.config)

    def test_expected_scenario_set(self) -> None:
        self.assertEqual(len(self.scenarios), 5)
        self.assertIn("Dual-Chokepoint Crisis", set(self.scenarios["scenario"]))
        self.assertIn("Demand Destruction Threshold", set(self.scenarios["scenario"]))

    def test_supply_gap_is_nonnegative(self) -> None:
        for _, row in self.scenarios.iterrows():
            result = deterministic_model(row, self.config, self.baseline)
            self.assertGreaterEqual(result.net_supply_gap_mbd, 0)

    def test_higher_hormuz_disruption_raises_brent_ceteris_paribus(self) -> None:
        row = self.scenarios.iloc[1].to_dict()
        low = dict(row, hormuz_disruption=0.25)
        high = dict(row, hormuz_disruption=0.75)
        self.assertGreater(
            deterministic_model(high, self.config, self.baseline).brent_usd_bbl,
            deterministic_model(low, self.config, self.baseline).brent_usd_bbl,
        )

    def test_seeded_simulation_is_reproducible(self) -> None:
        row = self.scenarios.iloc[2]
        first = monte_carlo(row, self.config, self.baseline, 1500, 99)
        second = monte_carlo(row, self.config, self.baseline, 1500, 99)
        np.testing.assert_allclose(
            first["implied_adr_value"], second["implied_adr_value"]
        )

    def test_summary_quantiles_and_probability(self) -> None:
        row = self.scenarios.iloc[2]
        simulation = monte_carlo(row, self.config, self.baseline, 2500, 42)
        summary = summarize_simulation(
            row["scenario"], simulation, self.baseline.bp_adr_price
        )
        self.assertLessEqual(summary["p10"], summary["median"])
        self.assertLessEqual(summary["median"], summary["p90"])
        self.assertGreaterEqual(summary["probability_above_baseline"], 0)
        self.assertLessEqual(summary["probability_above_baseline"], 1)

    def test_demand_threshold_is_below_dual_crisis(self) -> None:
        dual = self.scenarios.loc[
            self.scenarios["scenario"].eq("Dual-Chokepoint Crisis")
        ].iloc[0]
        demand = self.scenarios.loc[
            self.scenarios["scenario"].eq("Demand Destruction Threshold")
        ].iloc[0]
        dual_value = deterministic_model(dual, self.config, self.baseline).implied_adr_value
        demand_value = deterministic_model(
            demand, self.config, self.baseline
        ).implied_adr_value
        self.assertLess(demand_value, dual_value)

    def test_pdf_fonts_are_registered_portably(self) -> None:
        self.assertTrue(FONT_REGULAR)
        self.assertTrue(FONT_BOLD)


if __name__ == "__main__":
    unittest.main()
