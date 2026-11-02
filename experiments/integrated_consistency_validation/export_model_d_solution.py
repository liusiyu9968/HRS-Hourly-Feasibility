"""
Export Model D (Fixed-Investment OPEX Minimization) Complete Solution
====================================================================

Purpose:
- Re-run Model D with identical configuration
- Export complete hourly operational solution (67,200 values)
- Enable subsequent Integrated constraint feasibility verification

Scientific Integrity:
- Use EXACT same script as original run (experiments/fixed_investment_opex_control/run_fixed_investment_opex.py)
- Verify Status=9, ObjVal=39999163.38元 (reproducibility)
- Export to CSV for constraint verification
- Do NOT modify any model constraints or parameters
"""

import sys
import os
import json
import hashlib
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB
from datetime import datetime

# Add project root to path
sys.path.insert(0, '../../data/parameters')
from unified_params import get_params

# ============================================================================
# CONFIGURATION
# ============================================================================

EXPERIMENT_NAME = "model_d_solution_export"
DATA_FILE = "../../data/processed/representative_weeks_FixedEP_W10_FINAL.csv"
EXPECTED_DATA_HASH = "f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef"

# Model B investment path (LOCKED)
MODEL_B_REFERENCE = {
    "capex": 6355418.381344307,
    "capex_万元": 635.5418381344307,
    "investments": [
        {"period": 1, "asset": "C", "capacity": 50, "cost": 1400000},
        {"period": 2, "asset": "S", "capacity": 200, "cost": 1400000},
        {"period": 2, "asset": "K", "capacity": 120, "cost": 2100000},
        {"period": 3, "asset": "C", "capacity": 100, "cost": 2000000}
    ],
    "capacity_trajectory": {
        1: {"C": 100, "S": 158, "K": 120},
        2: {"C": 150, "S": 158, "K": 120},
        3: {"C": 150, "S": 358, "K": 240},
        4: {"C": 250, "S": 358, "K": 240},
        5: {"C": 250, "S": 358, "K": 240}
    }
}

# Fixed capacity parameters from Model B
C_FIXED = {1: 100, 2: 150, 3: 150, 4: 250, 5: 250}  # kg/h
S_FIXED = {1: 158, 2: 158, 3: 358, 4: 358, 5: 358}  # kg
K_FIXED = {1: 120, 2: 120, 3: 240, 4: 240, 5: 240}  # min/h

# ============================================================================
# DATA VERIFICATION
# ============================================================================

