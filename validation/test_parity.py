"""Computational regression tests; not empirical or economic validation."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import numpy as np
import yaml

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('BP_PARITY_ROOT',HERE.parent)).resolve()
sys.path.insert(0,str(HERE))
import run_challengers as validation
sys.path.insert(0,str(ROOT/'src'))
from bp_stress_model import model,market_data

class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=yaml.safe_load((ROOT/'config/model_config.yaml').read_text())
        cls.baseline=market_data.load_market_baseline(cls.config)
        cls.rows=[{k:v if k in ('scenario','short_label','narrative') else float(v)
                   for k,v in r.items()} for r in validation.rows(ROOT/'data/input/scenarios.csv')]
        cls.tracer=staticmethod(validation.make_trace_function(model,(ROOT/'src/bp_stress_model/model.py').read_text()))

    def test_frozen_source_blobs(self):
        import hashlib
        for name,expected in validation.BLOBS.items():
            content=(ROOT/name).read_bytes()
            observed=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
            self.assertEqual(expected,observed,name)

    def test_scenario_order_and_seed_schedule(self):
        self.assertEqual([r['scenario'] for r in self.rows],[
            'Diplomatic De-escalation','Extended Hormuz Constraint','Dual-Chokepoint Crisis',
            'Product and LNG Squeeze','Demand Destruction Threshold'])
        self.assertEqual([self.config['simulation']['seed']+i*101 for i in range(1,6)],
                         [20260828,20260929,20261030,20261131,20261232])

    def test_direct_and_instrumented_arrays_are_identical(self):
        for i,row in enumerate(self.rows,1):
            seed=self.config['simulation']['seed']+i*101
            direct=model.monte_carlo(row,self.config,self.baseline,1000,seed)
            traced=self.tracer(row,self.config,self.baseline,1000,seed)
            for key in direct:
                np.testing.assert_array_equal(direct[key],traced[key])

    def test_correct_seed_reproduces_published_summary(self):
        expected={r['scenario']:r for r in validation.rows(ROOT/'outputs/tables/scenario_summary.csv')}
        for i,row in enumerate(self.rows,1):
            result=model.monte_carlo(row,self.config,self.baseline,10000,20260727+i*101)
            summary=model.summarize_simulation(row['scenario'],result,self.baseline.bp_adr_price)
            for key,value in summary.items():
                if key!='scenario':
                    self.assertLessEqual(abs(value-float(expected[row['scenario']][key])),validation.ATOL)

    def test_legacy_seed_does_not_falsely_pass_canonical_parity(self):
        row=self.rows[0]
        a=model.monte_carlo(row,self.config,self.baseline,10000,20260727)
        b=model.monte_carlo(row,self.config,self.baseline,10000,20260828)
        self.assertFalse(np.array_equal(a['implied_adr_value'],b['implied_adr_value']))
        self.assertGreater(abs(np.median(a['implied_adr_value'])-np.median(b['implied_adr_value'])),validation.ATOL)

    def test_b_c_preserve_direct_brent_sign(self):
        for i,row in enumerate(self.rows,1):
            traced=self.tracer(row,self.config,self.baseline,1000,20260727+i*101)
            alternatives=validation.alternatives(traced['_trace'],self.config,self.baseline)
            oil=traced['brent_usd_bbl']/self.baseline.brent_usd_bbl-1
            self.assertTrue(np.all((alternatives['B']-alternatives['C'])*oil>=-validation.ATOL))

    def test_outputs_finite_and_bounded(self):
        for i,row in enumerate(self.rows,1):
            traced=self.tracer(row,self.config,self.baseline,1000,20260727+i*101)
            for array in validation.alternatives(traced['_trace'],self.config,self.baseline).values():
                self.assertTrue(np.isfinite(array).all())
                self.assertTrue(np.all((array>=4)&(array<=140)))

    def test_production_overwrite_refused(self):
        with self.assertRaises(ValueError):
            validation.evaluate(ROOT,ROOT/'outputs')

if __name__=='__main__':
    unittest.main()
