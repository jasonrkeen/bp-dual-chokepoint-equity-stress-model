"""Generate the executive PDF with ReportLab."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.font_manager import FontProperties, findfont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .market_data import MarketBaseline

GREEN = colors.HexColor("#16794F")
DARK = colors.HexColor("#17342D")
LIME = colors.HexColor("#9BC53D")
TEAL = colors.HexColor("#2B9A8B")
RED = colors.HexColor("#C64B45")
LIGHT = colors.HexColor("#EAF3EF")
MUTED = colors.HexColor("#50665E")
LINE = colors.HexColor("#D6E2DD")

def _register_portable_fonts() -> tuple[str, str]:
    """Embed Matplotlib's bundled DejaVu fonts on Windows, macOS, or Linux."""
    regular_name = "DejaVuSans"
    bold_name = "DejaVuSans-Bold"
    try:
        regular_path = findfont(
            FontProperties(family=["DejaVu Sans"], weight="normal"),
            fallback_to_default=True,
        )
        bold_path = findfont(
            FontProperties(family=["DejaVu Sans"], weight="bold"),
            fallback_to_default=True,
        )
        pdfmetrics.registerFont(TTFont(regular_name, regular_path))
        pdfmetrics.registerFont(TTFont(bold_name, bold_path))
        return regular_name, bold_name
    except Exception:
        # ReportLab's core fonts provide a safe final fallback if a local font
        # cache is unavailable.
        return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_portable_fonts()


