"""Production-parity challenger experiment; no production files are modified.

python validation/run_challengers.py --root . --out validation/results

B/C reuse the exact production simulation's common values and model-error
sample, exposed by instrumentation of an in-memory function copy. The direct
production function is also executed separately and compared draw by draw.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import numpy as np
import yaml

COMMIT = 'df298da3b38ab68e862f66d25986d2b2a3cfe808'
BLOBS = {
    'src/bp_stress_model/model.py': 'da2816d3411a76cd43a68d32afca52de6b8ee4ae',
    'src/bp_stress_model/market_data.py': '2e6226f2d9f66bbdc551d14706f2bbf3a5bc3bb3',
    'config/model_config.yaml': '3e76aba1faebfbfae4ddba67840803e19070f69b',
    'data/input/scenarios.csv': 'e6a92f84bed8a12c2e475cbe24758cbdadab474c',
    'outputs/tables/scenario_summary.csv': '128f630b8f9909d059bcc8c9248a1c4543c0eefa',
}
# Frozen, inherited experimental assumptions; NOT re-estimated here.
COEFFICIENTS = dict(xle_intercept=-0.00028, xle_market=0.941,
                    xle_brent=0.214, bp_xle=0.90, incremental_brent=0.08)
ATOL = 1e-12


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def save_csv(path, records):
    fields = list(dict.fromkeys(k for r in records for k in r))
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def make_trace_function(production, source):
    """Expose existing locals; never generate extra randomness or edit source."""
    function = next(n for n in ast.parse(source).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'monte_carlo')
    function.name = '_validation_monte_carlo'
    capture_count = 0
    body = []
    for statement in function.body:
        if (isinstance(statement, ast.AugAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == 'implied'
                and isinstance(statement.op, ast.Mult)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and statement.value.func.attr == 'lognormal'):
            body.append(ast.Assign(targets=[ast.Name(id='_model_error',ctx=ast.Store())],
                                   value=statement.value))
            statement.value = ast.Name(id='_model_error',ctx=ast.Load())
            capture_count += 1
        if isinstance(statement, ast.Return):
            names=['market_return','brent','ttf','crack','risk','weights',
                   'earnings_value','fcf_value','_model_error']
            statement.value.keys.append(ast.Constant(value='_trace'))
            statement.value.values.append(ast.Dict(
                keys=[ast.Constant(value=n) for n in names],
                values=[ast.Name(id=n,ctx=ast.Load()) for n in names]))
        body.append(statement)
    if capture_count != 1:
        raise ValueError('Unexpected production source structure; stop for review.')
    function.body = body
    module = ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    namespace = dict(production.__dict__)
    exec(compile(module, '<validation-only-in-memory-copy>', 'exec'), namespace)
    return namespace[function.name]


def alternatives(trace, config, baseline):
    c=COEFFICIENTS
    oil=trace['brent']/baseline.brent_usd_bbl-1
    gas=trace['ttf']/baseline.ttf_usd_mmbtu-1
    refining=trace['crack']/baseline.composite_crack_usd_bbl-1
    sector=c['xle_intercept']+c['xle_market']*trace['market_return']+c['xle_brent']*oil
    out={}
    for architecture,incremental in [('B',c['incremental_brent']),('C',0.0)]:
        market=baseline.bp_adr_price*np.maximum(
            0.20,1+c['bp_xle']*sector+incremental*oil
            +config['valuation']['gas_beta']*gas
            +config['valuation']['refining_beta']*refining-trace['risk'])
        values=(trace['weights'][:,0]*trace['earnings_value']
                +trace['weights'][:,1]*trace['fcf_value']
                +trace['weights'][:,2]*market)
        values*=trace['_model_error']
        out[architecture]=np.clip(values,4,140)
    return out


def evaluate(root, out):
    root=root.resolve(); out=out.resolve()
    protected=[root/'src',root/'config',root/'data/input',root/'outputs']
    if out==root or any(out==p or out.is_relative_to(p) for p in protected):
        raise ValueError('Refusing to write into production source/input/output paths.')
    source_hashes={}
    for name,expected in BLOBS.items():
        data=(root/name).read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if actual!=expected:
            raise ValueError(f'Frozen source changed: {name}; review before rerun.')
        source_hashes[name]={'git_blob':actual,'sha256':digest(data)}
    sys.path.insert(0,str(root/'src'))
    production=importlib.import_module('bp_stress_model.model')
    market_data=importlib.import_module('bp_stress_model.market_data')
    if Path(production.__file__).resolve()!=(root/'src/bp_stress_model/model.py').resolve():
        raise RuntimeError('Unexpected module; rerun in a clean process.')
    cfg=yaml.safe_load((root/'config/model_config.yaml').read_text())
    baseline=market_data.load_market_baseline(cfg,live=False)
    tracer=make_trace_function(production,(root/'src/bp_stress_model/model.py').read_text())
    canonical={r['scenario']:r for r in rows(root/'outputs/tables/scenario_summary.csv')}
    results=[]; checks=[]; hashes=[]
    n=cfg['simulation']['draws']; base_seed=cfg['simulation']['seed']
    for index,row in enumerate(rows(root/'data/input/scenarios.csv'),start=1):
        row={k:v if k in ('scenario','short_label','narrative') else float(v) for k,v in row.items()}
        seed=base_seed+index*101
        direct=production.monte_carlo(row,cfg,baseline,n,seed)
        captured=tracer(row,cfg,baseline,n,seed)
        for key in direct:
            np.testing.assert_array_equal(direct[key],captured[key])
        values={'A':direct['implied_adr_value'],**alternatives(captured['_trace'],cfg,baseline)}
        summary=production.summarize_simulation(row['scenario'],direct,baseline.bp_adr_price)
        error=max(abs(float(value)-float(canonical[row['scenario']][key]))
                  for key,value in summary.items() if key!='scenario')
        if error>ATOL:
            raise AssertionError(f'Published summary parity failed: {error}')
        checks.append(dict(scenario=row['scenario'],scenario_index=index,seed=seed,draws=n,
                           direct_vs_trace_max_abs_diff=0.0,published_summary_max_abs_diff=error,status='PASS'))
        for architecture,array in values.items():
            if not np.isfinite(array).all() or np.any(array<4) or np.any(array>140):
                raise AssertionError('Invalid simulation output')
            q=np.quantile(array,[.1,.5,.9])
            record=dict(scenario=row['scenario'],architecture=architecture,seed=seed,draws=n,
                        p10=float(q[0]),median=float(q[1]),p90=float(q[2]),
                        probability_above_baseline=float(np.mean(array>baseline.bp_adr_price)))
            if architecture!='A':
                diff=array-values['A']
                record.update(median_pct_change_vs_A=100*(q[1]/np.median(values['A'])-1),
                  mean_abs_dollar_diff_vs_A=float(np.mean(np.abs(diff))),
                  share_abs_diff_gt_1usd_vs_A=float(np.mean(np.abs(diff)>1)),
                  share_abs_pct_diff_gt_2pct_vs_A=float(np.mean(np.abs(diff/values['A'])>.02)),
                  correlation_with_A=float(np.corrcoef(values['A'],array)[0,1]))
            results.append(record)
            hashes.append(dict(scenario=row['scenario'],architecture=architecture,
                               sha256_float64_le=digest(np.asarray(array,dtype='<f8').tobytes())))
    out.mkdir(parents=True,exist_ok=True)
    save_csv(out/'paired_results.csv',results)
    save_csv(out/'production_parity.csv',checks)
    save_csv(out/'draw_hashes.csv',hashes)
    report=dict(experiment_version='0.2',production_commit=COMMIT,status='PASS',
                draws_compared=5*n,production_arrays_compared=5*8,
                max_direct_vs_trace_diff=0.0,
                max_published_summary_diff=max(r['published_summary_max_abs_diff'] for r in checks),
                numeric_atol=ATOL,seed_rule='base_seed + 101 * one_based_index',
                coefficients=COEFFICIENTS,
                coefficient_status='Inherited experimental assumptions; calibration not re-estimated here.',
                source_hashes=source_hashes,
                environment=dict(python=sys.version,platform=platform.platform(),
                  packages={p:importlib.metadata.version(p) for p in ['numpy','pandas','PyYAML']}),
                output_sha256={name:digest((out/name).read_bytes())
                  for name in ['paired_results.csv','production_parity.csv','draw_hashes.csv']},
                review_scope='Computational parity and same-environment repeatability, not independent scientific validation.')
    (out/'run_manifest.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'results')
    args=parser.parse_args()
    print(json.dumps(evaluate(args.root,args.out),indent=2))

if __name__=='__main__':
    main()
