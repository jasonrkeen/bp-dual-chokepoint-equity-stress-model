"""Publication-ready charts for model outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from .market_data import MarketBaseline
from .model import DeterministicResult, deterministic_model

GREEN = "#16794F"
DARK = "#17342D"
LIME = "#9BC53D"
TEAL = "#2B9A8B"
RED = "#C64B45"
GOLD = "#D6A43B"
LIGHT = "#EAF3EF"
GRID = "#D6E2DD"


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelcolor": DARK,
            "axes.edgecolor": GRID,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "xtick.color": DARK,
            "ytick.color": DARK,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
        }
    )


def build_all_charts(
    chart_dir: Path,
    summaries: pd.DataFrame,
    deterministic: pd.DataFrame,
    simulations: dict[str, dict[str, np.ndarray]],
    scenarios: pd.DataFrame,
    config: dict[str, Any],
    baseline: MarketBaseline,
) -> dict[str, Path]:
    chart_dir.mkdir(parents=True, exist_ok=True)
    apply_style()
    paths = {
        "scenario_ranges": chart_dir / "scenario_valuation_ranges.png",
        "probabilities": chart_dir / "probability_above_baseline.png",
        "waterfall": chart_dir / "dual_crisis_earnings_waterfall.png",
        "threshold": chart_dir / "dual_chokepoint_threshold_map.png",
        "sensitivity": chart_dir / "dual_crisis_sensitivity.png",
        "distributions": chart_dir / "scenario_distributions.png",
    }
    scenario_ranges(summaries, baseline, paths["scenario_ranges"])
    probability_chart(summaries, paths["probabilities"])
    waterfall_chart(deterministic, config, paths["waterfall"])
    threshold_map(scenarios, config, baseline, paths["threshold"])
    sensitivity_chart(scenarios, config, baseline, paths["sensitivity"])
    distribution_chart(simulations, baseline, paths["distributions"])
    return paths


def scenario_ranges(
    summaries: pd.DataFrame, baseline: MarketBaseline, output: Path
) -> None:
    frame = summaries.copy()
    y = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(10.5, 5.7))
    ax.hlines(y, frame["p10"], frame["p90"], color=TEAL, lw=7, alpha=0.28)
    ax.scatter(frame["median"], y, s=75, color=GREEN, zorder=3, label="Median")
    ax.scatter(frame["p10"], y, s=24, color=TEAL, zorder=3)
    ax.scatter(frame["p90"], y, s=24, color=TEAL, zorder=3)
    ax.axvline(
        baseline.bp_adr_price,
        color=RED,
        ls="--",
        lw=1.8,
        label=f"Baseline ${baseline.bp_adr_price:.2f}",
    )
    for idx, row in frame.iterrows():
        ax.text(row["median"] + 0.5, idx, f"${row['median']:.2f}", va="center", color=DARK)
    ax.set_yticks(y, frame["scenario"])
    ax.invert_yaxis()
    ax.set_xlabel("Implied BP ADR value (USD)")
    ax.set_title("Conditional BP ADR valuation ranges")
    ax.grid(axis="x")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def probability_chart(summaries: pd.DataFrame, output: Path) -> None:
    frame = summaries.copy()
    pct = frame["probability_above_baseline"] * 100
    colors = [GREEN if value >= 50 else GOLD if value >= 25 else RED for value in pct]
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    bars = ax.barh(frame["scenario"], pct, color=colors, alpha=0.9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Conditional probability above baseline (%)")
    ax.set_title("Probability BP ADR finishes above the market baseline")
    ax.grid(axis="x")
    ax.bar_label(bars, labels=[f"{value:.1f}%" for value in pct], padding=5, color=DARK)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def waterfall_chart(
    deterministic: pd.DataFrame, config: dict[str, Any], output: Path
) -> None:
    row = deterministic.loc[
        deterministic["scenario"].eq("Dual-Chokepoint Crisis")
    ].iloc[0]
    base = float(config["company"]["underlying_rc_profit_bn"])
    labels = [
        "Baseline\nprofit",
        "Upstream",
        "Gas/LNG",
        "Refining",
        "Trading +\ninventory",
        "Volumes",
        "Demand",
        "Freight +\nsecurity",
        "Scenario\nprofit",
    ]
    changes = [
        base,
        row["upstream_delta_bn"],
        row["gas_delta_bn"],
        row["refining_delta_bn"],
        row["trading_delta_bn"] + row["inventory_delta_bn"],
        -row["volume_loss_bn"],
        -row["customer_demand_loss_bn"],
        -row["freight_security_cost_bn"],
    ]
    cumulative = [0.0]
    for value in changes:
        cumulative.append(cumulative[-1] + value)
    bottoms = [0.0] + cumulative[1:-1]
    heights = [base] + changes[1:]
    colors = [DARK] + [GREEN if value >= 0 else RED for value in changes[1:]]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(11.2, 5.7))
    ax.bar(x[:-1], heights, bottom=bottoms, color=colors, width=0.72)
    ax.bar(x[-1], row["net_income_bn"], color=TEAL, width=0.72)
    ax.axhline(0, color=DARK, lw=0.8)
    ax.set_xticks(x, labels)
    ax.set_ylabel("USD billions")
    ax.set_title("Dual-chokepoint central case: earnings transmission")
    ax.grid(axis="y")
    for idx in range(len(x) - 1):
        value = heights[idx]
        y = bottoms[idx] + value
        ax.text(idx, y + (0.35 if value >= 0 else -0.55), f"{value:+.1f}", ha="center", fontsize=9)
    ax.text(x[-1], row["net_income_bn"] + 0.35, f"{row['net_income_bn']:.1f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def threshold_map(
    scenarios: pd.DataFrame,
    config: dict[str, Any],
    baseline: MarketBaseline,
    output: Path,
) -> None:
    reference = scenarios.loc[
        scenarios["scenario"].eq("Dual-Chokepoint Crisis")
    ].iloc[0].to_dict()
    reference["demand_destruction"] = 0.09
    reference["risk_premium"] = 0.12
    h_values = np.linspace(0.05, 0.90, 36)
    b_values = np.linspace(0.05, 0.90, 36)
    grid = np.zeros((len(b_values), len(h_values)))
    for i, b_value in enumerate(b_values):
        for j, h_value in enumerate(h_values):
            row = dict(reference)
            row["hormuz_disruption"] = float(h_value)
            row["bab_disruption"] = float(b_value)
            grid[i, j] = deterministic_model(row, config, baseline).implied_adr_value

    cmap = LinearSegmentedColormap.from_list(
        "bpstress", [RED, "#F2D37C", LIGHT, LIME, GREEN]
    )
    fig, ax = plt.subplots(figsize=(9.0, 6.2))
    image = ax.imshow(
        grid,
        origin="lower",
        extent=[h_values.min(), h_values.max(), b_values.min(), b_values.max()],
        aspect="auto",
        cmap=cmap,
    )
    contour = ax.contour(
        h_values,
        b_values,
        grid,
        levels=[baseline.bp_adr_price],
        colors=[DARK],
        linewidths=2.2,
    )
    ax.clabel(contour, fmt={baseline.bp_adr_price: "Baseline boundary"}, fontsize=9)
    ax.set_xlabel("Hormuz disruption share")
    ax.set_ylabel("Bab al-Mandeb disruption share")
    ax.set_title("Where operational losses overwhelm the commodity benefit")
    colorbar = fig.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label("Deterministic BP ADR value (USD)")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def sensitivity_chart(
    scenarios: pd.DataFrame,
    config: dict[str, Any],
    baseline: MarketBaseline,
    output: Path,
) -> None:
    base_row = scenarios.loc[
        scenarios["scenario"].eq("Dual-Chokepoint Crisis")
    ].iloc[0].to_dict()
    base_value = deterministic_model(base_row, config, baseline).implied_adr_value
    shocks = {
        "Hormuz disruption": ("hormuz_disruption", 0.10, 0, 1),
        "Bab disruption": ("bab_disruption", 0.10, 0, 1),
        "Demand destruction": ("demand_destruction", 0.05, 0, 0.4),
        "BP volume loss": ("bp_volume_loss", 0.03, 0, 0.3),
        "Equity risk premium": ("risk_premium", 0.05, 0, 0.4),
        "Policy offset (mmb/d)": ("policy_offset_mbd", 0.80, 0, 5),
        "TTF exogenous shock": ("ttf_exogenous_shock", 0.20, -0.5, 1.5),
    }
    records = []
    for label, (column, shock, lower, upper) in shocks.items():
        low = dict(base_row)
        high = dict(base_row)
        low[column] = float(np.clip(float(base_row[column]) - shock, lower, upper))
        high[column] = float(np.clip(float(base_row[column]) + shock, lower, upper))
        low_value = deterministic_model(low, config, baseline).implied_adr_value
        high_value = deterministic_model(high, config, baseline).implied_adr_value
        records.append(
            {
                "driver": label,
                "low": low_value - base_value,
                "high": high_value - base_value,
                "span": abs(high_value - low_value),
            }
        )
    frame = pd.DataFrame(records).sort_values("span")
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    y = np.arange(len(frame))
    ax.barh(y, frame["low"], color=RED, label="Lower input", alpha=0.88)
    ax.barh(y, frame["high"], color=GREEN, label="Higher input", alpha=0.88)
    ax.set_yticks(y, frame["driver"])
    ax.axvline(0, color=DARK, lw=1)
    ax.set_xlabel("Change from central implied value (USD/ADR)")
    ax.set_title("Dual-crisis one-at-a-time sensitivity")
    ax.grid(axis="x")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def distribution_chart(
    simulations: dict[str, dict[str, np.ndarray]],
    baseline: MarketBaseline,
    output: Path,
) -> None:
    labels = list(simulations)
    data = [simulations[label]["implied_adr_value"] for label in labels]
    fig, ax = plt.subplots(figsize=(11.0, 5.8))
    parts = ax.violinplot(data, showmedians=True, showextrema=False, widths=0.82)
    for body in parts["bodies"]:
        body.set_facecolor(TEAL)
        body.set_edgecolor(GREEN)
        body.set_alpha(0.42)
    parts["cmedians"].set_color(DARK)
    parts["cmedians"].set_linewidth(2)
    ax.axhline(
        baseline.bp_adr_price,
        color=RED,
        ls="--",
        lw=1.6,
        label=f"Baseline ${baseline.bp_adr_price:.2f}",
    )
    ax.set_xticks(np.arange(1, len(labels) + 1), [label.replace(" ", "\n") for label in labels])
    ax.set_ylabel("Implied BP ADR value (USD)")
    ax.set_title("Conditional valuation distributions (10,000 draws each)")
    ax.grid(axis="y")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)
