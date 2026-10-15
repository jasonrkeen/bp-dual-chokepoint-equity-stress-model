# Experimental production-parity validation

Start with [the review and limitations](../docs/production_parity_review.md).

`run_challengers.py` reproduces the production seed policy and compares two frozen market-factor variants without editing `src/`, `config/`, `data/input/`, or `outputs/`. It checks source hashes before execution. The pinned production reference is commit `df298da3b38ab68e862f66d25986d2b2a3cfe808`.

```bash
python -m pip install -r validation/requirements-lock.txt
python validation/run_challengers.py --root . --out validation/rerun_results
python -m unittest discover -s validation -p test_parity.py -v
```

`results/` stores the reviewed run. Regenerate into `rerun_results/` for comparison, not over the stored record. `run_manifest.json` records package versions, source hashes, and output hashes. SHA-256 draw hashes use little-endian float64 byte arrays.

The dependencies pin the tested Python 3.13.5 environment's NumPy, pandas, and PyYAML versions. Identical results on another numerical stack or platform are not guaranteed. This is an experimental computational audit, not a forecast, investment recommendation, or independent economic validation.
