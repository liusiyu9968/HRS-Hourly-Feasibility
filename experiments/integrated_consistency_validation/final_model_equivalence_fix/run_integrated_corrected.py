"""
Integrated Model with Corrected Investment Constraints
======================================================

Purpose:
    Fix investment constraint formulation to match original Integrated model:
    - Original: Each expansion OPTION can be purchased at most once across T periods
    - Previous error: Each asset CLASS limited to one option per period

This is the AUTHORITATIVE Integrated formulation for paper baseline.

Mathematical Model Source:
    experiments/run_leadtime_sensitivity.py (Integrated section, lines 417-600)

Key Fix (line ~457-461 in original):
    for c in range(len(p['Delta_C_options'])):
        m.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1)

    NOT:
        for t in range(1, T+1):
            m.addConstr(gp.quicksum(x_C[t,i] for i in range(...)) <= 1)

Configuration:
    Growth=15%, LT=1, S₀=158, Central Case, 10 representative weeks

Integrity:
    - Do NOT modify to pursue better numerical results
    - Use exact same data file (SHA256 verified)
    - Use Model D MIP start from validated hourly solution
    - Report actual solver status and gap honestly
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

sys.path.insert(0, '../../../data/parameters')
from unified_params import get_params

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_FILE = "../../../data/processed/representative_weeks_FixedEP_W10_FINAL.csv"
EXPECTED_DATA_HASH = "f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef"

MODEL_D_SOLUTION_FILE = os.environ.get("HRS_MODEL_D_SOLUTION_FILE", "../model_d_hourly_solution_20261029_221345.csv")
MODEL_D_SUMMARY_FILE = os.environ.get("HRS_MODEL_D_SUMMARY_FILE", "../model_d_solution_export_20261029_221345.json")

def compute_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

print("="*80)
print("INTEGRATED MODEL WITH CORRECTED INVESTMENT CONSTRAINTS")
print("="*80)
print("\nFIX: Investment options constrained across planning horizon")
print("     (not per-period per-asset-class)")

# ============================================================================
# VERIFY DATA FILE
# ============================================================================

data_hash = compute_sha256(DATA_FILE)
print(f"\n[DATA] Verifying data file: {DATA_FILE}")
print(f"   SHA256: {data_hash}")
if data_hash == EXPECTED_DATA_HASH:
    print("   [OK] Hash matches Model B/D reference")
else:
    print(f"   [ERROR] Hash mismatch! Expected: {EXPECTED_DATA_HASH}")
    sys.exit(1)

# ============================================================================
# LOAD DATA
# ============================================================================

print(f"\n[LOAD] Loading representative weeks...")
df = pd.read_csv(DATA_FILE)
print(f"   Loaded {len(df)} rows")

weeks_data = {}
for week_id in range(1, 11):
    week_df = df[df['representative_week_id'] == week_id].copy()
    week_df = week_df.sort_values('hour').reset_index(drop=True)

    if len(week_df) != 168:
        print(f"   [ERROR] Week {week_id}: Expected 168 hours, got {len(week_df)}")
        sys.exit(1)

    weeks_data[week_id] = {
        'demand_kg': week_df['demand_kg'].values,
        'G_peak': week_df['service_minutes'].max()
    }

print(f"   [OK] Loaded {len(weeks_data)} representative weeks")

# ============================================================================
# LOAD PARAMETERS
# ============================================================================

base_params = get_params(case='central')
p = {
    **base_params,
    'growth_rate': 0.15,
    'LT': 1,  # LT_C, LT_S, LT_K all = 1
    'LT_C': 1,
    'LT_S': 1,
    'LT_K': 1,
    's0': 158,
    'W': 10,
    'H': 168,
    'omega': [1, 1, 1, 1, 1, 7, 14, 12, 4, 10]
}

print(f"\n[PARAMS] Configuration:")
print(f"   Growth rate: {p['growth_rate']*100}%")
print(f"   Lead time: LT={p['LT']} year")
print(f"   Initial storage: S₀={p['s0']} kg")
print(f"   Discount rate: {p['discount_rate']*100}%")
print(f"   Planning horizon: T=5 years")
print(f"   Representative weeks: W={p['W']}")
print(f"   Hours per week: H={p['H']}")

# Compute growth multipliers
T = 5
rho = [1.0]
for t in range(1, T):
    rho.append(rho[-1] * (1 + p['growth_rate']))
p['rho'] = rho

print(f"   Growth multipliers: {[f'{r:.4f}' for r in rho]}")

# ============================================================================
# LOAD MODEL D SOLUTION (MIP START)
# ============================================================================

print(f"\n[MIP START] Loading Model D solution...")
print(f"   Solution file: {MODEL_D_SOLUTION_FILE}")
print(f"   Summary file: {MODEL_D_SUMMARY_FILE}")

mip_start_df = pd.read_csv(MODEL_D_SOLUTION_FILE)
print(f"   Loaded {len(mip_start_df)} hourly solutions")

with open(MODEL_D_SUMMARY_FILE, 'r') as f:
    model_d_summary = json.load(f)

print(f"   Model D total cost: {model_d_summary['costs']['total_cost_万元']:.6f}万元")
print(f"   Model D CAPEX: {model_d_summary['costs']['capex_fixed_万元']:.6f}万元")
print(f"   Model D OPEX: {model_d_summary['costs']['opex_optimized_万元']:.6f}万元")

# Organize MIP start solution
mip_start_sol = {}
for _, row in mip_start_df.iterrows():
    t = int(row['period'])
    w = int(row['week']) - 1  # 0-indexed
    h = int(row['hour']) - 1  # 0-indexed
    mip_start_sol[(t,w,h)] = {
        'a_arr': row['a_arr'],
        'a_dep': row['a_dep'],
        'z': row['z'],
        'I_trailer': row['I_trailer'],
        'Q_depart': row['Q_depart'],
        'q_comp': row['q_comp'],
        'I_HP': row['I_HP'],
        'q_disp': row['q_disp']
    }

# Model D investment decisions
model_d_investments = model_d_summary['fixed_capacities']
print(f"\n[MIP START] Model D investment path:")
print(f"   t=1: C+50, t=2: S+200/K+120, t=3: C+100")
print(f"   Final capacity: C=250, S=358, K=240")

# ============================================================================
# BUILD INTEGRATED MODEL (CORRECTED FORMULATION)
# ============================================================================

print(f"\n[BUILD] Building Integrated model with corrected constraints...")

m = gp.Model("Integrated_Corrected")
m.setParam('TimeLimit', 1800)
m.setParam('MIPGap', 0.001)
m.setParam('OutputFlag', 1)
m.setParam('LogFile', 'integrated_corrected_gurobi.log')

# ============================================================================
# INVESTMENT DECISION VARIABLES
# ============================================================================

print(f"\n[VARS] Creating investment variables...")

# Binary investment decisions: x[option_index, period]
x_C = {}
x_S = {}
x_K = {}

for c in range(len(p['Delta_C_options'])):
    for t in range(1, T+1):
        x_C[(c,t)] = m.addVar(vtype=GRB.BINARY, name=f"x_C_{c}_{t}")

for s in range(len(p['Delta_S_options'])):
    for t in range(1, T+1):
        x_S[(s,t)] = m.addVar(vtype=GRB.BINARY, name=f"x_S_{s}_{t}")

for k in range(len(p['Delta_K_options'])):
    for t in range(1, T+1):
        x_K[(k,t)] = m.addVar(vtype=GRB.BINARY, name=f"x_K_{k}_{t}")

# Operational status variables (accounting for lead time)
y_C = {}
y_S = {}
y_K = {}

for c in range(len(p['Delta_C_options'])):
    for t in range(1, T+1):
        y_C[(c,t)] = m.addVar(vtype=GRB.BINARY, name=f"y_C_{c}_{t}")

for s in range(len(p['Delta_S_options'])):
    for t in range(1, T+1):
        y_S[(s,t)] = m.addVar(vtype=GRB.BINARY, name=f"y_S_{s}_{t}")

for k in range(len(p['Delta_K_options'])):
    for t in range(1, T+1):
        y_K[(k,t)] = m.addVar(vtype=GRB.BINARY, name=f"y_K_{k}_{t}")

# Capacity variables
C_t = {}
S_t = {}
K_t = {}

for t in range(1, T+1):
    C_t[t] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"C_{t}")
    S_t[t] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"S_{t}")
    K_t[t] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"K_{t}")

print(f"   Investment purchase vars: {len(x_C) + len(x_S) + len(x_K)}")
print(f"   Operational status vars: {len(y_C) + len(y_S) + len(y_K)}")
print(f"   Capacity vars: {len(C_t) + len(S_t) + len(K_t)}")

# ============================================================================
# OPERATIONAL DECISION VARIABLES
# ============================================================================

print(f"\n[VARS] Creating operational variables...")

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
            a_arr[(t,w,h)] = m.addVar(vtype=GRB.BINARY, name=f"a_arr_{t}_{w}_{h}")
            a_dep[(t,w,h)] = m.addVar(vtype=GRB.BINARY, name=f"a_dep_{t}_{w}_{h}")
            z[(t,w,h)] = m.addVar(vtype=GRB.BINARY, name=f"z_{t}_{w}_{h}")
            I_trailer[(t,w,h)] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"I_trailer_{t}_{w}_{h}")
            Q_depart[(t,w,h)] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"Q_depart_{t}_{w}_{h}")
            q_comp[(t,w,h)] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"q_comp_{t}_{w}_{h}")
            I_HP[(t,w,h)] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"I_HP_{t}_{w}_{h}")
            q_disp[(t,w,h)] = m.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f"q_disp_{t}_{w}_{h}")

var_count_ops = (len(a_arr) + len(a_dep) + len(z) + len(I_trailer) +
                 len(Q_depart) + len(q_comp) + len(I_HP) + len(q_disp))
print(f"   Operational vars: {var_count_ops}")

m.update()

# ============================================================================
# INVESTMENT CONSTRAINTS (CORRECTED)
# ============================================================================

print(f"\n[CONSTRAINTS] Adding investment constraints (CORRECTED)...")

# CRITICAL FIX: Each expansion OPTION can be purchased at most once
# across the entire planning horizon
# (NOT: each asset class limited to one option per period)

for c in range(len(p['Delta_C_options'])):
    m.addConstr(
        gp.quicksum(x_C[(c,t)] for t in range(1, T+1)) <= 1,
        name=f"option_C_{c}_once"
    )

for s in range(len(p['Delta_S_options'])):
    m.addConstr(
        gp.quicksum(x_S[(s,t)] for t in range(1, T+1)) <= 1,
        name=f"option_S_{s}_once"
    )

for k in range(len(p['Delta_K_options'])):
    m.addConstr(
        gp.quicksum(x_K[(k,t)] for t in range(1, T+1)) <= 1,
        name=f"option_K_{k}_once"
    )

con_count_invest = len(p['Delta_C_options']) + len(p['Delta_S_options']) + len(p['Delta_K_options'])
print(f"   Purchase-once constraints: {con_count_invest}")

# Lead time constraints: operational from period (purchase_period + LT)
for t in range(1, T+1):
    for c in range(len(p['Delta_C_options'])):
        m.addConstr(
            y_C[(c,t)] == gp.quicksum(x_C[(c,tau)] for tau in range(1, max(0, t-p['LT_C'])+1)),
            name=f"leadtime_C_{c}_{t}"
        )
    for s in range(len(p['Delta_S_options'])):
        m.addConstr(
            y_S[(s,t)] == gp.quicksum(x_S[(s,tau)] for tau in range(1, max(0, t-p['LT_S'])+1)),
            name=f"leadtime_S_{s}_{t}"
        )
    for k in range(len(p['Delta_K_options'])):
        m.addConstr(
            y_K[(k,t)] == gp.quicksum(x_K[(k,tau)] for tau in range(1, max(0, t-p['LT_K'])+1)),
            name=f"leadtime_K_{k}_{t}"
        )

con_count_leadtime = 3 * T * (len(p['Delta_C_options']) + len(p['Delta_S_options']) + len(p['Delta_K_options'])) // 3
print(f"   Lead time constraints: {con_count_leadtime}")

# Total capacity equations
for t in range(1, T+1):
    m.addConstr(
        C_t[t] == p['C_0'] + gp.quicksum(p['Delta_C_options'][c][0]*y_C[(c,t)] for c in range(len(p['Delta_C_options']))),
        name=f"capacity_C_{t}"
    )
    m.addConstr(
        S_t[t] == p['s0'] + gp.quicksum(p['Delta_S_options'][s][0]*y_S[(s,t)] for s in range(len(p['Delta_S_options']))),
        name=f"capacity_S_{t}"
    )
    m.addConstr(
        K_t[t] == p['K_srv_0'] + gp.quicksum(p['Delta_K_options'][k][0]*y_K[(k,t)] for k in range(len(p['Delta_K_options']))),
        name=f"capacity_K_{t}"
    )

print(f"   Capacity equations: {3*T}")

# ============================================================================
# HOURLY OPERATIONAL CONSTRAINTS
# ============================================================================

print(f"\n[CONSTRAINTS] Adding hourly operational constraints...")

con_count_ops = 0

for t in range(1, T+1):
    rho_t = rho[t-1]

    for w in range(p['W']):
        demand = weeks_data[w+1]['demand_kg']
        G_peak = weeks_data[w+1]['G_peak']

        for h in range(p['H']):
            # Trailer connection dynamics
            if h == 0:
                m.addConstr(z[(t,w,h)] == a_arr[(t,w,h)] - a_dep[(t,w,h)],
                           name=f"trailer_conn_{t}_{w}_{h}")
            else:
                m.addConstr(z[(t,w,h)] == z[(t,w,h-1)] + a_arr[(t,w,h)] - a_dep[(t,w,h)],
                           name=f"trailer_conn_{t}_{w}_{h}")
            con_count_ops += 1

            # Trailer inventory balance
            if h == 0:
                m.addConstr(
                    I_trailer[(t,w,h)] == p['Q_trailer']*a_arr[(t,w,h)] - q_comp[(t,w,h)] - Q_depart[(t,w,h)],
                    name=f"trailer_inv_{t}_{w}_{h}"
                )
            else:
                m.addConstr(
                    I_trailer[(t,w,h)] == I_trailer[(t,w,h-1)] + p['Q_trailer']*a_arr[(t,w,h)]
                                         - q_comp[(t,w,h)] - Q_depart[(t,w,h)],
                    name=f"trailer_inv_{t}_{w}_{h}"
                )
            con_count_ops += 1

            # HP storage balance
            if h == 0:
                m.addConstr(
                    I_HP[(t,w,h)] == p['I_HP_0'] + q_comp[(t,w,h)] - q_disp[(t,w,h)],
                    name=f"hp_inv_{t}_{w}_{h}"
                )
            else:
                m.addConstr(
                    I_HP[(t,w,h)] == I_HP[(t,w,h-1)] + q_comp[(t,w,h)] - q_disp[(t,w,h)],
                    name=f"hp_inv_{t}_{w}_{h}"
                )
            con_count_ops += 1

            # Capacity limits
            m.addConstr(z[(t,w,h)] <= 1, name=f"cap_z_{t}_{w}_{h}")
            m.addConstr(I_trailer[(t,w,h)] <= p['M']*z[(t,w,h)], name=f"cap_I_trailer_{t}_{w}_{h}")
            m.addConstr(Q_depart[(t,w,h)] <= p['M']*a_dep[(t,w,h)], name=f"cap_Q_depart_{t}_{w}_{h}")
            m.addConstr(q_comp[(t,w,h)] <= C_t[t], name=f"cap_q_comp_C_{t}_{w}_{h}")
            m.addConstr(q_comp[(t,w,h)] <= p['M']*z[(t,w,h)], name=f"cap_q_comp_z_{t}_{w}_{h}")
            m.addConstr(I_HP[(t,w,h)] <= S_t[t], name=f"cap_I_HP_{t}_{w}_{h}")
            con_count_ops += 6

            # Exact demand satisfaction
            m.addConstr(q_disp[(t,w,h)] == rho_t * demand[h], name=f"demand_{t}_{w}_{h}")
            con_count_ops += 1

            # Sequencing constraints
            if h > 0:
                m.addConstr(a_dep[(t,w,h)] <= z[(t,w,h-1)], name=f"seq_dep_{t}_{w}_{h}")
                m.addConstr(a_arr[(t,w,h)] <= 1 - z[(t,w,h-1)], name=f"seq_arr_{t}_{w}_{h}")
                con_count_ops += 2

            m.addConstr(a_arr[(t,w,h)] + a_dep[(t,w,h)] <= 1, name=f"seq_mutex_{t}_{w}_{h}")
            con_count_ops += 1

        # Weekly boundary conditions
        h_last = p['H'] - 1
        m.addConstr(I_HP[(t,w,h_last)] == p['I_HP_0'], name=f"boundary_I_HP_{t}_{w}")
        m.addConstr(z[(t,w,h_last)] == 0, name=f"boundary_z_{t}_{w}")
        con_count_ops += 2

        # Service capacity constraint
        m.addConstr(K_t[t] >= rho_t * G_peak, name=f"service_cap_{t}_{w}")
        con_count_ops += 1

print(f"   Operational constraints: {con_count_ops}")

# ============================================================================
# OBJECTIVE: MINIMIZE TOTAL COST (CAPEX + OPEX)
# ============================================================================

print(f"\n[OBJECTIVE] Setting objective: min (CAPEX + OPEX)...")

# CAPEX
capex = gp.quicksum(
    (1 / (1 + p['discount_rate']))**(t-1) * (
        gp.quicksum(p['Delta_C_options'][c][1]*x_C[(c,t)] for c in range(len(p['Delta_C_options']))) +
        gp.quicksum(p['Delta_S_options'][s][1]*x_S[(s,t)] for s in range(len(p['Delta_S_options']))) +
        gp.quicksum(p['Delta_K_options'][k][1]*x_K[(k,t)] for k in range(len(p['Delta_K_options'])))
    )
    for t in range(1, T+1)
)

# OPEX
opex = gp.quicksum(
    (1 / (1 + p['discount_rate']))**(t-1) * p['omega'][w] * gp.quicksum(
        p['c_H2']*q_disp[(t,w,h)] + p['c_elec']*q_comp[(t,w,h)] + p['c_trailer']*a_arr[(t,w,h)]
        for h in range(p['H'])
    )
    for t in range(1, T+1) for w in range(p['W'])
)

m.setObjective(capex + opex, GRB.MINIMIZE)
print("   [OK] Objective set: min (CAPEX + OPEX)")

print(f"\n[MODEL] Final model size:")
print(f"   Variables: {m.NumVars}")
print(f"   Constraints: {m.NumConstrs}")

# ============================================================================
# SET MIP START FROM MODEL D
# ============================================================================

print(f"\n[MIP START] Loading Model D solution as warm start...")

# Model D investment decisions mapping
# Model D: t=1 C+50(option 0), t=2 S+200(option 1), t=2 K+120(option 1), t=3 C+100(option 1)
model_d_invest_map = {
    (0, 1): True,  # C option 0 (+50) at t=1
    (1, 2): True,  # S option 1 (+200) at t=2
    (1, 2): True,  # K option 1 (+120) at t=2
    (1, 3): True   # C option 1 (+100) at t=3
}

# Set investment purchase variables
for c in range(len(p['Delta_C_options'])):
    for t in range(1, T+1):
        if (c == 0 and t == 1) or (c == 1 and t == 3):
            x_C[(c,t)].Start = 1
        else:
            x_C[(c,t)].Start = 0

for s in range(len(p['Delta_S_options'])):
    for t in range(1, T+1):
        if s == 1 and t == 2:
            x_S[(s,t)].Start = 1
        else:
            x_S[(s,t)].Start = 0

for k in range(len(p['Delta_K_options'])):
    for t in range(1, T+1):
        if k == 1 and t == 2:
            x_K[(k,t)].Start = 1
        else:
            x_K[(k,t)].Start = 0

# Set operational status variables (accounting for lead time)
for c in range(len(p['Delta_C_options'])):
    for t in range(1, T+1):
        if (c == 0 and t >= 2) or (c == 1 and t >= 4):
            y_C[(c,t)].Start = 1
        else:
            y_C[(c,t)].Start = 0

for s in range(len(p['Delta_S_options'])):
    for t in range(1, T+1):
        if s == 1 and t >= 3:
            y_S[(s,t)].Start = 1
        else:
            y_S[(s,t)].Start = 0

for k in range(len(p['Delta_K_options'])):
    for t in range(1, T+1):
        if k == 1 and t >= 3:
            y_K[(k,t)].Start = 1
        else:
            y_K[(k,t)].Start = 0

# Set capacity variables
for t in range(1, T+1):
    C_t[t].Start = float(model_d_investments['C'][str(t)])
    S_t[t].Start = float(model_d_investments['S'][str(t)])
    K_t[t].Start = float(model_d_investments['K'][str(t)])

# Set operational variables from Model D hourly solution
for t in range(1, T+1):
    for w in range(p['W']):
        for h in range(p['H']):
            sol = mip_start_sol[(t,w,h)]
            a_arr[(t,w,h)].Start = sol['a_arr']
            a_dep[(t,w,h)].Start = sol['a_dep']
            z[(t,w,h)].Start = sol['z']
            I_trailer[(t,w,h)].Start = sol['I_trailer']
            Q_depart[(t,w,h)].Start = sol['Q_depart']
            q_comp[(t,w,h)].Start = sol['q_comp']
            I_HP[(t,w,h)].Start = sol['I_HP']
            q_disp[(t,w,h)].Start = sol['q_disp']

print("   [OK] MIP start loaded from Model D")
print(f"   Investment path: 4 purchases (t=1 C+50, t=2 S+200/K+120, t=3 C+100)")
print(f"   Operational vars: {var_count_ops}")
print(f"   Expected incumbent: ~4635.46万元")

# ============================================================================
# SOLVE
# ============================================================================

print("\n" + "="*80)
print("SOLVING CORRECTED INTEGRATED MODEL WITH MIP START")
print("="*80)

t0 = datetime.now()
m.optimize()
t1 = datetime.now()

runtime = (t1 - t0).total_seconds()

print("\n" + "="*80)
print("SOLVER RESULTS")
print("="*80)

# ============================================================================
# EXTRACT RESULTS
# ============================================================================

if m.status in [GRB.OPTIMAL, GRB.TIME_LIMIT] and m.SolCount > 0:
    print(f"\n[RESULT] Solver terminated:")
    print(f"   Status: {m.status} ({'OPTIMAL' if m.status == GRB.OPTIMAL else 'TIME_LIMIT'})")
    print(f"   Runtime: {runtime:.2f}s ({runtime/60:.1f} min)")
    print(f"   Feasible: TRUE")
    print(f"   Best incumbent: {m.ObjVal:.2f}元 = {m.ObjVal/1e4:.6f}万元")

    if m.status == GRB.OPTIMAL:
        print("   [OK] OPTIMAL solution found (within MIPGap tolerance)")
    else:
        print(f"   [TIME_LIMIT] TIME_LIMIT reached with feasible incumbent")
        print(f"   Best bound: {m.ObjBound:.2f}元 = {m.ObjBound/1e4:.6f}万元")
        print(f"   MIP Gap: {m.MIPGap*100:.4f}%")

    # Extract investment decisions
    print(f"\n[INVESTMENT] Investment decisions:")
    investments = []
    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            if x_C[(c,t)].X > 0.5:
                delta, cost = p['Delta_C_options'][c]
                investments.append({
                    'period': t,
                    'asset': 'C',
                    'option': c,
                    'capacity': delta,
                    'cost': cost
                })
                print(f"   Period {t}: C+{delta} kg/h (option {c}), Cost={cost/1e4:.0f}万元")

        for s in range(len(p['Delta_S_options'])):
            if x_S[(s,t)].X > 0.5:
                delta, cost = p['Delta_S_options'][s]
                investments.append({
                    'period': t,
                    'asset': 'S',
                    'option': s,
                    'capacity': delta,
                    'cost': cost
                })
                print(f"   Period {t}: S+{delta} kg (option {s}), Cost={cost/1e4:.0f}万元")

        for k in range(len(p['Delta_K_options'])):
            if x_K[(k,t)].X > 0.5:
                delta, cost = p['Delta_K_options'][k]
                investments.append({
                    'period': t,
                    'asset': 'K',
                    'option': k,
                    'capacity': delta,
                    'cost': cost
                })
                print(f"   Period {t}: K+{delta} min/h (option {k}), Cost={cost/1e4:.0f}万元")

    print(f"   Total investments: {len(investments)}")

    # Extract capacity trajectory
    print(f"\n[CAPACITY] Capacity trajectory:")
    capacity_trajectory = {}
    for t in range(1, T+1):
        capacity_trajectory[t] = {
            'C': round(C_t[t].X, 2),
            'S': round(S_t[t].X, 2),
            'K': round(K_t[t].X, 2)
        }
        print(f"   Period {t}: C={capacity_trajectory[t]['C']} kg/h, "
              f"S={capacity_trajectory[t]['S']} kg, K={capacity_trajectory[t]['K']} min/h")

    # Compute CAPEX and OPEX breakdown
    capex_val = 0
    for t in range(1, T+1):
        beta = (1 / (1 + p['discount_rate']))**(t-1)
        for c in range(len(p['Delta_C_options'])):
            if x_C[(c,t)].X > 0.5:
                capex_val += beta * p['Delta_C_options'][c][1]
        for s in range(len(p['Delta_S_options'])):
            if x_S[(s,t)].X > 0.5:
                capex_val += beta * p['Delta_S_options'][s][1]
        for k in range(len(p['Delta_K_options'])):
            if x_K[(k,t)].X > 0.5:
                capex_val += beta * p['Delta_K_options'][k][1]

    opex_val = m.ObjVal - capex_val

    print(f"\n[COSTS] Cost breakdown:")
    print(f"   CAPEX: {capex_val:.2f}元 = {capex_val/1e4:.6f}万元")
    print(f"   OPEX: {opex_val:.2f}元 = {opex_val/1e4:.6f}万元")
    print(f"   Total: {m.ObjVal:.2f}元 = {m.ObjVal/1e4:.6f}万元")

    # Compare with Model D
    model_d_total = model_d_summary['costs']['total_cost']
    diff = m.ObjVal - model_d_total
    diff_pct = diff / model_d_total * 100

    print(f"\n[COMPARISON] vs Model D:")
    print(f"   Model D: {model_d_total:.2f}元 = {model_d_total/1e4:.6f}万元")
    print(f"   This run: {m.ObjVal:.2f}元 = {m.ObjVal/1e4:.6f}万元")
    print(f"   Difference: {diff:.2f}元 = {diff/1e4:.6f}万元 ({diff_pct:+.4f}%)")

    if abs(diff) < 1000:
        print(f"   [MATCH] Solutions essentially identical (±1000元)")
    elif diff < 0:
        print(f"   [BETTER] Found cheaper solution")
    else:
        print(f"   [WORSE] Model D was cheaper")

    # ========================================================================
    # EXPORT RESULTS
    # ========================================================================

    print("\n" + "="*80)
    print("EXPORTING RESULTS")
    print("="*80)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Export summary JSON
    result = {
        'experiment': 'integrated_corrected',
        'timestamp': timestamp,
        'formulation_fix': {
            'description': 'Investment constraint corrected to match original model',
            'original_constraint': 'Each expansion OPTION purchased at most once across T periods',
            'previous_error': 'Each asset CLASS limited to one option per period',
            'fix_applied': 'Restored option-level constraint: sum over t (x[option,t]) <= 1'
        },
        'mip_start_source': {
            'solution_file': MODEL_D_SOLUTION_FILE,
            'summary_file': MODEL_D_SUMMARY_FILE,
            'total_cost_万元': model_d_summary['costs']['total_cost_万元']
        },
        'configuration': {
            'model_version': 'Model Freeze v1.0',
            'growth_rate': p['growth_rate'],
            'LT': p['LT'],
            's0': p['s0'],
            'scenario': 'Central Case',
            'objective': 'min CAPEX+OPEX',
            'data_file': DATA_FILE,
            'data_hash': data_hash
        },
        'solver': {
            'status': m.status,
            'status_str': 'OPTIMAL' if m.status == GRB.OPTIMAL else 'TIME_LIMIT',
            'runtime': runtime,
            'variable_count': m.NumVars,
            'constraint_count': m.NumConstrs,
            'feasible': True,
            'gap': m.MIPGap,  # retain actual achieved gap for all feasible statuses
            'best_bound': m.ObjBound if m.status == GRB.TIME_LIMIT else m.ObjVal
        },
        'costs': {
            'total': m.ObjVal,
            'total_万元': m.ObjVal / 1e4,
            'capex': capex_val,
            'capex_万元': capex_val / 1e4,
            'opex': opex_val,
            'opex_万元': opex_val / 1e4
        },
        'investments': investments,
        'capacity_trajectory': capacity_trajectory,
        'comparison_with_model_d': {
            'model_d_total_万元': model_d_total / 1e4,
            'integrated_total_万元': m.ObjVal / 1e4,
            'difference_万元': diff / 1e4,
            'difference_pct': diff_pct
        }
    }

    json_file = f"integrated_corrected_result_{timestamp}.json"
    with open(json_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n[EXPORT] Results saved to {json_file}")

    # Export hourly solution CSV
    print(f"\n[EXPORT] Exporting hourly operational solution...")

    solution_rows = []
    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                row = {
                    'period': t,
                    'week': w+1,
                    'hour': h+1,
                    'a_arr': round(a_arr[(t,w,h)].X, 6),
                    'a_dep': round(a_dep[(t,w,h)].X, 6),
                    'z': round(z[(t,w,h)].X, 6),
                    'I_trailer': round(I_trailer[(t,w,h)].X, 6),
                    'Q_depart': round(Q_depart[(t,w,h)].X, 6),
                    'q_comp': round(q_comp[(t,w,h)].X, 6),
                    'I_HP': round(I_HP[(t,w,h)].X, 6),
                    'q_disp': round(q_disp[(t,w,h)].X, 6)
                }
                solution_rows.append(row)

    solution_df = pd.DataFrame(solution_rows)
    csv_file = f"integrated_corrected_hourly_{timestamp}.csv"
    solution_df.to_csv(csv_file, index=False)
    print(f"   [OK] Exported {len(solution_df)} rows to {csv_file}")

    # Export Gurobi solution file
    print(f"\n[EXPORT] Exporting Gurobi solution file...")
    sol_file = f"integrated_corrected_solution_{timestamp}.sol"
    m.write(sol_file)
    print(f"   [OK] Saved to {sol_file}")

    print("\n" + "="*80)
    print("[COMPLETE] CORRECTED INTEGRATED MODEL SOLVED")
    print("="*80)
    print(f"\n[SUMMARY]:")
    print(f"   Total cost: {m.ObjVal/1e4:.6f}万元")
    print(f"   CAPEX: {capex_val/1e4:.6f}万元")
    print(f"   OPEX: {opex_val/1e4:.6f}万元")
    print(f"   Status: {result['solver']['status_str']}")
    if m.status == GRB.TIME_LIMIT:
        print(f"   Gap: {result['solver']['gap']*100:.4f}%")
        print(f"   Best bound: {result['solver']['best_bound']/1e4:.6f}万元")
    print(f"   Runtime: {runtime:.2f}s ({runtime/60:.1f} min)")
    print(f"   Investments: {len(investments)} purchases")
    print(f"   Final capacity: C={capacity_trajectory[T]['C']}, S={capacity_trajectory[T]['S']}, K={capacity_trajectory[T]['K']}")

    print(f"\n[FILES GENERATED]:")
    print(f"   - {json_file} (summary)")
    print(f"   - {csv_file} (8400 hourly solutions)")
    print(f"   - {sol_file} (Gurobi solution)")
    print(f"   - integrated_corrected_gurobi.log (solver log)")

else:
    print(f"\n[ERROR] Solver failed: Status={m.status}")
    sys.exit(1)
