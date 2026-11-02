#!/usr/bin/env python3
"""Offline checks of recorded outputs; optional authorized empirical-input check."""
import argparse, json,hashlib,sys,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REC=ROOT/'results/reference/paper_reference_case.json'
DATA=ROOT/'data/processed/representative_weeks_FixedEP_W10_FINAL.csv'
EXPECTED='f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef'

def close(a,b,abs_tol=0.0001):return abs(float(a)-float(b))<=abs_tol

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',action='store_true',help='Require authorized input and verify its SHA256, shape and weights')
    args=p.parse_args()
    r=json.loads(REC.read_text(encoding='utf-8'))
    A,B,D,C=r['A'],r['B'],r['D'],r['C_plus']
    assert close(B['capex']-A['screened_capex'],256.25,0.01)
    assert close(D['fixed_capex']+D['opex'],D['total'])
    assert close(C['capex']+C['opex'],C['total'])
    assert C['best_bound'] <= C['total'] and C['gap_percent'] > 0
    assert r['source_data_sha256']==EXPECTED
    corrected=json.loads((ROOT/'experiments/integrated_consistency_validation/final_model_equivalence_fix/integrated_corrected_result_20261030_131154.json').read_text(encoding='utf-8'))
    assert close(corrected['costs']['total_万元'],C['total'],1e-6)
    assert close(corrected['solver']['best_bound']/10000,C['best_bound'],1e-6)
    assert close(corrected['solver']['gap']*100,C['gap_percent'],1e-6)
    print('[OK] Recorded scalar result consistency checks; NOT a solver rerun.')
    if args.input:
        if not DATA.exists():raise SystemExit('Missing private data: '+str(DATA))
        h=hashlib.sha256(DATA.read_bytes()).hexdigest()
        if h!=EXPECTED:raise SystemExit(f'Empirical input SHA256 mismatch: {h}')
        with DATA.open(newline='',encoding='utf-8-sig') as stream:
            reader=csv.DictReader(stream)
            needed={'hour','demand_kg','service_minutes','representative_week_id','weight'}
            assert needed<=set(reader.fieldnames),f'Missing columns: {needed-set(reader.fieldnames)}'
            rows=list(reader)
        assert len(rows)==1680,f'Expected 1680 rows, got {len(rows)}'
        from collections import Counter
        counts=Counter(int(row['representative_week_id']) for row in rows)
        assert counts=={i:168 for i in range(1,11)},counts
        weights={i:{float(row['weight']) for row in rows if int(row['representative_week_id'])==i} for i in range(1,11)}
        assert [list(weights[i])[0] for i in range(1,11)] == [1,1,1,1,1,7,14,12,4,10], weights
        print('[OK] Authorized empirical CSV hash, rows, IDs, weights verified.')
    else:
        print('[INFO] No confidential input inspected; run --input to verify an authorized copy.')

if __name__=='__main__':main()
