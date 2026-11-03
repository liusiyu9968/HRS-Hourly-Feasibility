#!/usr/bin/env python3
"""
LIMITED S0 SENSITIVITY — SCREENING STAGE

Purpose: Find whether Sequential Stage2 can recover hourly feasibility with higher S0.

Fixed:
- Model Freeze v1.0
- growth = 15%
- LT = 1
- Central Case
- final representative weeks
- unified_params
- All solver/model settings unchanged

Variable: S0 ∈ {170, 180, 190, 200} kg

Run only Sequential (S1 + S2) for each S0.
Do NOT run Integrated in this screening stage.

Core question: Does Sequential Stage2 become FEASIBLE for any S0 in tested range?

Outputs:
- s0_sensitivity_screening_result.json
- S0_SENSITIVITY_SCREENING_AUDIT.md
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import time
import json
import sys

sys.path.insert(0, '../data/parameters')
from unified_params import get_params


def run_sequential_s1_for_s0(s0_value):
    """
    Run Sequential Stage 1 with given S0.

    Returns: (status, capex, investment_plan, runtime)
    """

    # Fixed configuration
    growth_rate = 0.15
    lt_value = 1

    print("="*70)
    print(f"S0 = {s0_value} kg | SEQUENTIAL STAGE 1")
    print("="*70)

    # Load parameters
    params = get_params('central')
    params['LT_C'] = lt_value
    params['LT_S'] = lt_value
    params['LT_K'] = lt_value
    params['S_0'] = s0_value  # Override S0

    # Load representative weeks
    df = pd.read_csv('../data/processed/representative_weeks_FixedEP_W10_FINAL.csv', encoding='utf-8-sig')
    df['hour'] = pd.to_datetime(df['hour'])

    # Process weeks data
    weeks_data = {}
    for week_id in sorted(df['representative_week_id'].unique()):
        week_data = df[df['representative_week_id'] == week_id].sort_values('hour')
        demand = week_data['demand_kg'].values
        service = week_data['service_minutes'].values
        weeks_data[int(week_id)] = {
            'demand': demand,
            'service': service,
            'D_1h': demand.max(),
            'D_2h': max([demand[i:i+2].sum() for i in range(167)]),
            'D_4h': max([demand[i:i+4].sum() for i in range(165)]),
            'G_peak': service.max(),
            'weight': week_data['weight'].values[0]
        }

    # Compute growth multipliers
    T = 5
    rho = [(1 + growth_rate)**t for t in range(T)]

    # Store parameters
    p = params.copy()
    p.update({
        'T': T,
        'W': len(weeks_data),
        'H': 168,
        'rho': rho,
        'omega': [weeks_data[w+1]['weight'] for w in range(len(weeks_data))],
        'S_0': s0_value
    })

    # ============================================================
    # SEQUENTIAL STAGE 1: Aggregated Capacity Planning
    # ============================================================

    m1 = gp.Model("SeqS1_S0" + str(s0_value))

    m1.setParam('OutputFlag', 0)
    m1.setParam('MIPGap', 0.001)
    m1.setParam('TimeLimit', 300)

    # Extract expansion options
    Delta_C_opts = params['Delta_C_options']
    Delta_S_opts = params['Delta_S_options']
    Delta_K_opts = params['Delta_K_options']

    C_0, S_0, K_0 = params['C_0'], s0_value, params['K_srv_0']
    Q_t = params['Q_trailer']
    I_HP_0 = params['I_HP_0']
    LT_C, LT_S, LT_K = params['LT_C'], params['LT_S'], params['LT_K']
    c_H2, c_elec, c_trailer = params['c_H2'], params['c_elec'], params['c_trailer']
    discount_rate = params['discount_rate']

    # Decision variables: investment timing
    x_C = {}
    for c_idx in range(len(Delta_C_opts)):
        for t in range(1, T+1):
            x_C[c_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'x_C_{c_idx}_{t}')

    x_S = {}
    for s_idx in range(len(Delta_S_opts)):
        for t in range(1, T+1):
            x_S[s_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'x_S_{s_idx}_{t}')

    x_K = {}
    for k_idx in range(len(Delta_K_opts)):
        for t in range(1, T+1):
            x_K[k_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'x_K_{k_idx}_{t}')

    # Capacity trajectories
    C = {}
    S = {}
    K = {}
    for t in range(1, T+1):
        C[t] = m1.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f'C_{t}')
        S[t] = m1.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f'S_{t}')
        K[t] = m1.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f'K_{t}')

    # Lead-time availability indicators y
    y_C = {}
    for c_idx in range(len(Delta_C_opts)):
        for t in range(1, T+1):
            y_C[c_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'y_C_{c_idx}_{t}')
            tau_max = max(0, t - LT_C)
            if tau_max > 0:
                m1.addConstr(y_C[c_idx, t] == gp.quicksum(x_C[c_idx, tau] for tau in range(1, tau_max+1)))
            else:
                m1.addConstr(y_C[c_idx, t] == 0)

    y_S = {}
    for s_idx in range(len(Delta_S_opts)):
        for t in range(1, T+1):
            y_S[s_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'y_S_{s_idx}_{t}')
            tau_max = max(0, t - LT_S)
            if tau_max > 0:
                m1.addConstr(y_S[s_idx, t] == gp.quicksum(x_S[s_idx, tau] for tau in range(1, tau_max+1)))
            else:
                m1.addConstr(y_S[s_idx, t] == 0)

    y_K = {}
    for k_idx in range(len(Delta_K_opts)):
        for t in range(1, T+1):
            y_K[k_idx, t] = m1.addVar(vtype=GRB.BINARY, name=f'y_K_{k_idx}_{t}')
            tau_max = max(0, t - LT_K)
            if tau_max > 0:
                m1.addConstr(y_K[k_idx, t] == gp.quicksum(x_K[k_idx, tau] for tau in range(1, tau_max+1)))
            else:
                m1.addConstr(y_K[k_idx, t] == 0)

    # Capacity evolution
    for t in range(1, T+1):
        m1.addConstr(C[t] == C_0 + gp.quicksum(Delta_C_opts[c_idx][0] * y_C[c_idx, t] for c_idx in range(len(Delta_C_opts))))
        m1.addConstr(S[t] == S_0 + gp.quicksum(Delta_S_opts[s_idx][0] * y_S[s_idx, t] for s_idx in range(len(Delta_S_opts))))
        m1.addConstr(K[t] == K_0 + gp.quicksum(Delta_K_opts[k_idx][0] * y_K[k_idx, t] for k_idx in range(len(Delta_K_opts))))

    # At-most-once constraints
    for c_idx in range(len(Delta_C_opts)):
        m1.addConstr(gp.quicksum(x_C[c_idx, t] for t in range(1, T+1)) <= 1)
    for s_idx in range(len(Delta_S_opts)):
        m1.addConstr(gp.quicksum(x_S[s_idx, t] for t in range(1, T+1)) <= 1)
    for k_idx in range(len(Delta_K_opts)):
        m1.addConstr(gp.quicksum(x_K[k_idx, t] for t in range(1, T+1)) <= 1)

    # Aggregated demand constraints (CORRECT formulation from leadtime script)
    for t in range(1, T+1):
        rho_t = rho[t-1]
        B_avail = m1.addVar(lb=0, name=f'B_avail_{t}')
        m1.addConstr(B_avail == S[t] - I_HP_0)

        for w in range(1, p['W']+1):
            week = weeks_data[w]
            # Service capacity (min/h)
            m1.addConstr(K[t] >= rho_t * week['G_peak'])
            # Demand windows with buffer
            m1.addConstr(rho_t * week['D_1h'] <= C[t] + B_avail)
            m1.addConstr(rho_t * week['D_2h'] <= 2*C[t] + B_avail)
            m1.addConstr(rho_t * week['D_4h'] <= 4*C[t] + B_avail)

    # Objective: NPV of CAPEX + simplified OPEX
    beta = 1 / (1 + discount_rate)

    capex_expr = gp.quicksum([
        beta ** t * (
            gp.quicksum(Delta_C_opts[c_idx][1] * x_C[c_idx, t] for c_idx in range(len(Delta_C_opts))) +
            gp.quicksum(Delta_S_opts[s_idx][1] * x_S[s_idx, t] for s_idx in range(len(Delta_S_opts))) +
            gp.quicksum(Delta_K_opts[k_idx][1] * x_K[k_idx, t] for k_idx in range(len(Delta_K_opts)))
        )
        for t in range(1, T+1)
    ])

    # Simplified OPEX: assume proportional to demand
    total_demand_per_period = {}
    for t in range(1, T+1):
        total_demand_per_period[t] = sum([
            weeks_data[w+1]['demand'].sum() * weeks_data[w+1]['weight'] * rho[t-1]
            for w in range(p['W'])
        ])

    opex_expr = gp.quicksum([
        beta ** t * (c_H2 + c_elec) * total_demand_per_period[t]
        for t in range(1, T+1)
    ])

    m1.setObjective(capex_expr + opex_expr, GRB.MINIMIZE)

    # Solve
    start_time = time.time()
    m1.optimize()
    s1_runtime = time.time() - start_time

    if m1.status not in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
        return ('INFEASIBLE' if m1.status == GRB.INFEASIBLE else f'STATUS_{m1.status}'), 0, {}, s1_runtime

    # Extract investment plan
    inv_plan = {
        'C_traj': [C_0] + [C[t].X for t in range(1, T+1)],
        'S_traj': [S_0] + [S[t].X for t in range(1, T+1)],
        'K_traj': [K_0] + [K[t].X for t in range(1, T+1)],
        'x_C': {(c, t): x_C[c, t].X for c, t in x_C},
        'x_S': {(s, t): x_S[s, t].X for s, t in x_S},
        'x_K': {(k, t): x_K[k, t].X for k, t in x_K}
    }

    # Calculate CAPEX (undiscounted)
    capex = sum([
        sum([Delta_C_opts[c_idx][1] * x_C[c_idx, t].X for c_idx in range(len(Delta_C_opts))]) +
        sum([Delta_S_opts[s_idx][1] * x_S[s_idx, t].X for s_idx in range(len(Delta_S_opts))]) +
        sum([Delta_K_opts[k_idx][1] * x_K[k_idx, t].X for k_idx in range(len(Delta_K_opts))])
        for t in range(1, T+1)
    ])

    status = 'OPTIMAL' if m1.status == GRB.OPTIMAL else 'TIME_LIMIT'
    return status, capex, inv_plan, s1_runtime


def run_sequential_s2_for_s0(s0_value, inv_plan):
    """
    Run Sequential Stage 2 with fixed investment plan.

    Returns: (status, runtime, iis_count, iis_summary)
    """

    # Fixed configuration
    growth_rate = 0.15
    lt_value = 1

    print("="*70)
    print(f"S0 = {s0_value} kg | SEQUENTIAL STAGE 2")
    print("="*70)

    # Load parameters
    params = get_params('central')
    params['LT_C'] = lt_value
    params['LT_S'] = lt_value
    params['LT_K'] = lt_value
    params['S_0'] = s0_value

    # Load representative weeks
    df = pd.read_csv('../data/processed/representative_weeks_FixedEP_W10_FINAL.csv', encoding='utf-8-sig')
    df['hour'] = pd.to_datetime(df['hour'])

    # Process weeks data
    weeks_data = {}
    for week_id in sorted(df['representative_week_id'].unique()):
        week_data = df[df['representative_week_id'] == week_id].sort_values('hour')
        demand = week_data['demand_kg'].values
        service = week_data['service_minutes'].values
        weeks_data[int(week_id)] = {
            'demand': demand,
            'service': service
        }

    # Compute growth multipliers
    T = 5
    W = len(weeks_data)
    H = 168
    rho = [(1 + growth_rate)**t for t in range(T)]

    # Store parameters
    p = params.copy()
    p.update({
        'T': T,
        'W': W,
        'H': H,
        'rho': rho,
        'S_0': s0_value
    })

    # Extract fixed capacities from investment plan
    C_fixed = inv_plan['C_traj']  # [C_0, C_1, ..., C_5]
    S_fixed = inv_plan['S_traj']
    K_fixed = inv_plan['K_traj']

    # ============================================================
    # SEQUENTIAL STAGE 2: Hourly Feasibility Validation
    # ============================================================

    m2 = gp.Model("SeqS2_S0" + str(s0_value))

    m2.setParam('OutputFlag', 0)
    m2.setParam('MIPGap', 0.001)
    m2.setParam('TimeLimit', 1800)  # 30 minutes

    # Parameters
    Q_t = params['Q_trailer']
    I_HP_0 = params['I_HP_0']
    c_H2, c_elec, c_trailer = params['c_H2'], params['c_elec'], params['c_trailer']
    discount_rate = params['discount_rate']
    beta = 1 / (1 + discount_rate)

    # Decision variables: hourly operations
    q_comp = {}  # Compression flow
    q_disp = {}  # Dispensing flow
    I_HP = {}    # HP storage inventory
    I_t = {}     # Trailer inventory
    a = {}       # Trailer arrival
    z = {}       # Trailer presence

    for t in range(1, T+1):
        for w in range(1, W+1):
            for h in range(H):
                q_comp[t,w,h] = m2.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=C_fixed[t], name=f'q_comp_{t}_{w}_{h}')
                q_disp[t,w,h] = m2.addVar(vtype=GRB.CONTINUOUS, lb=0, name=f'q_disp_{t}_{w}_{h}')
                I_HP[t,w,h] = m2.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=S_fixed[t], name=f'I_HP_{t}_{w}_{h}')
                I_t[t,w,h] = m2.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=Q_t, name=f'I_t_{t}_{w}_{h}')
                a[t,w,h] = m2.addVar(vtype=GRB.BINARY, name=f'a_{t}_{w}_{h}')
                z[t,w,h] = m2.addVar(vtype=GRB.BINARY, name=f'z_{t}_{w}_{h}')

    # Initial conditions
    for t in range(1, T+1):
        for w in range(1, W+1):
            m2.addConstr(I_HP[t,w,0] == I_HP_0, name=f'init_HP_{t}_{w}')
            m2.addConstr(I_t[t,w,0] == 0, name=f'init_t_{t}_{w}')
            m2.addConstr(z[t,w,0] == 0, name=f'init_z_{t}_{w}')

    # Hourly dynamics
    for t in range(1, T+1):
        for w in range(1, W+1):
            demand_w = weeks_data[w]['demand'] * rho[t-1]
            for h in range(1, H):
                # HP storage balance
                m2.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h-1] - q_disp[t,w,h-1],
                            name=f'bal_HP_{t}_{w}_{h}')

                # Trailer inventory balance
                m2.addConstr(I_t[t,w,h] == I_t[t,w,h-1] + Q_t * a[t,w,h] - q_comp[t,w,h-1],
                            name=f'bal_t_{t}_{w}_{h}')

                # Dispensing meets demand
                m2.addConstr(q_disp[t,w,h-1] >= demand_w[h-1], name=f'demand_{t}_{w}_{h}')

                # Trailer sequencing
                m2.addConstr(a[t,w,h] <= 1 - z[t,w,h-1], name=f'seq_a_{t}_{w}_{h}')
                m2.addConstr(z[t,w,h] >= z[t,w,h-1] + a[t,w,h] - 1, name=f'seq_z1_{t}_{w}_{h}')
                m2.addConstr(z[t,w,h] <= z[t,w,h-1] + a[t,w,h], name=f'seq_z2_{t}_{w}_{h}')

                # Compression requires trailer
                M = C_fixed[t]
                m2.addConstr(q_comp[t,w,h-1] <= M * z[t,w,h-1], name=f'comp_trailer_{t}_{w}_{h}')

            # Trailer count constraint
            m2.addConstr(gp.quicksum(z[t,w,h] for h in range(H)) <= K_fixed[t] * H,
                        name=f'trailer_count_{t}_{w}')

    # Objective: minimize OPEX
    opex_expr = gp.quicksum([
        beta ** t * (
            (c_H2 + c_elec) * gp.quicksum(q_disp[t,w,h] for w in range(1, W+1) for h in range(H)) +
            c_trailer * gp.quicksum(a[t,w,h] for w in range(1, W+1) for h in range(H))
        )
        for t in range(1, T+1)
    ])

    m2.setObjective(opex_expr, GRB.MINIMIZE)

    # Solve
    start_time = time.time()
    m2.optimize()
    s2_runtime = time.time() - start_time

    if m2.status == GRB.OPTIMAL or m2.status == GRB.TIME_LIMIT:
        return ('OPTIMAL' if m2.status == GRB.OPTIMAL else 'TIME_LIMIT'), s2_runtime, 0, {}

    elif m2.status == GRB.INFEASIBLE:
        m2.computeIIS()
        iis_constrs = [(c.ConstrName, c) for c in m2.getConstrs() if c.IISConstr]
        iis_count = len(iis_constrs)

        # Analyze IIS structure
        families = {}
        t_set, w_set, h_set = set(), set(), set()
        for name, c in iis_constrs:
            # Parse constraint family
            if 'bal_HP' in name:
                family = 'HP_storage_balance'
            elif 'bal_t' in name:
                family = 'trailer_balance'
            elif 'demand' in name:
                family = 'demand_satisfaction'
            elif 'seq' in name:
                family = 'trailer_sequencing'
            elif 'comp_trailer' in name:
                family = 'compression_trailer_coupling'
            elif 'trailer_count' in name:
                family = 'trailer_count'
            else:
                family = 'other'

            families[family] = families.get(family, 0) + 1

            # Extract t, w, h indices
            parts = name.split('_')
            for part in parts:
                if part.isdigit():
                    idx = int(part)
                    if idx <= T:
                        t_set.add(idx)
                    elif idx <= W:
                        w_set.add(idx)
                    else:
                        h_set.add(idx)

        iis_summary = {
            'families': families,
            't_range': (min(t_set), max(t_set)) if t_set else (None, None),
            'w_range': (min(w_set), max(w_set)) if w_set else (None, None),
            'h_range': (min(h_set), max(h_set)) if h_set else (None, None)
        }

        return 'INFEASIBLE', s2_runtime, iis_count, iis_summary

    else:
        return f'STATUS_{m2.status}', s2_runtime, 0, {}


def main():
    S0_VALUES = [158, 170, 180, 190, 200]  # Include baseline

    print("="*70)
    print("LIMITED S0 SENSITIVITY — SCREENING STAGE")
    print("="*70)
    print()
    print(f"Growth Rate: 15%")
    print(f"Lead Time: LT=1")
    print(f"S0 Range: {S0_VALUES} kg")
    print()

    results = []
    first_feasible_s0 = None

    for s0 in S0_VALUES:
        print(f"\n{'='*70}")
        print(f"Testing S0 = {s0} kg")
        print(f"{'='*70}\n")

        # Run S1
        s1_status, s1_capex, s1_inv_plan, s1_runtime = run_sequential_s1_for_s0(s0)
        print(f"S1 Status: {s1_status}, CAPEX: {s1_capex/10000:.2f}万元, Runtime: {s1_runtime:.1f}s")

        if s1_status != 'OPTIMAL':
            results.append({
                'S0': s0,
                'S1_status': s1_status,
                'S1_CAPEX_yuan': s1_capex,
                'S1_runtime_s': s1_runtime,
                'S2_status': 'SKIPPED'
            })
            continue

        # Run S2
        s2_status, s2_runtime, s2_iis_count, s2_iis_summary = run_sequential_s2_for_s0(s0, s1_inv_plan)
        print(f"S2 Status: {s2_status}, Runtime: {s2_runtime:.1f}s", end='')
        if s2_status == 'INFEASIBLE':
            print(f", IIS: {s2_iis_count} constraints")
        else:
            print()

        results.append({
            'S0': s0,
            'S1_status': s1_status,
            'S1_CAPEX_yuan': s1_capex,
            'S1_CAPEX_10k_yuan': s1_capex / 10000,
            'S1_runtime_s': s1_runtime,
            'S1_investment_plan': {
                'C_traj': s1_inv_plan['C_traj'],
                'S_traj': s1_inv_plan['S_traj'],
                'K_traj': s1_inv_plan['K_traj']
            },
            'S2_status': s2_status,
            'S2_runtime_s': s2_runtime,
            'S2_IIS_count': s2_iis_count,
            'S2_IIS_summary': s2_iis_summary
        })

        # Check for first FEASIBLE S2
        if s2_status in ['OPTIMAL', 'TIME_LIMIT'] and first_feasible_s0 is None:
            first_feasible_s0 = s0
            print(f"\n[✓] FEASIBLE CASE FOUND: S0={s0} kg")
            break

    # Save results
    output = {
        'experiment': 'S0_sensitivity_screening',
        'fixed_params': {
            'growth_rate': 0.15,
            'LT': 1,
            'S0_tested': S0_VALUES
        },
        'results': results,
        'first_feasible_S0': first_feasible_s0,
        'conclusion': 'SEQUENTIAL_RELIABILITY_CONDITION_FOUND' if first_feasible_s0 else 'NO_RELIABILITY_CONDITION_FOUND'
    }

    with open('s0_sensitivity_screening_result.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print("SCREENING SUMMARY")
    print(f"{'='*70}\n")
    print(f"{'S0':<6} {'S1':<12} {'S1 CAPEX':<12} {'S2':<12} {'IIS':<10}")
    print("-"*70)
    for r in results:
        s1_capex = f"{r['S1_CAPEX_10k_yuan']:.2f}万元" if 'S1_CAPEX_10k_yuan' in r else '—'
        iis = str(r['S2_IIS_count']) if r.get('S2_IIS_count', 0) > 0 else '—'
        print(f"{r['S0']:<6} {r['S1_status']:<12} {s1_capex:<12} {r['S2_status']:<12} {iis:<10}")

    if first_feasible_s0:
        print(f"\n[OK] SEQUENTIAL RELIABILITY CONDITION FOUND at S0={first_feasible_s0} kg")
    else:
        print(f"\n[X] NO RELIABILITY CONDITION FOUND IN TESTED RANGE")

    return output


if __name__ == '__main__':
    main()
