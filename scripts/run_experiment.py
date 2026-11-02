#!/usr/bin/env python3
"""Run an unchanged reference-case experiment from its expected working directory.

This is a convenience launcher, not a replacement for the paper's original models.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = {
    'a':'experiments/verify_s0_158_sequential.py',
    'b':'experiments/integrated_capex_control/run_integrated_capex_only.py',
    'd':'experiments/fixed_investment_opex_control/run_fixed_investment_opex.py',
    'd-export':'experiments/integrated_consistency_validation/export_model_d_solution.py',
    'c':'experiments/integrated_consistency_validation/final_model_equivalence_fix/run_integrated_corrected.py',
    'forced':'experiments/forced_compressor_counterfactual_v2.py',
    'growth':'experiments/run_growth_sensitivity.py',
    'leadtime':'experiments/run_leadtime_sensitivity.py',
    'storage':'experiments/run_s0_sensitivity_screening.py',
}

def latest_d_pair():
    directory=ROOT/'experiments/integrated_consistency_validation'
    # Pair CSV and JSON using their identical timestamp; prefer latest available.
    pairs=[]
    for csvfile in directory.glob('model_d_hourly_solution_*.csv'):
        stamp=csvfile.stem.split('model_d_hourly_solution_',1)[1]
        meta=directory/f'model_d_solution_export_{stamp}.json'
        if meta.exists():pairs.append((csvfile.stat().st_mtime,csvfile,meta))
    if not pairs:return None
    _,csvfile,meta=max(pairs)
    return csvfile,meta

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('experiment', choices=MAP)
    ap.add_argument('extra', nargs=argparse.REMAINDER, help='Optional source script args, after --')
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    data=ROOT/'data/processed/representative_weeks_FixedEP_W10_FINAL.csv'
    if not data.exists():
        ap.error('Restricted representative-week CSV missing; see data/processed/README.md')
    src=ROOT/MAP[args.experiment]
    env=os.environ.copy()
    if args.experiment == 'c':
        pair=latest_d_pair()
        if not pair: ap.error('C+ requires Model D 8400-hour CSV + matching summary. Run d-export first.')
        csvfile,metadata=pair
        env['HRS_MODEL_D_SOLUTION_FILE']=str(csvfile)
        env['HRS_MODEL_D_SUMMARY_FILE']=str(metadata)
    # relative paths in original scientific scripts are rooted at their script directory
    cmd=[sys.executable,str(src)]+[x for x in args.extra if x!='--']
    print('Running:', ' '.join(cmd), flush=True)
    print('Working directory:',src.parent,flush=True)
    if args.dry_run:return
    proc=subprocess.run(cmd,cwd=src.parent,env=env)
    raise SystemExit(proc.returncode)

if __name__=='__main__':main()
