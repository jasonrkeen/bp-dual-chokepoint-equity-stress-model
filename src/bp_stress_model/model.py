"""Physical, market, corporate, and valuation layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import numpy as np

from .market_data import MarketBaseline


@dataclass(frozen=True)
class DeterministicResult:
    scenario: str
    gross_hormuz_loss_mbd: float
    effective_bab_loss_mbd: float
    other_product_loss_mbd: float
    total_offsets_mbd: float
    net_supply_gap_mbd: float
    brent_usd_bbl: float
    ttf_usd_mmbtu: float
    crack_usd_bbl: float
    freight_index: float
    upstream_delta_bn: float
    gas_delta_bn: float
    refining_delta_bn: float
    trading_delta_bn: float
    inventory_delta_bn: float
    volume_loss_bn: float
    customer_demand_loss_bn: float
    freight_security_cost_bn: float
    working_capital_bn: float
    net_income_bn: float
    operating_cash_flow_bn: float
    free_cash_flow_bn: float
    net_debt_bn: float
    earnings_value: float
    fcf_value: float
    market_value: float
    implied_adr_value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deterministic_model(
    row: Mapping[str, Any],
    config: dict[str, Any],
    baseline: MarketBaseline,
) -> DeterministicResult:
    """Evaluate one transparent central scenario."""
    physical = config["physical"]
    market_cfg = config["market"]
    market_model = config["market_model"]
    company = config["company"]
    corporate = config["corporate_model"]
    valuation = config["valuation"]

    h = float(row["hormuz_disruption"])
    b = float(row["bab_disruption"])
    duration = float(row["duration_days"])
    demand_destruction = float(row["demand_destruction"])

    gross_hormuz = float(physical["hormuz_oil_flow_mbd"]) * h
    bab_loss = (
        float(physical["bab_oil_flow_mbd"])
        * b
        * (1.0 - float(physical["bab_reroutable_share"]))
    )
    other_loss = float(row["russian_product_loss_mbd"])
    bypass = float(physical["available_bypass_mbd"]) * float(
        physical["bypass_utilization"]
    )
    offsets = (
        bypass
        + float(row["policy_offset_mbd"])
        + float(row["demand_response_mbd"])
    )
    net_gap = max(0.0, gross_hormuz + bab_loss + other_loss - offsets)
    gap_share = net_gap / float(market_cfg["global_liquids_demand_mbd"])

    brent_multiplier = (
        1.0
        + float(row["oil_sentiment"])
        + float(market_model["oil_gap_linear"]) * gap_share
        + float(market_model["oil_gap_convex"]) * gap_share**2
    )
    brent_multiplier *= max(
        0.55, 1.0 - float(market_model["demand_price_drag"]) * demand_destruction
    )
    brent = max(35.0, baseline.brent_usd_bbl * brent_multiplier)

    lng_lost_share = h
    ttf = baseline.ttf_usd_mmbtu * max(
        0.65,
        1.0
        + float(row["ttf_exogenous_shock"])
        + float(market_model["ttf_lng_elasticity"]) * lng_lost_share,
    )

    product_gap_share = min(
        0.25, (other_loss + 0.25 * gross_hormuz) / 30.0
    )
    crack_multiplier = (
        1.0
        + float(market_model["crack_product_elasticity"]) * product_gap_share
        + float(market_model["crack_logistics_elasticity"]) * b
        - float(market_model["crack_demand_drag"]) * demand_destruction
    )
    crack = float(np.clip(baseline.composite_crack_usd_bbl * crack_multiplier, 8, 60))
    freight = 100.0 * (
        1.0 + 0.45 * h + 0.70 * b + 0.0012 * max(duration - 30.0, 0.0)
    )

    liquids_mbd = (
        float(company["upstream_production_mmboed"]) * float(company["liquids_share"])
    )
    annual_liquids_mmbbl = liquids_mbd * 365.0
    upstream_delta = (
        annual_liquids_mmbbl
        * (brent - baseline.brent_usd_bbl)
        * float(corporate["upstream_after_tax_capture"])
        * (1.0 - float(row["bp_volume_loss"]))
        / 1000.0
    )
    gas_delta = (
        float(corporate["gas_earnings_base_bn"])
        * (ttf / baseline.ttf_usd_mmbtu - 1.0)
        * float(corporate["gas_price_capture"])
    )
    refining_delta = (
        float(company["refining_throughput_mbd"])
        * 365.0
        * (crack - baseline.composite_crack_usd_bbl)
        * float(corporate["refining_after_tax_capture"])
        * float(row["refinery_availability"])
        / 1000.0
    )
    trading_delta = min(
        float(corporate["trading_opportunity_cap_bn"]),
        0.45 * abs(brent / baseline.brent_usd_bbl - 1.0)
        + 0.35 * abs(ttf / baseline.ttf_usd_mmbtu - 1.0),
    )
    inventory_delta = max(0.0, brent - baseline.brent_usd_bbl) * 0.012
    volume_loss = float(corporate["volume_profit_pool_bn"]) * float(
        row["bp_volume_loss"]
    )
    customer_loss = float(corporate["customer_demand_exposure_bn"]) * demand_destruction
    freight_security = (
        max(0.0, freight - 100.0)
        * float(corporate["freight_cost_per_index_bn"])
        + duration * float(corporate["security_cost_per_day_bn"])
    )
    working_capital = max(0.0, brent - baseline.brent_usd_bbl) * float(
        corporate["working_capital_per_brent_dollar_bn"]
    )

    base_profit = float(company["underlying_rc_profit_bn"])
    profit = max(
        0.25,
        base_profit
        + upstream_delta
        + gas_delta
        + refining_delta
        + trading_delta
        + inventory_delta
        - volume_loss
        - customer_loss
        - freight_security,
    )
    ocf = max(
        0.5,
        float(company["operating_cash_flow_bn"])
        + 1.18 * (profit - base_profit)
        - working_capital,
    )
    fcf = ocf - float(company["cash_capex_bn"])
    net_debt = max(
        5.0,
        float(company["net_debt_bn"])
        + working_capital
        - 0.22 * max(0.0, profit - base_profit),
    )

    base_price = baseline.bp_adr_price
    risk = float(row["risk_premium"])
    multiple_factor = np.exp(
        -float(valuation["risk_premium_multiplier"]) * risk
        - 0.55 * demand_destruction
    )
    debt_factor = max(
        0.75,
        1.0
        - float(valuation["debt_penalty"])
        * (net_debt / float(company["net_debt_bn"]) - 1.0),
    )
    earnings_value = (
        base_price
        * (profit / base_profit) ** float(valuation["earnings_scaling_exponent"])
        * multiple_factor
        * debt_factor
    )
    base_fcf = float(company["operating_cash_flow_bn"]) - float(
        company["cash_capex_bn"]
    )
    fcf_ratio = max(0.10, fcf / base_fcf)
    fcf_value = (
        base_price
        * fcf_ratio ** float(valuation["fcf_scaling_exponent"])
        * np.exp(-0.85 * risk)
        * debt_factor
    )
    market_value = base_price * max(
        0.20,
        1.0
        + float(valuation["oil_beta"]) * (brent / baseline.brent_usd_bbl - 1.0)
        + float(valuation["market_beta"]) * float(row["market_return"])
        + float(valuation["gas_beta"]) * (ttf / baseline.ttf_usd_mmbtu - 1.0)
        + float(valuation["refining_beta"])
        * (crack / baseline.composite_crack_usd_bbl - 1.0)
        + float(valuation["fx_pass_through"]) * float(row["fx_return"])
        - risk,
    )
    implied = (
        float(valuation["earnings_weight"]) * earnings_value
        + float(valuation["fcf_weight"]) * fcf_value
        + float(valuation["market_weight"]) * market_value
    )

    return DeterministicResult(
        scenario=str(row["scenario"]),
        gross_hormuz_loss_mbd=gross_hormuz,
        effective_bab_loss_mbd=bab_loss,
        other_product_loss_mbd=other_loss,
        total_offsets_mbd=offsets,
        net_supply_gap_mbd=net_gap,
        brent_usd_bbl=brent,
        ttf_usd_mmbtu=ttf,
        crack_usd_bbl=crack,
        freight_index=freight,
        upstream_delta_bn=upstream_delta,
        gas_delta_bn=gas_delta,
        refining_delta_bn=refining_delta,
        trading_delta_bn=trading_delta,
        inventory_delta_bn=inventory_delta,
        volume_loss_bn=volume_loss,
        customer_demand_loss_bn=customer_loss,
        freight_security_cost_bn=freight_security,
        working_capital_bn=working_capital,
        net_income_bn=profit,
        operating_cash_flow_bn=ocf,
        free_cash_flow_bn=fcf,
        net_debt_bn=net_debt,
        earnings_value=float(earnings_value),
        fcf_value=float(fcf_value),
        market_value=float(market_value),
        implied_adr_value=float(implied),
    )


def monte_carlo(
    row: Mapping[str, Any],
    config: dict[str, Any],
    baseline: MarketBaseline,
    draws: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Run vectorized conditional simulation for a single scenario."""
    rng = np.random.default_rng(seed)
    n = int(draws)
    physical = config["physical"]
    market_cfg = config["market"]
    mm = config["market_model"]
    company = config["company"]
    corp = config["corporate_model"]
    val = config["valuation"]

    h = _bounded_normal(rng, float(row["hormuz_disruption"]), 0.075, n, 0, 1)
    b = _bounded_normal(rng, float(row["bab_disruption"]), 0.080, n, 0, 1)
    duration = np.clip(
        rng.lognormal(np.log(max(float(row["duration_days"]), 1)), 0.18, n), 7, 365
    )
    demand = _bounded_normal(
        rng, float(row["demand_destruction"]), 0.025, n, 0, 0.40
    )
    policy = np.clip(
        rng.normal(float(row["policy_offset_mbd"]), 0.30, n), 0, None
    )
    demand_response = np.clip(
        rng.normal(float(row["demand_response_mbd"]), 0.35, n), 0, None
    )
    russian = np.clip(
        rng.normal(float(row["russian_product_loss_mbd"]), 0.20, n), 0, None
    )
    bypass_utilization = _bounded_normal(
        rng, float(physical["bypass_utilization"]), 0.08, n, 0.35, 1.0
    )
    volume_loss = _bounded_normal(
        rng, float(row["bp_volume_loss"]), 0.018, n, 0, 0.30
    )
    refinery_availability = _bounded_normal(
        rng, float(row["refinery_availability"]), 0.025, n, 0.70, 1.0
    )
    market_return = rng.normal(float(row["market_return"]), 0.045, n)
    risk = np.clip(rng.normal(float(row["risk_premium"]), 0.025, n), 0, 0.40)
    ttf_shock = rng.normal(float(row["ttf_exogenous_shock"]), 0.10, n)
    fx_return = rng.normal(float(row["fx_return"]), 0.025, n)
    oil_sentiment = rng.normal(float(row["oil_sentiment"]), 0.025, n)

    gross_hormuz = float(physical["hormuz_oil_flow_mbd"]) * h
    bab_loss = (
        float(physical["bab_oil_flow_mbd"])
        * b
        * (1 - float(physical["bab_reroutable_share"]))
    )
    offsets = (
        float(physical["available_bypass_mbd"]) * bypass_utilization
        + policy
        + demand_response
    )
    net_gap = np.maximum(0, gross_hormuz + bab_loss + russian - offsets)
    gap_share = net_gap / float(market_cfg["global_liquids_demand_mbd"])
    brent = baseline.brent_usd_bbl * (
        1
        + oil_sentiment
        + float(mm["oil_gap_linear"]) * gap_share
        + float(mm["oil_gap_convex"]) * gap_share**2
    ) * np.maximum(0.55, 1 - float(mm["demand_price_drag"]) * demand)
    brent = np.clip(brent, 35, 240)

    ttf = baseline.ttf_usd_mmbtu * np.maximum(
        0.65, 1 + ttf_shock + float(mm["ttf_lng_elasticity"]) * h
    )
    product_gap_share = np.minimum(0.25, (russian + 0.25 * gross_hormuz) / 30.0)
    crack = baseline.composite_crack_usd_bbl * (
        1
        + float(mm["crack_product_elasticity"]) * product_gap_share
        + float(mm["crack_logistics_elasticity"]) * b
        - float(mm["crack_demand_drag"]) * demand
    )
    crack = np.clip(crack, 8, 60)
    freight = 100 * (1 + 0.45 * h + 0.70 * b + 0.0012 * np.maximum(duration - 30, 0))

    liquids_mbd = float(company["upstream_production_mmboed"]) * float(
        company["liquids_share"]
    )
    upstream_capture = _bounded_normal(
        rng, float(corp["upstream_after_tax_capture"]), 0.045, n, 0.20, 0.65
    )
    refining_capture = _bounded_normal(
        rng, float(corp["refining_after_tax_capture"]), 0.050, n, 0.20, 0.70
    )
    upstream_delta = (
        liquids_mbd
        * 365
        * (brent - baseline.brent_usd_bbl)
        * upstream_capture
        * (1 - volume_loss)
        / 1000
    )
    gas_delta = (
        float(corp["gas_earnings_base_bn"])
        * (ttf / baseline.ttf_usd_mmbtu - 1)
        * _bounded_normal(rng, float(corp["gas_price_capture"]), 0.06, n, 0.2, 0.7)
    )
    refining_delta = (
        float(company["refining_throughput_mbd"])
        * 365
        * (crack - baseline.composite_crack_usd_bbl)
        * refining_capture
        * refinery_availability
        / 1000
    )
    trading_mean = np.minimum(
        float(corp["trading_opportunity_cap_bn"]),
        0.45 * np.abs(brent / baseline.brent_usd_bbl - 1)
        + 0.35 * np.abs(ttf / baseline.ttf_usd_mmbtu - 1),
    )
    trading_delta = np.clip(
        rng.normal(trading_mean, 0.30 + 0.20 * trading_mean), -1.0, 2.0
    )
    inventory_delta = np.maximum(0, brent - baseline.brent_usd_bbl) * rng.normal(
        0.012, 0.003, n
    )
    lost_volume = float(corp["volume_profit_pool_bn"]) * volume_loss
    customer_loss = float(corp["customer_demand_exposure_bn"]) * demand
    freight_security = (
        np.maximum(0, freight - 100) * float(corp["freight_cost_per_index_bn"])
        + duration * float(corp["security_cost_per_day_bn"])
    )
    working_capital = np.maximum(0, brent - baseline.brent_usd_bbl) * np.clip(
        rng.normal(float(corp["working_capital_per_brent_dollar_bn"]), 0.010, n),
        0.02,
        0.09,
    )

    base_profit = float(company["underlying_rc_profit_bn"])
    profit = np.maximum(
        0.25,
        base_profit
        + upstream_delta
        + gas_delta
        + refining_delta
        + trading_delta
        + inventory_delta
        - lost_volume
        - customer_loss
        - freight_security,
    )
    ocf = np.maximum(
        0.5,
        float(company["operating_cash_flow_bn"])
        + rng.normal(1.18, 0.08, n) * (profit - base_profit)
        - working_capital,
    )
    fcf = ocf - rng.normal(float(company["cash_capex_bn"]), 0.55, n)
    net_debt = np.maximum(
        5,
        float(company["net_debt_bn"])
        + working_capital
        - 0.22 * np.maximum(0, profit - base_profit),
    )

    base_price = baseline.bp_adr_price
    multiple_factor = np.exp(
        -rng.normal(float(val["risk_premium_multiplier"]), 0.10, n) * risk
        - 0.55 * demand
    )
    debt_factor = np.maximum(
        0.75,
        1
        - float(val["debt_penalty"])
        * (net_debt / float(company["net_debt_bn"]) - 1),
    )
    earnings_value = (
        base_price
        * (profit / base_profit)
        ** rng.normal(float(val["earnings_scaling_exponent"]), 0.05, n)
        * multiple_factor
        * debt_factor
    )
    base_fcf = float(company["operating_cash_flow_bn"]) - float(
        company["cash_capex_bn"]
    )
    fcf_ratio = np.maximum(0.10, fcf / base_fcf)
    fcf_value = (
        base_price
        * fcf_ratio ** rng.normal(float(val["fcf_scaling_exponent"]), 0.05, n)
        * np.exp(-0.85 * risk)
        * debt_factor
    )
    oil_beta = _bounded_normal(rng, float(val["oil_beta"]), 0.05, n, 0.10, 0.65)
    market_value = base_price * np.maximum(
        0.20,
        1
        + oil_beta * (brent / baseline.brent_usd_bbl - 1)
        + float(val["market_beta"]) * market_return
        + float(val["gas_beta"]) * (ttf / baseline.ttf_usd_mmbtu - 1)
        + float(val["refining_beta"])
        * (crack / baseline.composite_crack_usd_bbl - 1)
        + float(val["fx_pass_through"]) * fx_return
        - risk,
    )
    weights = rng.dirichlet(
        np.array(
            [
                float(val["earnings_weight"]),
                float(val["fcf_weight"]),
                float(val["market_weight"]),
            ]
        )
        * 45,
        size=n,
    )
    implied = (
        weights[:, 0] * earnings_value
        + weights[:, 1] * fcf_value
        + weights[:, 2] * market_value
    )
    # Epistemic/model-form uncertainty prevents transparent public-data
    # sensitivities from being treated as an internal company forecast.
    model_sigma = float(val["model_error_sigma"])
    implied *= rng.lognormal(-0.5 * model_sigma**2, model_sigma, n)
    implied = np.clip(implied, 4, 140)

    return {
        "implied_adr_value": implied,
        "brent_usd_bbl": brent,
        "ttf_usd_mmbtu": ttf,
        "crack_usd_bbl": crack,
        "net_income_bn": profit,
        "free_cash_flow_bn": fcf,
        "net_debt_bn": net_debt,
        "net_supply_gap_mbd": net_gap,
    }


def summarize_simulation(
    scenario: str, simulation: dict[str, np.ndarray], baseline_price: float
) -> dict[str, float | str]:
    values = simulation["implied_adr_value"]
    return {
        "scenario": scenario,
        "brent_median": float(np.median(simulation["brent_usd_bbl"])),
        "ttf_median": float(np.median(simulation["ttf_usd_mmbtu"])),
        "net_income_median_bn": float(np.median(simulation["net_income_bn"])),
        "fcf_median_bn": float(np.median(simulation["free_cash_flow_bn"])),
        "net_debt_median_bn": float(np.median(simulation["net_debt_bn"])),
        "p10": float(np.quantile(values, 0.10)),
        "median": float(np.median(values)),
        "p90": float(np.quantile(values, 0.90)),
        "probability_above_baseline": float(np.mean(values > baseline_price)),
    }


def _bounded_normal(
    rng: np.random.Generator,
    mean: float,
    std: float,
    size: int,
    lower: float,
    upper: float,
) -> np.ndarray:
    return np.clip(rng.normal(mean, std, size), lower, upper)