def compute_sha256(file_path):
    """Compute SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

print("\n" + "="*80)
print("MODEL D SOLUTION EXPORT")
print("="*80)

# Verify data file
data_hash = compute_sha256(DATA_FILE)
print(f"\n[DATA] Data file: {DATA_FILE}")
print(f"   SHA256: {data_hash}")
if data_hash == EXPECTED_DATA_HASH:
    print("   [OK] VERIFIED (matches Model B/D reference)")
else:
    print(f"   [ERROR] MISMATCH! Expected: {EXPECTED_DATA_HASH}")
    sys.exit(1)

# ============================================================================
# LOAD DATA & PARAMETERS
# ============================================================================

print("\n[LOAD] Loading representative weeks data...")
df = pd.read_csv(DATA_FILE)
print(f"   Loaded {len(df)} rows")

# Group by representative_week_id
weeks_data = {}
for week_id in range(1, 11):
    week_df = df[df['representative_week_id'] == week_id].copy()
    week_df = week_df.sort_values('hour').reset_index(drop=True)

    if len(week_df) != 168:
        print(f"   [ERROR] Week {week_id}: Expected 168 hours, got {len(week_df)}")
        sys.exit(1)

    # Calculate G_peak (peak service time requirement in minutes)
    G_peak = week_df['service_minutes'].max()

    weeks_data[week_id] = {
        'demand_kg': week_df['demand_kg'].values,
        'G_peak': G_peak
    }

print(f"   [OK] Loaded {len(weeks_data)} representative weeks")

# Load parameters from unified_params
base_params = get_params(case='central')

# Add additional parameters for Model Freeze v1.0
p = {
    **base_params,
    'growth_rate': 0.15,  # 15% CAGR
    'LT': 1,  # 1-year lead time
    's0': 158,  # Initial storage (override)
    'W': 10,  # 10 representative weeks
    'H': 168,  # 168 hours per week
    'omega': [1, 1, 1, 1, 1, 7, 14, 12, 4, 10],  # Weekly weights
    'rho': None  # Will compute from growth_rate
}

print(f"\n[PARAMS] Parameters:")
print(f"   Growth rate: {p['growth_rate']*100}%")
print(f"   Lead time: {p['LT']} year")
print(f"   Initial storage: {p['s0']} kg")
print(f"   Discount rate: {p['discount_rate']*100}%")
print(f"   Planning horizon: T=5 years")
print(f"   Representative weeks: W={p['W']}")
print(f"   Hours per week: H={p['H']}")

# ============================================================================
# BUILD MODEL
# ============================================================================

print("\n[BUILD] Building Model D (Fixed-Investment OPEX Minimization)...")

T = 5
m = gp.Model("Model_D_Solution_Export")
m.setParam('TimeLimit', 1800)
m.setParam('MIPGap', 0.001)
m.setParam('OutputFlag', 1)

# Growth multipliers
rho = [1.0]
for t in range(1, T):
    rho.append(rho[-1] * (1 + p['growth_rate']))

print(f"   Growth multipliers: {[f'{r:.4f}' for r in rho]}")

# Verify fixed capacities match Model B
print(f"\n[VERIFY] Fixed capacity trajectory (from Model B):")
for t in range(1, T+1):
    ref_cap = MODEL_B_REFERENCE["capacity_trajectory"][t]
    assert C_FIXED[t] == ref_cap["C"], f"C mismatch at t={t}"
    assert S_FIXED[t] == ref_cap["S"], f"S mismatch at t={t}"
    assert K_FIXED[t] == ref_cap["K"], f"K mismatch at t={t}"
    print(f"   Period {t}: C={C_FIXED[t]} kg/h, S={S_FIXED[t]} kg, K={K_FIXED[t]} min/h")

# ============================================================================
# DECISION VARIABLES (Operational only, no investment)
# ============================================================================

print("\n[VARS] Creating operational variables...")

a_arr = {}
a_dep = {}
z = {}
I_trailer = {}
Q_depart = {}
q_comp = {}
I_HP = {}
q_disp = {}

for t in range(1, T+1):
    for w in range(p['W']):
        for h in range(p['H']):
            a_arr[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f"a_arr_{t}_{w}_{h}")
            a_dep[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f"a_dep_{t}_{w}_{h}")
            z[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f"z_{t}_{w}_{h}")
            I_trailer[t,w,h] = m.addVar(lb=0, name=f"I_trailer_{t}_{w}_{h}")
            Q_depart[t,w,h] = m.addVar(lb=0, name=f"Q_depart_{t}_{w}_{h}")
            q_comp[t,w,h] = m.addVar(lb=0, name=f"q_comp_{t}_{w}_{h}")
            I_HP[t,w,h] = m.addVar(lb=0, name=f"I_HP_{t}_{w}_{h}")
            q_disp[t,w,h] = m.addVar(lb=0, name=f"q_disp_{t}_{w}_{h}")

var_count = len(a_arr) + len(a_dep) + len(z) + len(I_trailer) + len(Q_depart) + len(q_comp) + len(I_HP) + len(q_disp)
print(f"   [OK] Created {var_count} operational variables")

# ============================================================================
# CONSTRAINTS
# ============================================================================

print("\n[CONSTRAINTS] Adding constraints...")

con_count = 0

# For each period and representative week
for t in range(1, T+1):
    rho_t = rho[t-1]

    for w in range(p['W']):
        demand = weeks_data[w+1]['demand_kg']

        for h in range(p['H']):
            # Trailer connection dynamics
            if h == 0:
                m.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
            else:
                m.addConstr(z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h])
            con_count += 1

            # Trailer inventory balance
            if h == 0:
                m.addConstr(I_trailer[t,w,h] == p['Q_trailer'] * a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
            else:
                m.addConstr(I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer'] * a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
            con_count += 1

            # HP storage balance
            if h == 0:
                m.addConstr(I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h])
            else:
                m.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h])
            con_count += 1

            # Capacity limits
            m.addConstr(z[t,w,h] <= 1)
            m.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h])
            m.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h])
            m.addConstr(q_comp[t,w,h] <= C_FIXED[t])  # ★ FIXED capacity
            m.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h])
            m.addConstr(I_HP[t,w,h] <= S_FIXED[t])  # ★ FIXED capacity
            con_count += 6

            # Exact demand satisfaction
            m.addConstr(q_disp[t,w,h] == rho_t * demand[h])
            con_count += 1

            # Sequencing constraints
            if h > 0:
                m.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                m.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                con_count += 2

            m.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)
            con_count += 1

        # Weekly boundary conditions
        m.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'])
        m.addConstr(z[t,w,p['H']-1] == 0)
        con_count += 2

print(f"   [OK] Added {con_count} constraints")

# Verify service capacity (parameter check, not constraint)
print("\n[CHECK] Verifying service capacity...")
service_violations = []
for t in range(1, T+1):
    rho_t = rho[t-1]
    for w in range(p['W']):
        G_peak = weeks_data[w+1]['G_peak']
        required_K = rho_t * G_peak
        if K_FIXED[t] < required_K - 1e-3:
            service_violations.append((t, w+1, K_FIXED[t], required_K))

if service_violations:
    print("   [WARNING] Service capacity violations detected:")
    for t, w, k_fixed, k_required in service_violations:
        print(f"      Period {t}, Week {w}: K={k_fixed} < Required {k_required:.2f}")
else:
    print("   [OK] All service capacity constraints satisfied")

# ============================================================================
# OBJECTIVE: Minimize OPEX ONLY
# ============================================================================

print("\n[OBJECTIVE] Setting objective: min OPEX...")

opex = gp.quicksum(
    (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
    gp.quicksum(
        p['c_H2']*q_disp[t,w,h] + p['c_elec']*q_comp[t,w,h] + p['c_trailer']*a_arr[t,w,h]
        for h in range(p['H'])
    )
    for t in range(1, T+1) for w in range(p['W'])
)

m.setObjective(opex, GRB.MINIMIZE)
print("   [OK] Objective set: min OPEX (CAPEX fixed)")

# ============================================================================
# SOLVE
# ============================================================================

print("\n" + "="*80)
print("SOLVING MODEL D")
print("="*80)

m.optimize()

print("\n" + "="*80)
print("SOLVER RESULTS")
print("="*80)

# ============================================================================
# EXTRACT RESULTS
# ============================================================================

if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT] and m.SolCount > 0:
    print(f"\n[RESULT] Solver terminated: Status={m.status}, Runtime={m.Runtime:.2f}s")
    print(f"   Feasible: TRUE")
    print(f"   Best incumbent: {m.ObjVal:.2f}元 = {m.ObjVal/1e4:.6f}万元")

    if m.status == GRB.OPTIMAL:
        print("   [OK] OPTIMAL solution found")
    else:
        print(f"   [TIME_LIMIT] TIME_LIMIT reached with feasible incumbent")
        print(f"   Best bound: {m.ObjBound:.2f}元 = {m.ObjBound/1e4:.6f}万元")
        print(f"   MIP Gap: {m.MIPGap*100:.4f}%")

    # Verify reproducibility
    expected_opex = 39999163.38
    if abs(m.ObjVal - expected_opex) < 1000:  # Within 1000元 tolerance
        print(f"\n   [OK] REPRODUCIBILITY VERIFIED: ObjVal matches original run (±1000元)")
    else:
        print(f"\n   [WARNING] REPRODUCIBILITY WARNING: ObjVal={m.ObjVal:.2f}, Expected={expected_opex:.2f}")
        print(f"      Difference: {abs(m.ObjVal - expected_opex):.2f}元")

    # ========================================================================
    # EXPORT SOLUTION
    # ========================================================================

    print("\n" + "="*80)
    print("EXPORTING SOLUTION")
    print("="*80)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Export to CSV
    print("\n[EXPORT] Exporting hourly operational solution to CSV...")

    solution_rows = []
    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                row = {
                    'period': t,
                    'week': w+1,
                    'hour': h+1,
                    'a_arr': round(a_arr[t,w,h].X, 6),
                    'a_dep': round(a_dep[t,w,h].X, 6),
                    'z': round(z[t,w,h].X, 6),
                    'I_trailer': round(I_trailer[t,w,h].X, 6),
                    'Q_depart': round(Q_depart[t,w,h].X, 6),
                    'q_comp': round(q_comp[t,w,h].X, 6),
                    'I_HP': round(I_HP[t,w,h].X, 6),
                    'q_disp': round(q_disp[t,w,h].X, 6)
                }
                solution_rows.append(row)

    solution_df = pd.DataFrame(solution_rows)
    csv_file = f"model_d_hourly_solution_{timestamp}.csv"
    solution_df.to_csv(csv_file, index=False)
    print(f"   [OK] Exported {len(solution_df)} rows to {csv_file}")

    # Export summary JSON
    print("\n[EXPORT] Exporting summary to JSON...")

    # Compute OPEX breakdown
    opex_h2 = sum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        sum(p['c_H2'] * q_disp[t,w,h].X for h in range(p['H']))
        for t in range(1, T+1) for w in range(p['W'])
    )

    opex_elec = sum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        sum(p['c_elec'] * q_comp[t,w,h].X for h in range(p['H']))
        for t in range(1, T+1) for w in range(p['W'])
    )

    opex_trailer = sum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        sum(p['c_trailer'] * a_arr[t,w,h].X for h in range(p['H']))
        for t in range(1, T+1) for w in range(p['W'])
    )

    result = {
        "experiment": "model_d_solution_export",
        "timestamp": timestamp,
        "reproducibility": {
            "original_run_opex": 39999163.38,
            "this_run_opex": m.ObjVal,
            "difference": m.ObjVal - 39999163.38,
            "verified": abs(m.ObjVal - 39999163.38) < 1000
        },
        "solver": {
            "status": m.status,
            "runtime": m.Runtime,
            "variable_count": var_count,
            "constraint_count": con_count,
            "feasible": True,
            "gap": m.MIPGap,  # preserve achieved nonzero gap even if status is OPTIMAL
            "best_bound": m.ObjBound,
            "status_str": "OPTIMAL" if m.status == GRB.OPTIMAL else "TIME_LIMIT"
        },
        "costs": {
            "opex_optimized": m.ObjVal,
            "opex_optimized_万元": m.ObjVal / 1e4,
            "opex_breakdown": {
                "hydrogen": opex_h2,
                "hydrogen_万元": opex_h2 / 1e4,
                "electricity": opex_elec,
                "electricity_万元": opex_elec / 1e4,
                "trailer": opex_trailer,
                "trailer_万元": opex_trailer / 1e4
            },
            "capex_fixed": MODEL_B_REFERENCE["capex"],
            "capex_fixed_万元": MODEL_B_REFERENCE["capex_万元"],
            "total_cost": MODEL_B_REFERENCE["capex"] + m.ObjVal,
            "total_cost_万元": MODEL_B_REFERENCE["capex_万元"] + m.ObjVal / 1e4
        },
        "fixed_capacities": {
            "C": C_FIXED,
            "S": S_FIXED,
            "K": K_FIXED
        },
        "solution_files": {
            "hourly_csv": csv_file
        }
    }

    json_file = f"model_d_solution_export_{timestamp}.json"
    with open(json_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"   [OK] Exported summary to {json_file}")

    print("\n" + "="*80)
    print("[COMPLETE] MODEL D SOLUTION EXPORT COMPLETE")
    print("="*80)
    print(f"\n[COSTS] Total cost: {result['costs']['total_cost_万元']:.6f}万元")
    print(f"   CAPEX (fixed): {result['costs']['capex_fixed_万元']:.6f}万元")
    print(f"   OPEX (optimized): {result['costs']['opex_optimized_万元']:.6f}万元")
    print(f"\n[FILES] Exported files:")
    print(f"   - {csv_file} ({len(solution_df)} hourly solutions)")
    print(f"   - {json_file} (summary)")

else:
    print(f"\n[ERROR] Solver failed: Status={m.status}")
    sys.exit(1)
