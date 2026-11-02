"""
Growth Sensitivity Harness v2.0

Purpose: Unified sensitivity script for growth rate experiments
         - Harness Gate: growth=15% (reproduce Core Baseline v2.0)
         - Future: growth=10%, 20%

Model Version: Model Freeze v1.0
Computational Budget: PRIMARY (TimeLimit=1800s, MIPGap=0.001)

Fixed Parameters:
- S0 = 158 kg
- LT = 1 year (all equipment)
- Cost scenario = Central Case
- Representative weeks = FixedEP_W10_FINAL.csv
- Parameters = unified_params.py
- Solver = Gurobi 11.0.3
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, '../data/parameters')
from unified_params import get_params

def run_growth_sensitivity(growth_rate):
    """
    Run complete sensitivity experiment for specified growth rate

    Args:
        growth_rate: Annual demand growth rate (e.g., 0.10, 0.15, 0.20)

    Returns:
        dict with Sequential S1/S2 and Integrated results
    """

    print("="*70)
    print(f"GROWTH SENSITIVITY: growth_rate = {growth_rate:.0%}")
    print(f"Model Freeze v1.0 | S0=158 | LT=1 | Central Case")
    print("="*70)

    # Load parameters and data
    params = get_params('central')
    df = pd.read_csv('../data/processed/representative_weeks_FixedEP_W10_FINAL.csv', encoding='utf-8-sig')
    df['hour'] = pd.to_datetime(df['hour'])

    weeks_data = {}
    for week_id in sorted(df['representative_week_id'].unique()):
        week_data = df[df['representative_week_id'] == week_id].sort_values('hour')
        weeks_data[int(week_id)] = {
            'demand': week_data['demand_kg'].values,
            'service': week_data['service_minutes'].values,
            'weight': week_data['weight'].values[0]
        }

    # Calculate growth multipliers
    T = 5
    rho = [(1 + growth_rate) ** (t-1) for t in range(1, T+1)]

    print(f"\nGrowth multipliers (rho): {[f'{r:.4f}' for r in rho]}")

    p = params.copy()
    p.update({
        'T': T,
        'W': len(weeks_data),
        'H': 168,
        'rho': rho,
        'omega': [weeks_data[w+1]['weight'] for w in range(len(weeks_data))],
        'S_0': 158
    })

    results = {
        'growth_rate': growth_rate,
        'rho': rho,
        's0': 158,
        'model_version': 'Model Freeze v1.0',
        'computational_budget': 'PRIMARY (TimeLimit=1800s, MIPGap=0.001)'
    }

    # ==========================================================================
    # SEQUENTIAL STAGE 1
    # ==========================================================================
    print(f"\n{'='*70}")
    print("SEQUENTIAL STAGE 1: Aggregated Capacity Planning")
    print("="*70)

    seq_s1_start = time.time()
    m1 = gp.Model("Sequential_S1")
    m1.setParam('OutputFlag', 1)
    m1.setParam('MIPGap', 0.001)
    m1.setParam('TimeLimit', 300)

    # Investment variables
    x_C, x_S, x_K = {}, {}, {}
    y_C, y_S, y_K = {}, {}, {}
    C_t, S_t, K_t = {}, {}, {}

    for t in range(1, T+1):
        for c in range(2):
            x_C[c,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_C_{c}_{t}')
            y_C[c,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_C_{c}_{t}')
        for s in range(2):
            x_S[s,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_S_{s}_{t}')
            y_S[s,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_S_{s}_{t}')
        for k in range(2):
            x_K[k,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_K_{k}_{t}')
            y_K[k,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_K_{k}_{t}')
        C_t[t] = m1.addVar(lb=0, name=f'C_{t}')
        S_t[t] = m1.addVar(lb=0, name=f'S_{t}')
        K_t[t] = m1.addVar(lb=0, name=f'K_{t}')

    m1.update()

    # Investment constraints
    for c in range(2):
        m1.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1, name=f'invest_C_{c}')
    for s in range(2):
        m1.addConstr(gp.quicksum(x_S[s,t] for t in range(1, T+1)) <= 1, name=f'invest_S_{s}')
    for k in range(2):
        m1.addConstr(gp.quicksum(x_K[k,t] for t in range(1, T+1)) <= 1, name=f'invest_K_{k}')

    for t in range(1, T+1):
        for c in range(2):
            m1.addConstr(y_C[c,t] == gp.quicksum(x_C[c,tau] for tau in range(1, max(0, t-p['LT_C'])+1)),
                        name=f'lead_C_{c}_{t}')
        for s in range(2):
            m1.addConstr(y_S[s,t] == gp.quicksum(x_S[s,tau] for tau in range(1, max(0, t-p['LT_S'])+1)),
                        name=f'lead_S_{s}_{t}')
        for k in range(2):
            m1.addConstr(y_K[k,t] == gp.quicksum(x_K[k,tau] for tau in range(1, max(0, t-p['LT_K'])+1)),
                        name=f'lead_K_{k}_{t}')

        m1.addConstr(C_t[t] == p['C_0'] + p['Delta_C_options'][0][0]*y_C[0,t] + p['Delta_C_options'][1][0]*y_C[1,t],
                    name=f'capacity_C_{t}')
        m1.addConstr(S_t[t] == p['S_0'] + p['Delta_S_options'][0][0]*y_S[0,t] + p['Delta_S_options'][1][0]*y_S[1,t],
                    name=f'capacity_S_{t}')
        m1.addConstr(K_t[t] == p['K_srv_0'] + p['Delta_K_options'][0][0]*y_K[0,t] + p['Delta_K_options'][1][0]*y_K[1,t],
                    name=f'capacity_K_{t}')

    # Aggregated adequacy constraints
    for t in range(1, T+1):
        rho_t = rho[t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']
            service = weeks_data[w+1]['service']

            D_1h = demand.max()
            D_2h = max([demand[i:i+2].sum() for i in range(167)])
            D_4h = max([demand[i:i+4].sum() for i in range(165)])
            G_peak = service.max()

            B_avail = S_t[t] - 50

            m1.addConstr(C_t[t] + B_avail >= rho_t * D_1h, name=f'agg_1h_t{t}_w{w}')
            m1.addConstr(2*C_t[t] + B_avail >= rho_t * D_2h, name=f'agg_2h_t{t}_w{w}')
            m1.addConstr(4*C_t[t] + B_avail >= rho_t * D_4h, name=f'agg_4h_t{t}_w{w}')
            m1.addConstr(K_t[t] >= rho_t * G_peak, name=f'service_t{t}_w{w}')

    # Objective: CAPEX
    capex = sum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            p['Delta_C_options'][0][1]*x_C[0,t] + p['Delta_C_options'][1][1]*x_C[1,t] +
            p['Delta_S_options'][0][1]*x_S[0,t] + p['Delta_S_options'][1][1]*x_S[1,t] +
            p['Delta_K_options'][0][1]*x_K[0,t] + p['Delta_K_options'][1][1]*x_K[1,t]
        )
        for t in range(1, T+1)
    )

    m1.setObjective(capex, GRB.MINIMIZE)

    print("\nOptimizing Sequential Stage 1...")
    m1.optimize()
    seq_s1_time = time.time() - seq_s1_start

    seq_s1_result = {
        'status': m1.Status,
        'status_str': 'OPTIMAL' if m1.Status == 2 else f'Status={m1.Status}',
        'feasible': m1.Status in [2, 9],
        'runtime': seq_s1_time,
        'variable_count': m1.NumVars,
        'constraint_count': m1.NumConstrs
    }

    if m1.Status in [2, 9]:
        seq_s1_result['capex'] = m1.ObjVal

        # Extract investments
        investments = []
        for t in range(1, T+1):
            for c in range(2):
                if x_C[c,t].X > 0.5:
                    delta_cap = p['Delta_C_options'][c][0]
                    cost = p['Delta_C_options'][c][1]
                    investments.append((t, 'C', delta_cap, cost))
            for s in range(2):
                if x_S[s,t].X > 0.5:
                    delta_cap = p['Delta_S_options'][s][0]
                    cost = p['Delta_S_options'][s][1]
                    investments.append((t, 'S', delta_cap, cost))
            for k in range(2):
                if x_K[k,t].X > 0.5:
                    delta_cap = p['Delta_K_options'][k][0]
                    cost = p['Delta_K_options'][k][1]
                    investments.append((t, 'K', delta_cap, cost))

        seq_s1_result['investments'] = investments

        # Extract capacity trajectory
        capacity = {}
        for t in range(1, T+1):
            capacity[t] = {
                'C': C_t[t].X,
                'S': S_t[t].X,
                'K': K_t[t].X
            }
        seq_s1_result['capacity'] = capacity

        print(f"\nSequential S1 Result:")
        print(f"  Status: {seq_s1_result['status_str']}")
        print(f"  CAPEX: {seq_s1_result['capex']:.2f} 万元")
        print(f"  Runtime: {seq_s1_time:.2f}s")
        print(f"  Investments: {len(investments)}")
        for inv_t, eq, cap, cost in investments:
            print(f"    T={inv_t}: {eq}+{cap} ({cost:.0f}万元)")

    else:
        print(f"\nSequential S1: {seq_s1_result['status_str']}")

    results['sequential_s1'] = seq_s1_result

    # ==========================================================================
    # SEQUENTIAL STAGE 2
    # ==========================================================================
    if not seq_s1_result['feasible']:
        print("\nSequential S1 INFEASIBLE, skipping Stage 2")
        results['sequential_s2'] = {'status': 'SKIPPED', 'feasible': False}
    else:
        print(f"\n{'='*70}")
        print("SEQUENTIAL STAGE 2: Hourly Operations Verification")
        print("="*70)

        seq_s2_start = time.time()

        # Fixed capacities from S1
        C_fixed = {t: seq_s1_result['capacity'][t]['C'] for t in range(1, T+1)}
        S_fixed = {t: seq_s1_result['capacity'][t]['S'] for t in range(1, T+1)}
        K_fixed = {t: seq_s1_result['capacity'][t]['K'] for t in range(1, T+1)}

        m2 = gp.Model("Sequential_S2")
        m2.setParam('OutputFlag', 0)
        m2.setParam('TimeLimit', 300)

        # Operational variables
        a_arr, a_dep, z = {}, {}, {}
        I_trailer, Q_depart = {}, {}
        q_comp, I_HP, q_disp = {}, {}, {}

        for t in range(1, T+1):
            for w in range(p['W']):
                for h in range(p['H']):
                    a_arr[t,w,h] = m2.addVar(vtype=GRB.BINARY)
                    a_dep[t,w,h] = m2.addVar(vtype=GRB.BINARY)
                    z[t,w,h] = m2.addVar(vtype=GRB.BINARY)
                    I_trailer[t,w,h] = m2.addVar(lb=0)
                    Q_depart[t,w,h] = m2.addVar(lb=0)
                    q_comp[t,w,h] = m2.addVar(lb=0)
                    I_HP[t,w,h] = m2.addVar(lb=0)
                    q_disp[t,w,h] = m2.addVar(lb=0)

        m2.update()

        # Hourly operational constraints
        for t in range(1, T+1):
            rho_t = rho[t-1]
            for w in range(p['W']):
                demand = weeks_data[w+1]['demand']
                service = weeks_data[w+1]['service']

                for h in range(p['H']):
                    if h == 0:
                        m2.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
                        m2.addConstr(I_trailer[t,w,h] == p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                        m2.addConstr(I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h])
                    else:
                        m2.addConstr(z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h])
                        m2.addConstr(I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                        m2.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h])

                    m2.addConstr(z[t,w,h] <= 1)
                    m2.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h])
                    m2.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h])
                    m2.addConstr(q_comp[t,w,h] <= C_fixed[t])
                    m2.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h])
                    m2.addConstr(I_HP[t,w,h] <= S_fixed[t])
                    m2.addConstr(q_disp[t,w,h] == rho_t * demand[h])

                    if h > 0:
                        m2.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                        m2.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                    m2.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)

                m2.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'])
                m2.addConstr(z[t,w,p['H']-1] == 0)

        m2.setObjective(0, GRB.MINIMIZE)

        print("\nOptimizing Sequential Stage 2...")
        m2.optimize()
        seq_s2_time = time.time() - seq_s2_start

        seq_s2_result = {
            'status': m2.Status,
            'feasible': m2.Status in [2, 9],
            'runtime': seq_s2_time,
            'variable_count': m2.NumVars,
            'constraint_count': m2.NumConstrs
        }

        if m2.Status == 3:  # INFEASIBLE
            print("\nSequential S2: INFEASIBLE")
            print("Computing IIS...")
            m2.computeIIS()
            iis_constrs = [c for c in m2.getConstrs() if c.IISConstr]
            seq_s2_result['status_str'] = 'INFEASIBLE'
            seq_s2_result['IIS_count'] = len(iis_constrs)
            print(f"  IIS Count: {len(iis_constrs)}")
        else:
            seq_s2_result['status_str'] = 'FEASIBLE' if m2.Status in [2, 9] else f'Status={m2.Status}'
            print(f"\nSequential S2: {seq_s2_result['status_str']}")

        results['sequential_s2'] = seq_s2_result

    # ==========================================================================
    # INTEGRATED
    # ==========================================================================
    print(f"\n{'='*70}")
    print("INTEGRATED: Joint Investment + Operations")
    print("="*70)

    int_start = time.time()
    m3 = gp.Model("Integrated")
    m3.setParam('OutputFlag', 1)
    m3.setParam('MIPGap', 0.001)
    m3.setParam('TimeLimit', 1800)

    # Investment variables (same as S1)
    x_C, x_S, x_K = {}, {}, {}
    y_C, y_S, y_K = {}, {}, {}
    C_t, S_t, K_t = {}, {}, {}

    for t in range(1, T+1):
        for c in range(2):
            x_C[c,t] = m3.addVar(vtype=GRB.BINARY)
            y_C[c,t] = m3.addVar(vtype=GRB.BINARY)
        for s in range(2):
            x_S[s,t] = m3.addVar(vtype=GRB.BINARY)
            y_S[s,t] = m3.addVar(vtype=GRB.BINARY)
        for k in range(2):
            x_K[k,t] = m3.addVar(vtype=GRB.BINARY)
            y_K[k,t] = m3.addVar(vtype=GRB.BINARY)
        C_t[t] = m3.addVar(lb=0)
        S_t[t] = m3.addVar(lb=0)
        K_t[t] = m3.addVar(lb=0)

    # Operational variables (same as S2)
    a_arr, a_dep, z = {}, {}, {}
    I_trailer, Q_depart = {}, {}
    q_comp, I_HP, q_disp = {}, {}, {}

    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                a_arr[t,w,h] = m3.addVar(vtype=GRB.BINARY)
                a_dep[t,w,h] = m3.addVar(vtype=GRB.BINARY)
                z[t,w,h] = m3.addVar(vtype=GRB.BINARY)
                I_trailer[t,w,h] = m3.addVar(lb=0)
                Q_depart[t,w,h] = m3.addVar(lb=0)
                q_comp[t,w,h] = m3.addVar(lb=0)
                I_HP[t,w,h] = m3.addVar(lb=0)
                q_disp[t,w,h] = m3.addVar(lb=0)

    m3.update()

    # Investment constraints (same as S1)
    for c in range(2):
        m3.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1)
    for s in range(2):
        m3.addConstr(gp.quicksum(x_S[s,t] for t in range(1, T+1)) <= 1)
    for k in range(2):
        m3.addConstr(gp.quicksum(x_K[k,t] for t in range(1, T+1)) <= 1)

    for t in range(1, T+1):
        for c in range(2):
            m3.addConstr(y_C[c,t] == gp.quicksum(x_C[c,tau] for tau in range(1, max(0, t-p['LT_C'])+1)))
        for s in range(2):
            m3.addConstr(y_S[s,t] == gp.quicksum(x_S[s,tau] for tau in range(1, max(0, t-p['LT_S'])+1)))
        for k in range(2):
            m3.addConstr(y_K[k,t] == gp.quicksum(x_K[k,tau] for tau in range(1, max(0, t-p['LT_K'])+1)))

        m3.addConstr(C_t[t] == p['C_0'] + p['Delta_C_options'][0][0]*y_C[0,t] + p['Delta_C_options'][1][0]*y_C[1,t])
        m3.addConstr(S_t[t] == p['S_0'] + p['Delta_S_options'][0][0]*y_S[0,t] + p['Delta_S_options'][1][0]*y_S[1,t])
        m3.addConstr(K_t[t] == p['K_srv_0'] + p['Delta_K_options'][0][0]*y_K[0,t] + p['Delta_K_options'][1][0]*y_K[1,t])

    # Operational constraints (same as S2, with C_t/S_t/K_t variables)
    for t in range(1, T+1):
        rho_t = rho[t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']
            service = weeks_data[w+1]['service']

            # Service capacity constraint (aggregate)
            G_peak = service.max()
            m3.addConstr(K_t[t] >= rho_t * G_peak)

            for h in range(p['H']):
                if h == 0:
                    m3.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
                    m3.addConstr(I_trailer[t,w,h] == p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m3.addConstr(I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h])
                else:
                    m3.addConstr(z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h])
                    m3.addConstr(I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m3.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h])

                m3.addConstr(z[t,w,h] <= 1)
                m3.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h])
                m3.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h])
                m3.addConstr(q_comp[t,w,h] <= C_t[t])
                m3.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h])
                m3.addConstr(I_HP[t,w,h] <= S_t[t])
                m3.addConstr(q_disp[t,w,h] == rho_t * demand[h])

                if h > 0:
                    m3.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                    m3.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                m3.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)

            m3.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'])
            m3.addConstr(z[t,w,p['H']-1] == 0)

    # Objective: CAPEX + OPEX
    capex = sum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            p['Delta_C_options'][0][1]*x_C[0,t] + p['Delta_C_options'][1][1]*x_C[1,t] +
            p['Delta_S_options'][0][1]*x_S[0,t] + p['Delta_S_options'][1][1]*x_S[1,t] +
            p['Delta_K_options'][0][1]*x_K[0,t] + p['Delta_K_options'][1][1]*x_K[1,t]
        )
        for t in range(1, T+1)
    )

    opex = sum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        sum(p['c_H2']*q_disp[t,w,h] + p['c_elec']*q_comp[t,w,h] + p['c_trailer']*a_arr[t,w,h]
            for h in range(p['H']))
        for t in range(1, T+1) for w in range(p['W'])
    )

    m3.setObjective(capex + opex, GRB.MINIMIZE)

    print("\nOptimizing Integrated...")
    m3.optimize()
    int_time = time.time() - int_start

    int_result = {
        'status': m3.Status,
        'feasible': m3.Status in [2, 9] and m3.SolCount > 0,
        'runtime': int_time,
        'variable_count': m3.NumVars,
        'constraint_count': m3.NumConstrs
    }

    if m3.SolCount > 0:
        int_result['total_cost'] = m3.ObjVal
        int_result['capex'] = capex.getValue()
        int_result['opex'] = opex.getValue()
        int_result['gap'] = m3.MIPGap if m3.Status == 9 else 0.0
        int_result['best_bound'] = m3.ObjBound if hasattr(m3, 'ObjBound') else m3.ObjVal

        # Extract investments
        investments = []
        for t in range(1, T+1):
            for c in range(2):
                if x_C[c,t].X > 0.5:
                    investments.append((t, 'C', p['Delta_C_options'][c][0], p['Delta_C_options'][c][1]))
            for s in range(2):
                if x_S[s,t].X > 0.5:
                    investments.append((t, 'S', p['Delta_S_options'][s][0], p['Delta_S_options'][s][1]))
            for k in range(2):
                if x_K[k,t].X > 0.5:
                    investments.append((t, 'K', p['Delta_K_options'][k][0], p['Delta_K_options'][k][1]))

        int_result['investments'] = investments

        # Extract capacity
        capacity = {}
        for t in range(1, T+1):
            capacity[t] = {
                'C': C_t[t].X,
                'S': S_t[t].X,
                'K': K_t[t].X
            }
        int_result['capacity'] = capacity

        if m3.Status == 2:
            int_result['status_str'] = 'OPTIMAL'
        elif m3.Status == 9:
            int_result['status_str'] = 'TIME_LIMIT_WITH_INCUMBENT'

        print(f"\nIntegrated Result:")
        print(f"  Status: {int_result['status_str']}")
        print(f"  Total Cost: {int_result['total_cost']:.2f} 万元")
        print(f"  CAPEX: {int_result['capex']:.2f} 万元")
        print(f"  OPEX: {int_result['opex']:.2f} 万元")
        print(f"  Gap: {int_result['gap']:.4f} ({int_result['gap']*100:.2f}%)")
        print(f"  Runtime: {int_time:.2f}s")
        print(f"  Investments: {len(investments)}")
        for inv_t, eq, cap, cost in investments:
            print(f"    T={inv_t}: {eq}+{cap} ({cost:.0f}万元)")

        # Export full hourly solution (5×10×168 = 8400 hours)
        print(f"\nExporting full hourly solution (8400 hours)...")
        hourly_data = []
        for t in range(1, T+1):
            rho_t = rho[t-1]
            C_val = capacity[t]['C']
            S_val = capacity[t]['S']
            K_val = capacity[t]['K']

            for w in range(p['W']):
                week_weight = p['omega'][w]
                demand_vec = weeks_data[w+1]['demand']
                service_vec = weeks_data[w+1]['service']

                for h in range(p['H']):
                    hourly_data.append({
                        't': t,
                        'week': w+1,
                        'hour': h,
                        'week_weight': week_weight,
                        'rho': rho_t,
                        'demand': demand_vec[h],
                        'service_minutes': service_vec[h],
                        'C_t': C_val,
                        'S_t': S_val,
                        'K_t': K_val,
                        'q_comp': q_comp[t,w,h].X,
                        'q_disp': q_disp[t,w,h].X,
                        'I_HP': I_HP[t,w,h].X,
                        'trailer_presence': z[t,w,h].X,
                        'trailer_arrival': a_arr[t,w,h].X,
                        'trailer_departure': a_dep[t,w,h].X,
                        'trailer_inventory': I_trailer[t,w,h].X,
                        'trailer_delivery': Q_depart[t,w,h].X
                    })

        hourly_df = pd.DataFrame(hourly_data)
        hourly_file = f'growth_{growth_rate*100:.0f}_integrated_hourly.csv'
        hourly_df.to_csv(hourly_file, index=False, float_format='%.6f')
        print(f"  Saved {len(hourly_data)} hourly records to {hourly_file}")

    else:
        int_result['status_str'] = f'Status={m3.Status}_NO_INCUMBENT'
        print(f"\nIntegrated: {int_result['status_str']}")

    results['integrated'] = int_result

    return results


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        growth_pct = float(sys.argv[1])
    else:
        growth_pct = 15.0  # Default: 15% (harness gate)

    growth_rate = growth_pct / 100.0

    results = run_growth_sensitivity(growth_rate)

    # Save results
    output_file = f'growth_{growth_pct:.0f}_sensitivity_result.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"Results saved to: {output_file}")
    print("="*70)
