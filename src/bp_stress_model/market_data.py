"""Pinned and optional live market observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import warnings

import pandas as pd


@dataclass(frozen=True)
class MarketBaseline:
    bp_adr_price: float
    brent_usd_bbl: float
    ttf_usd_mmbtu: float
    composite_crack_usd_bbl: float
    observed_at: str
    status: str
    notes: str


def _pinned(config: dict[str, Any]) -> MarketBaseline:
    market = config["market"]
    return MarketBaseline(
        bp_adr_price=float(market["bp_adr_price"]),
        brent_usd_bbl=float(market["brent_usd_bbl"]),
        ttf_usd_mmbtu=float(market["ttf_usd_mmbtu"]),
        composite_crack_usd_bbl=float(market["composite_crack_usd_bbl"]),
        observed_at=str(config["project"]["baseline_date"]),
        status="pinned",
        notes="Reproducible July 27, 2026 baseline.",
    )


def load_market_baseline(config: dict[str, Any], live: bool = False) -> MarketBaseline:
    """Load the reproducible baseline or attempt a non-destructive live refresh."""
    baseline = _pinned(config)
    if not live:
        return baseline

    try:
        import yfinance as yf

        bp_history = yf.download(
            "BP", period="7d", interval="1d", auto_adjust=True, progress=False
        )
        brent_history = yf.download(
            "BZ=F", period="7d", interval="1d", auto_adjust=True, progress=False
        )
        bp_price = _latest_close(bp_history, baseline.bp_adr_price)
        brent_price = _latest_close(brent_history, baseline.brent_usd_bbl)
        return MarketBaseline(
            bp_adr_price=bp_price,
            brent_usd_bbl=brent_price,
            ttf_usd_mmbtu=baseline.ttf_usd_mmbtu,
            composite_crack_usd_bbl=baseline.composite_crack_usd_bbl,
            observed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            status="partially_live",
            notes="BP ADR and Brent refreshed with yfinance; TTF and crack remain modeled references.",
        )
    except Exception as exc:
        warnings.warn(f"Live refresh failed; using pinned baseline ({exc}).")
        return MarketBaseline(
            **{
                **baseline.__dict__,
                "status": "pinned_fallback",
                "notes": f"Live refresh unavailable: {type(exc).__name__}.",
            }
        )


def _latest_close(frame: pd.DataFrame, fallback: float) -> float:
    if frame.empty or "Close" not in frame:
        return fallback
    series = frame["Close"]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    clean = pd.to_numeric(series, errors="coerce").dropna()
    return float(clean.iloc[-1]) if not clean.empty else fallback

