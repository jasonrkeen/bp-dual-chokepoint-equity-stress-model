> This file mirrors `.github/copilot-instructions.md` and `CLAUDE.md`; keep all three in sync when any changes.

# AGENTS.md — bp-dual-chokepoint-equity-stress-model

## Purpose
Monte Carlo equity stress model for BP under Hormuz and Red Sea disruption scenarios.

## Tech stack
- Python; dependencies in `requirements.txt`
- Key libraries: `numpy`, `pandas`, `matplotlib`, `PyYAML`, `reportlab`, `requests`, `yfinance`

## Folder structure
- `.github/` (1 files)
- `config/` (1 files)
- `data/` (3 files)
- `docs/` (1 files)
- `outputs/` (12 files)
- `src/` (7 files)
- `tests/` (1 files)
- `CITATION.cff`
- `README.md`
- `main.py`
- `methodology.md`
- `requirements.txt`

## Setup, run, test
Commands documented in README.md (referenced files exist):
```bash
python -m pip install -r requirements.txt
python main.py
python3 -m venv .venv
python main.py --live
python main.py --draws 20000 --seed 20260727
python -m unittest discover -s tests -v
```
- Tests: 1 Python test file(s) under `tests/`; framework appears to be unittest. Add/update tests with any logic change.
- CI workflows exist in `.github/workflows/`; keep them passing.

## Conventions observed
- Functions use type hints; keep annotating new code.
- Uses `dataclasses` for structured config/results.
- Config lives in: `config/model_config.yaml`, `src/bp_stress_model/config.py`; avoid hardcoding parameters elsewhere.
- Random seeds are set for reproducibility (Monte Carlo/simulation); keep seeded, deterministic runs.
- Public data sources referenced: FRED, EIA, yfinance.
- Write paths relative to the repo root (no absolute local paths).

## Output artifacts
- Generated outputs go to: `outputs/charts/`, `outputs/pdf/`, `outputs/tables/`
- A PDF report is produced with `reportlab`; keep it in sync with model changes.
- Charts are generated with matplotlib.

## Guardrails
- Never commit secrets, API keys, tokens, or `.env` files.
- Do not commit large raw datasets or binaries; keep data fetched or documented with its source.
- Keep analysis source-backed: cite data sources and assumptions; label scenario/forecast outputs as model estimates, not facts.
- Preserve reproducibility: no unseeded randomness, no hidden manual steps.