def generate_pdf(
    output: Path,
    summaries: pd.DataFrame,
    deterministic: pd.DataFrame,
    charts: dict[str, Path],
    config: dict[str, Any],
    baseline: MarketBaseline,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        str(output),
        pagesize=LETTER,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.48 * inch,
        title=config["project"]["title"],
        author=config["project"]["author"],
    )
    story: list[Any] = []

    best = summaries.loc[summaries["median"].idxmax()]
    threshold = summaries.loc[
        summaries["scenario"].eq("Demand Destruction Threshold")
    ].iloc[0]
    dual = summaries.loc[summaries["scenario"].eq("Dual-Chokepoint Crisis")].iloc[0]

    story.extend(
        [
            Paragraph("BP DUAL-CHOKEPOINT", styles["eyebrow"]),
            Paragraph("Energy Shock Equity Stress Model", styles["title"]),
            Paragraph(
                "A scenario-based assessment of simultaneous Strait of Hormuz and "
                "Bab al-Mandeb disruption, refined-product pressure, LNG scarcity, "
                "and demand destruction.",
                styles["subtitle"],
            ),
            Spacer(1, 0.18 * inch),
            Paragraph(
                f"Market baseline: {config['project']['baseline_date']}  |  "
                f"BP ADR ${baseline.bp_adr_price:.2f}  |  "
                f"Brent ${baseline.brent_usd_bbl:.2f}/bbl",
                styles["baseline"],
            ),
            Spacer(1, 0.28 * inch),
            Paragraph("Executive judgment", styles["h2"]),
            Paragraph(
                "BP benefits initially from higher oil and gas realizations, tighter "
                "refining margins, and trading optionality. The benefit is nonlinear "
                "and conditional. A long dual-chokepoint disruption increases freight, "
                "security and working-capital costs while raising the probability of "
                "volume loss, demand destruction, balance-sheet pressure, and "
                "valuation-multiple compression.",
                styles["body"],
            ),
            Spacer(1, 0.20 * inch),
            _metric_cards(
                [
                    ("Highest median scenario", f"${best['median']:.2f}", best["scenario"]),
                    (
                        "Demand-threshold median",
                        f"${threshold['median']:.2f}",
                        f"P(>base) {threshold['probability_above_baseline']:.1%}",
                    ),
                    (
                        "Dual-crisis probability",
                        f"{dual['probability_above_baseline']:.1%}",
                        "above baseline",
                    ),
                ],
                styles,
            ),
            Spacer(1, 0.23 * inch),
            Image(str(charts["scenario_ranges"]), width=7.25 * inch, height=3.93 * inch),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("Scenario results", styles["h1"]),
            Paragraph(
                "Each distribution is conditional on the specified scenario. It does "
                "not estimate the probability that the geopolitical scenario itself "
                "will occur.",
                styles["note"],
            ),
            Spacer(1, 0.12 * inch),
            _scenario_table(summaries, styles),
            Spacer(1, 0.24 * inch),
            Image(str(charts["probabilities"]), width=7.15 * inch, height=3.82 * inch),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("Why BP's response becomes nonlinear", styles["h1"]),
            _channel_table(styles),
            Spacer(1, 0.18 * inch),
            Image(str(charts["waterfall"]), width=7.2 * inch, height=3.67 * inch),
            Paragraph(
                "The waterfall shows the transparent central assumptions for the "
                "dual-chokepoint case. Monte Carlo results add uncertainty around "
                "physical losses, capture rates, trading, working capital, market "
                "returns, valuation weights, and risk-premium compression.",
                styles["note"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("Threshold map", styles["h1"]),
            Image(str(charts["threshold"]), width=6.85 * inch, height=4.72 * inch),
            Paragraph(
                "The dark boundary marks the modeled combination at which BP's "
                "deterministic ADR value crosses the current-share-price baseline. "
                "All other assumptions are held at the dual-crisis reference case, "
                "including 9% demand destruction and a 12% equity risk premium.",
                styles["body"],
            ),
            PageBreak(),
            Paragraph("Sensitivity and interpretation", styles["h1"]),
            Image(str(charts["sensitivity"]), width=6.75 * inch, height=4.08 * inch),
            Spacer(1, 0.14 * inch),
            Paragraph(
                "Hormuz severity is the largest one-at-a-time driver because it "
                "changes both physical crude availability and BP's realized-price "
                "benefit. Demand destruction and the equity risk premium work in the "
                "opposite direction. Bab al-Mandeb has a smaller direct physical "
                "effect because rerouting is possible, but it remains important through "
                "freight, insurance, delays, and refining logistics.",
                styles["body"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            Paragraph("Method and limitations", styles["h1"]),
            Paragraph(
                "<b>Physical supply layer.</b> Gross Hormuz oil disruption is combined "
                "with effective Bab al-Mandeb losses and Russian product losses, then "
                "reduced by available bypass capacity, policy releases, and demand "
                "response.",
                styles["body"],
            ),
            Paragraph(
                "<b>Market layer.</b> A convex short-run supply-gap function estimates "
                "Brent. LNG interruption affects a TTF reference price, while product "
                "losses, logistics pressure, and demand destruction affect a composite "
                "refining crack spread.",
                styles["body"],
            ),
            Paragraph(
                "<b>Corporate layer.</b> Commodity prices flow through BP's upstream, "
                "gas/LNG, refining, trading, customer, volume, freight, security, and "
                "working-capital channels. Trading is bounded because public reporting "
                "cannot reproduce BP's internal positions.",
                styles["body"],
            ),
            Paragraph(
                "<b>Valuation layer.</b> The implied ADR value is an ensemble of "
                "earnings-scaling, free-cash-flow, and market-factor estimates, with "
                "net-debt, GBP/USD, and risk-premium effects. Each scenario uses "
                f"{int(config['simulation']['draws']):,} Monte Carlo draws.",
                styles["body"],
            ),
            Spacer(1, 0.10 * inch),
            Paragraph("Important limitations", styles["h2"]),
            Paragraph(
                "This is a transparent research stress test, not BP's internal planning "
                "model, an event forecast, or investment advice. Scenario probabilities "
                "are not assigned. Public segment disclosures cannot identify trading "
                "books, cargo-level exposure, hedges, tax effects, or asset outages in "
                "real time. Results should be recalibrated as filings and event data "
                "change.",
                styles["body"],
            ),
            Spacer(1, 0.12 * inch),
            Paragraph("Primary sources", styles["h2"]),
            Paragraph(
                "- BP - 2025 results, 2025 Annual Report and Form 20-F, and Q1 2026 results.<br/>"
                "- U.S. EIA - Hormuz chokepoint, Red Sea shipping, and LNG disruption analyses.<br/>"
                "- Reuters - July 27, 2026 oil-market and Hormuz traffic update.<br/>"
                "- FRED and yfinance - optional live market observations when available.",
                styles["source"],
            ),
            Spacer(1, 0.18 * inch),
            Paragraph(
                f"Model version {config['project']['model_version']}  |  "
                f"Author: {config['project']['author']}  |  "
                f"Baseline status: {baseline.status}",
                styles["footer_note"],
            ),
        ]
    )

    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return output


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=sample["Normal"], fontSize=11, leading=13,
            textColor=GREEN, fontName=FONT_BOLD, spaceAfter=5
        ),
        "title": ParagraphStyle(
            "title", parent=sample["Title"], fontSize=27, leading=30,
            textColor=DARK, alignment=TA_LEFT, fontName=FONT_BOLD, spaceAfter=8
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=sample["Normal"], fontSize=11.2, leading=16,
            textColor=MUTED, fontName=FONT_REGULAR, spaceAfter=6
        ),
        "baseline": ParagraphStyle(
            "baseline", parent=sample["Normal"], fontSize=9.5, leading=12,
            textColor=colors.white, fontName=FONT_REGULAR, backColor=GREEN, borderPadding=8
        ),
        "h1": ParagraphStyle(
            "h1", parent=sample["Heading1"], fontSize=19, leading=22,
            textColor=DARK, fontName=FONT_BOLD, spaceAfter=10
        ),
        "h2": ParagraphStyle(
            "h2", parent=sample["Heading2"], fontSize=13, leading=16,
            textColor=GREEN, fontName=FONT_BOLD, spaceBefore=4, spaceAfter=5
        ),
        "body": ParagraphStyle(
            "body", parent=sample["BodyText"], fontSize=9.4, leading=13.2,
            textColor=DARK, fontName=FONT_REGULAR, spaceAfter=7
        ),
        "note": ParagraphStyle(
            "note", parent=sample["BodyText"], fontSize=8.2, leading=11,
            textColor=MUTED, fontName=FONT_REGULAR, spaceAfter=5
        ),
        "source": ParagraphStyle(
            "source", parent=sample["BodyText"], fontSize=8.1, leading=11.5,
            textColor=DARK, fontName=FONT_REGULAR
        ),
        "card_label": ParagraphStyle(
            "card_label", parent=sample["Normal"], fontSize=7.7, leading=9,
            textColor=MUTED, fontName=FONT_REGULAR, alignment=TA_CENTER
        ),
        "card_value": ParagraphStyle(
            "card_value", parent=sample["Normal"], fontSize=17, leading=19,
            textColor=GREEN, fontName=FONT_BOLD, alignment=TA_CENTER
        ),
        "card_note": ParagraphStyle(
            "card_note", parent=sample["Normal"], fontSize=7, leading=8,
            textColor=MUTED, fontName=FONT_REGULAR, alignment=TA_CENTER
        ),
        "table_header": ParagraphStyle(
            "table_header", parent=sample["Normal"], fontSize=7.1, leading=8,
            textColor=colors.white, fontName=FONT_BOLD, alignment=TA_CENTER
        ),
        "table_cell": ParagraphStyle(
            "table_cell", parent=sample["Normal"], fontSize=7.2, leading=8.5,
            textColor=DARK, fontName=FONT_REGULAR, alignment=TA_CENTER
        ),
        "table_left": ParagraphStyle(
            "table_left", parent=sample["Normal"], fontSize=7.2, leading=8.5,
            textColor=DARK, fontName=FONT_REGULAR, alignment=TA_LEFT
        ),
        "footer_note": ParagraphStyle(
            "footer_note", parent=sample["Normal"], fontSize=7.5, leading=9,
            textColor=MUTED, fontName=FONT_REGULAR, alignment=TA_CENTER
        ),
    }


def _metric_cards(items: list[tuple[str, str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    cells = []
    for label, value, note in items:
        cells.append(
            [
                Paragraph(label, styles["card_label"]),
                Paragraph(value, styles["card_value"]),
                Paragraph(note, styles["card_note"]),
            ]
        )
    table = Table(
        [[Table([[item] for item in cell], colWidths=[2.22 * inch]) for cell in cells]],
        colWidths=[2.32 * inch] * 3,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _scenario_table(frame: pd.DataFrame, styles: dict[str, ParagraphStyle]) -> Table:
    headers = [
        "Scenario", "Brent", "TTF", "Net income", "P10", "Median", "P90", "Above base"
    ]
    data = [[Paragraph(item, styles["table_header"]) for item in headers]]
    for _, row in frame.iterrows():
        data.append(
            [
                Paragraph(str(row["scenario"]), styles["table_left"]),
                Paragraph(f"${row['brent_median']:.0f}", styles["table_cell"]),
                Paragraph(f"${row['ttf_median']:.1f}", styles["table_cell"]),
                Paragraph(f"${row['net_income_median_bn']:.1f}B", styles["table_cell"]),
                Paragraph(f"${row['p10']:.2f}", styles["table_cell"]),
                Paragraph(f"${row['median']:.2f}", styles["table_cell"]),
                Paragraph(f"${row['p90']:.2f}", styles["table_cell"]),
                Paragraph(f"{row['probability_above_baseline']:.1%}", styles["table_cell"]),
            ]
        )
    table = Table(
        data,
        colWidths=[1.50 * inch, 0.62 * inch, 0.55 * inch, 0.76 * inch, 0.65 * inch, 0.70 * inch, 0.65 * inch, 0.78 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _channel_table(styles: dict[str, ParagraphStyle]) -> Table:
    positive = (
        "<b>Positive channels</b><br/>"
        "Higher crude realizations<br/>"
        "Higher international gas and LNG prices<br/>"
        "Tighter refining margins<br/>"
        "Trading optionality and inventory gains<br/>"
        "Geographic upstream diversification"
    )
    negative = (
        "<b>Negative channels</b><br/>"
        "Cargo delays and potential volume losses<br/>"
        "Freight, insurance and security costs<br/>"
        "Working-capital requirements and net debt<br/>"
        "Customer demand destruction<br/>"
        "Recession and equity-risk-premium expansion"
    )
    table = Table(
        [[Paragraph(positive, styles["body"]), Paragraph(negative, styles["body"])]],
        colWidths=[3.38 * inch, 3.38 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), LIGHT),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8ECEB")),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _page(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    width, height = LETTER
    canvas.setStrokeColor(LINE)
    canvas.line(0.55 * inch, 0.35 * inch, width - 0.55 * inch, 0.35 * inch)
    canvas.setFont(FONT_REGULAR, 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.55 * inch, 0.20 * inch, "BP Dual-Chokepoint Energy Shock Equity Stress Model")
    canvas.drawRightString(width - 0.55 * inch, 0.20 * inch, f"Page {doc.page}")
    canvas.restoreState()
