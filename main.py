"""Run the BP Dual-Chokepoint Energy Shock Equity Stress Model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bp_stress_model.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run BP's scenario-based dual-chokepoint equity stress model."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt to refresh BP ADR and Brent observations; fall back safely if unavailable.",
    )
    parser.add_argument(
        "--draws",
        type=int,
        default=None,
        help="Override the configured Monte Carlo draws per scenario.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override the configured random seed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(ROOT, live=args.live, draws=args.draws, seed=args.seed)

