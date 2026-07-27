"""Configuration and input loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_config(root: Path) -> dict[str, Any]:
    with (root / "config" / "model_config.yaml").open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError("model_config.yaml must contain a mapping.")
    return config


def load_scenarios(root: Path) -> pd.DataFrame:
    scenarios = pd.read_csv(root / "data" / "input" / "scenarios.csv")
    required = {
        "scenario",
        "hormuz_disruption",
        "bab_disruption",
        "duration_days",
        "demand_destruction",
        "risk_premium",
    }
    missing = required.difference(scenarios.columns)
    if missing:
        raise ValueError(f"Scenario file is missing columns: {sorted(missing)}")
    if scenarios["scenario"].duplicated().any():
        raise ValueError("Scenario names must be unique.")
    for column in ("hormuz_disruption", "bab_disruption", "demand_destruction"):
        if not scenarios[column].between(0, 1).all():
            raise ValueError(f"{column} must be between 0 and 1.")
    return scenarios

