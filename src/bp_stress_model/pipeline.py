"""End-to-end model pipeline."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .charts import build_all_charts
from .config import load_config, load_scenarios
from .market_data import load_market_baseline
from .model import deterministic_model, monte_carlo, summarize_simulation
from .report import generate_pdf


def run_pipeline(
    root: Path,
    live: bool = False,
    draws: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    config = load_config(root)
    scenarios = load_scenarios(root)
    baseline = load_market_baseline(config, live=live)
    n_draws = int(draws or config["simulation"]["draws"])
    random_seed = int(seed or config["simulation"]["seed"])
    if n_draws < 1000:
        raise ValueError("Use at least 1,000 draws for stable scenario percentiles.")
    config["simulation"]["draws"] = n_draws
    config["simulation"]["seed"] = random_seed

    output = root / "outputs"
    table_dir = output / "tables"
    chart_dir = output / "charts"
    pdf_dir = output / "pdf"
    for directory in (table_dir, chart_dir, pdf_dir):
        directory.mkdir(parents=True, exist_ok=True)

    deterministic_records = []
    summaries = []
    simulations: dict[str, dict[str, np.ndarray]] = {}
    print("=" * 72)
    print(config["project"]["title"])
    print("=" * 72)
    print(f"Baseline: {baseline.observed_at} ({baseline.status})")
    print(f"BP ADR: ${baseline.bp_adr_price:.2f} | Brent: ${baseline.brent_usd_bbl:.2f}/bbl")
    print(f"Monte Carlo: {n_draws:,} draws per scenario")

    for idx, (_, row) in enumerate(scenarios.iterrows(), start=1):
        name = str(row["scenario"])
        print(f"[{idx}/{len(scenarios)}] {name}")
        central = deterministic_model(row, config, baseline)
        simulation = monte_carlo(
            row,
            config,
            baseline,
            draws=n_draws,
            seed=random_seed + idx * 101,
        )
        deterministic_records.append(central.to_dict())
        summaries.append(
            summarize_simulation(name, simulation, baseline.bp_adr_price)
        )
        simulations[name] = simulation

    deterministic_frame = pd.DataFrame(deterministic_records)
    summary_frame = pd.DataFrame(summaries)
    summary_frame.to_csv(table_dir / "scenario_summary.csv", index=False)
    deterministic_frame.to_csv(table_dir / "deterministic_scenario_details.csv", index=False)
    _save_simulation_samples(simulations, table_dir / "monte_carlo_samples.csv")
    _save_assumptions(config, table_dir / "assumption_register.csv")

    charts = build_all_charts(
        chart_dir,
        summary_frame,
        deterministic_frame,
        simulations,
        scenarios,
        config,
        baseline,
    )
    _validate_chart_assets(charts)
    pdf_path = generate_pdf(
        pdf_dir / "BP_Dual_Chokepoint_Equity_Stress_Report.pdf",
        summary_frame,
        deterministic_frame,
        charts,
        config,
        baseline,
    )
    _write_executive_summary(
        output / "executive_summary.md", summary_frame, config, baseline
    )
    manifest = {
        "project": config["project"],
        "run_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "market_baseline": asdict(baseline),
        "simulation": {"draws_per_scenario": n_draws, "seed": random_seed},
        "scenario_count": int(len(scenarios)),
        "output_files": sorted(
            str(path.relative_to(root))
            for path in output.rglob("*")
            if path.is_file()
        ),
        "validation": {
            "all_p10_le_median": bool((summary_frame["p10"] <= summary_frame["median"]).all()),
            "all_median_le_p90": bool((summary_frame["median"] <= summary_frame["p90"]).all()),
            "probabilities_in_unit_interval": bool(
                summary_frame["probability_above_baseline"].between(0, 1).all()
            ),
            "finite_outputs": bool(
                np.isfinite(
                    summary_frame.select_dtypes(include=[np.number]).to_numpy()
                ).all()
            ),
        },
    }
    with (output / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    print("-" * 72)
    for _, row in summary_frame.iterrows():
        print(
            f"{row['scenario']:<31} "
            f"median ${row['median']:>6.2f} | "
            f"P(>base) {row['probability_above_baseline']:>6.1%}"
        )
    print(f"Saved {pdf_path}")
    return {
        "summaries": summary_frame,
        "deterministic": deterministic_frame,
        "manifest": manifest,
        "pdf": pdf_path,
    }


def _save_simulation_samples(
    simulations: dict[str, dict[str, np.ndarray]], output: Path
) -> None:
    frames = []
    for scenario, values in simulations.items():
        size = len(values["implied_adr_value"])
        frames.append(
            pd.DataFrame(
                {
                    "scenario": scenario,
                    "draw": np.arange(1, size + 1),
                    **values,
                }
            )
        )
    pd.concat(frames, ignore_index=True).to_csv(output, index=False)


def _flatten(prefix: str, value: Any, records: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            _flatten(child_prefix, child, records)
    else:
        records.append({"parameter": prefix, "value": value})


def _save_assumptions(config: dict[str, Any], output: Path) -> None:
    records: list[dict[str, Any]] = []
    for section in (
        "market",
        "physical",
        "company",
        "market_model",
        "corporate_model",
        "valuation",
        "simulation",
    ):
        _flatten(section, config[section], records)
    pd.DataFrame(records).to_csv(output, index=False)


def _write_executive_summary(
    output: Path,
    summaries: pd.DataFrame,
    config: dict[str, Any],
    baseline: Any,
) -> None:
    best = summaries.loc[summaries["median"].idxmax()]
    threshold = summaries.loc[
        summaries["scenario"].eq("Demand Destruction Threshold")
    ].iloc[0]
    lines = [
        f"# {config['project']['title']}",
        "",
        f"**Baseline:** {config['project']['baseline_date']} | "
        f"BP ADR ${baseline.bp_adr_price:.2f} | "
        f"Brent ${baseline.brent_usd_bbl:.2f}/bbl",
        "",
        "## Executive judgment",
        "",
        "BP benefits initially from higher crude and gas realizations and tighter "
        "refining margins. The benefit is not unlimited: prolonged disruption raises "
        "volume loss, freight, security, working-capital, demand-destruction, net-debt, "
        "and valuation-compression risks.",
        "",
        f"- Highest conditional median: **{best['scenario']} - ${best['median']:.2f}**.",
        f"- Demand-threshold median: **${threshold['median']:.2f}**.",
        f"- Demand-threshold probability above baseline: "
        f"**{threshold['probability_above_baseline']:.1%}**.",
        "",
        "These probabilities are conditional on each scenario and are not estimates "
        "of scenario occurrence. This is research, not investment advice.",
    ]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_chart_assets(charts: dict[str, Path]) -> None:
    invalid = [
        str(path)
        for path in charts.values()
        if not path.exists() or path.stat().st_size < 10_000
    ]
    if invalid:
        raise RuntimeError(f"Chart generation produced invalid assets: {invalid}")
