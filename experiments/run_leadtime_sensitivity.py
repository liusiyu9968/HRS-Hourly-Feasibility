"""
Lead-Time Sensitivity Analysis
Model Freeze v1.0

Tests impact of equipment lead time (LT) on station capacity planning.

Fixed: S0=158, growth=15%, Central Case
Variable: LT ∈ {0, 1, 2} years

Usage:
    python run_leadtime_sensitivity.py <LT_value>

Example:
    python run_leadtime_sensitivity.py 1  # LT=1 (baseline)
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


def run_leadtime_sensitivity(lt_value):
    """
    Run complete sensitivity analysis for given lead time.

    Parameters:
    -----------
    lt_value : int
        Lead time in years (0, 1, or 2)

    Returns:
    --------
    dict : Complete results for Sequential S1, S2, and Integrated
    """

    # Fixed configuration
    s0 = 158
    growth_rate = 0.15  # 15% annual growth (Core Baseline)

    print("="*70)
    print(f"LEAD-TIME SENSITIVITY: LT = {lt_value} years")
    print(f"Model Freeze v1.0 | S0={s0} | Growth=15% | Central Case")
    print("="*70)

    # Load parameters
    params = get_params('central')

    # Override lead times with sensitivity parameter
    params['LT_C'] = lt_value
    params['LT_S'] = lt_value
    params['LT_K'] = lt_value

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

    # Compute growth multipliers (rho)
    T = 5
    rho = [(1 + growth_rate)**t for t in range(T)]

    print(f"\nGrowth multipliers (rho): {[f'{r:.4f}' for r in rho]}")
    print(f"Lead times: LT_C={params['LT_C']}, LT_S={params['LT_S']}, LT_K={params['LT_K']}")

    # Store parameters
    p = params.copy()
    p.update({
        'T': T,
        'W': len(weeks_data),
        'H': 168,
        'rho': rho,
        'omega': [weeks_data[w+1]['weight'] for w in range(len(weeks_data))],
        'S_0': s0
    })

    results = {
        'lt_value': lt_value,
        'growth_rate': growth_rate,
        'rho': rho,
        's0': s0,
        'model_version': 'Model Freeze v1.0',
        'computational_budget': 'PRIMARY (TimeLimit=1800s, MIPGap=0.001)'
    }

    # ============================================================
    # SEQUENTIAL STAGE 1: Aggregated Capacity Planning
    # ============================================================

    print("\n" + "="*70)
    print("SEQUENTIAL STAGE 1: Aggregated Capacity Planning")
    print("="*70)

    m1 = gp.Model("SeqS1_LT" + str(lt_value))

    m1.setParam('OutputFlag', 1)
    m1.setParam('MIPGap', 0.001)
    m1.setParam('TimeLimit', 300)

    # Decision variables
    x_C, x_S, x_K = {}, {}, {}
    y_C, y_S, y_K = {}, {}, {}
    C_total, S_total, K_total = {}, {}, {}

    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            x_C[c,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_C_{c}_{t}')
            y_C[c,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_C_{c}_{t}')
        for s in range(len(p['Delta_S_options'])):
            x_S[s,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_S_{s}_{t}')
            y_S[s,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_S_{s}_{t}')
        for k in range(len(p['Delta_K_options'])):
            x_K[k,t] = m1.addVar(vtype=GRB.BINARY, name=f'x_K_{k}_{t}')
            y_K[k,t] = m1.addVar(vtype=GRB.BINARY, name=f'y_K_{k}_{t}')

        C_total[t] = m1.addVar(lb=0, name=f'C_total_{t}')
        S_total[t] = m1.addVar(lb=0, name=f'S_total_{t}')
        K_total[t] = m1.addVar(lb=0, name=f'K_total_{t}')

    m1.update()

    # Constraints: Each expansion option used at most once
    for c in range(len(p['Delta_C_options'])):
        m1.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1)
    for s in range(len(p['Delta_S_options'])):
        m1.addConstr(gp.quicksum(x_S[s,t] for t in range(1, T+1)) <= 1)
    for k in range(len(p['Delta_K_options'])):
        m1.addConstr(gp.quicksum(x_K[k,t] for t in range(1, T+1)) <= 1)

    # Lead time constraints
    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            m1.addConstr(y_C[c,t] == gp.quicksum(x_C[c,tau] for tau in range(1, max(0, t-p['LT_C'])+1)))
        for s in range(len(p['Delta_S_options'])):
            m1.addConstr(y_S[s,t] == gp.quicksum(x_S[s,tau] for tau in range(1, max(0, t-p['LT_S'])+1)))
        for k in range(len(p['Delta_K_options'])):
            m1.addConstr(y_K[k,t] == gp.quicksum(x_K[k,tau] for tau in range(1, max(0, t-p['LT_K'])+1)))

    # Total capacity
    for t in range(1, T+1):
        m1.addConstr(C_total[t] == p['C_0'] + gp.quicksum(p['Delta_C_options'][c][0]*y_C[c,t] for c in range(len(p['Delta_C_options']))))
        m1.addConstr(S_total[t] == p['S_0'] + gp.quicksum(p['Delta_S_options'][s][0]*y_S[s,t] for s in range(len(p['Delta_S_options']))))
        m1.addConstr(K_total[t] == p['K_srv_0'] + gp.quicksum(p['Delta_K_options'][k][0]*y_K[k,t] for k in range(len(p['Delta_K_options']))))

    # Aggregated feasibility constraints
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        B_avail = m1.addVar(lb=0)
        m1.addConstr(B_avail == S_total[t] - p['I_HP_0'])

        for w in range(p['W']):
            week = weeks_data[w+1]
            # Service capacity
            m1.addConstr(K_total[t] >= rho_t * week['G_peak'])
            # Demand windows with buffer
            m1.addConstr(rho_t * week['D_1h'] <= C_total[t] + B_avail)
            m1.addConstr(rho_t * week['D_2h'] <= 2*C_total[t] + B_avail)
            m1.addConstr(rho_t * week['D_4h'] <= 4*C_total[t] + B_avail)

    # Objective: Minimize CAPEX
    capex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            gp.quicksum(p['Delta_C_options'][c][1]*x_C[c,t] for c in range(len(p['Delta_C_options']))) +
            gp.quicksum(p['Delta_S_options'][s][1]*x_S[s,t] for s in range(len(p['Delta_S_options']))) +
            gp.quicksum(p['Delta_K_options'][k][1]*x_K[k,t] for k in range(len(p['Delta_K_options'])))
        )
        for t in range(1, T+1)
    )
    m1.setObjective(capex, GRB.MINIMIZE)

    print(f"\nOptimizing Sequential Stage 1...")
    t0_s1 = time.time()
    m1.optimize()
    t1_s1 = time.time()

    seq_s1_result = {
        'status': m1.Status,
        'feasible': False,
        'runtime': t1_s1 - t0_s1,
        'variable_count': m1.NumVars,
        'constraint_count': m1.NumConstrs
    }

    if m1.Status == GRB.OPTIMAL:
        seq_s1_result['status_str'] = 'OPTIMAL'
        seq_s1_result['feasible'] = True
        seq_s1_result['capex'] = m1.ObjVal

        # Extract investments
        investments = []
        for t in range(1, T+1):
            for c in range(len(p['Delta_C_options'])):
                if x_C[c,t].X > 0.5:
                    cap, cost = p['Delta_C_options'][c]
                    investments.append([t, 'C', cap, cost])
            for s in range(len(p['Delta_S_options'])):
                if x_S[s,t].X > 0.5:
                    cap, cost = p['Delta_S_options'][s]
                    investments.append([t, 'S', cap, cost])
            for k in range(len(p['Delta_K_options'])):
                if x_K[k,t].X > 0.5:
                    cap, cost = p['Delta_K_options'][k]
                    investments.append([t, 'K', cap, cost])

        seq_s1_result['investments'] = investments

        # Extract capacity trajectory
        capacity = {}
        for t in range(1, T+1):
            capacity[str(t)] = {
                'C': C_total[t].X,
                'S': S_total[t].X,
                'K': K_total[t].X
            }
        seq_s1_result['capacity'] = capacity

        print(f"\nSeq S1 Result:")
        print(f"  Status: OPTIMAL")
        print(f"  CAPEX: {m1.ObjVal/10000:.2f} 万元")
        print(f"  Runtime: {t1_s1-t0_s1:.2f}s")
        print(f"  Investments: {len(investments)}")
        for inv in investments:
            print(f"    T={inv[0]}: {inv[1]}+{inv[2]} ({inv[3]/10000:.0f}万元)")

    else:
        seq_s1_result['status_str'] = f'Status={m1.Status}'
        print(f"\nSeq S1: FAILED (Status={m1.Status})")
        results['sequential_s1'] = seq_s1_result
        return results

    results['sequential_s1'] = seq_s1_result

    # ============================================================
    # SEQUENTIAL STAGE 2: Hourly Operational Verification
    # ============================================================

    print("\n" + "="*70)
    print("SEQUENTIAL STAGE 2: Hourly Operational Verification")
    print("="*70)

    # Compute fixed capacities from Stage 1 investment plan
    C_fixed = {t: p['C_0'] for t in range(1, T+1)}
    S_fixed = {t: p['S_0'] for t in range(1, T+1)}
    K_fixed = {t: p['K_srv_0'] for t in range(1, T+1)}

    for inv in investments:
        inv_t, eq_type, cap, _ = inv
        op_t = inv_t + p['LT_C']  # Operational from this period
        if eq_type == 'C':
            for t in range(op_t, T+1):
                C_fixed[t] += cap
        elif eq_type == 'S':
            for t in range(op_t, T+1):
                S_fixed[t] += cap
        elif eq_type == 'K':
            for t in range(op_t, T+1):
                K_fixed[t] += cap

    print(f"\nFixed capacity trajectory from Stage 1:")
    for t in range(1, T+1):
        print(f"  T={t}: C={C_fixed[t]:.0f} kg/h, S={S_fixed[t]:.0f} kg, K={K_fixed[t]:.0f} min/h")

    m2 = gp.Model("SeqS2_LT" + str(lt_value))

    m2.setParam('OutputFlag', 1)
    m2.setParam('MIPGap', 0.001)
    m2.setParam('TimeLimit', 1800)

    # Operational variables
    a_arr, a_dep, z = {}, {}, {}
    I_trailer, Q_depart = {}, {}
    q_comp, I_HP, q_disp = {}, {}, {}

    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                a_arr[t,w,h] = m2.addVar(vtype=GRB.BINARY, name=f'a_arr_{t}_{w}_{h}')
                a_dep[t,w,h] = m2.addVar(vtype=GRB.BINARY, name=f'a_dep_{t}_{w}_{h}')
                z[t,w,h] = m2.addVar(vtype=GRB.BINARY, name=f'z_{t}_{w}_{h}')
                I_trailer[t,w,h] = m2.addVar(lb=0, name=f'I_trailer_{t}_{w}_{h}')
                Q_depart[t,w,h] = m2.addVar(lb=0, name=f'Q_depart_{t}_{w}_{h}')
                q_comp[t,w,h] = m2.addVar(lb=0, name=f'q_comp_{t}_{w}_{h}')
                I_HP[t,w,h] = m2.addVar(lb=0, name=f'I_HP_{t}_{w}_{h}')
                q_disp[t,w,h] = m2.addVar(lb=0, name=f'q_disp_{t}_{w}_{h}')

    m2.update()

    # Operational constraints
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']

            for h in range(p['H']):
                # Inventory dynamics
                if h == 0:
                    m2.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
                    m2.addConstr(I_trailer[t,w,h] == p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m2.addConstr(I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h])
                else:
                    m2.addConstr(z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h])
                    m2.addConstr(I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m2.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h])

                # Capacity and logical constraints
                m2.addConstr(z[t,w,h] <= 1)
                m2.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h])
                m2.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h])
                m2.addConstr(q_comp[t,w,h] <= C_fixed[t])
                m2.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h])
                m2.addConstr(I_HP[t,w,h] <= S_fixed[t])
                m2.addConstr(q_disp[t,w,h] == rho_t * demand[h])

                # Sequencing
                if h > 0:
                    m2.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                    m2.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                m2.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)

            # Weekly boundary
            m2.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'])
            m2.addConstr(z[t,w,p['H']-1] == 0)

    # Objective: Minimize OPEX
    opex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        gp.quicksum(
            p['c_H2']*q_disp[t,w,h] + p['c_elec']*q_comp[t,w,h] + p['c_trailer']*a_arr[t,w,h]
            for h in range(p['H'])
        )
        for t in range(1, T+1) for w in range(p['W'])
    )
    m2.setObjective(opex, GRB.MINIMIZE)

    print(f"\nOptimizing Sequential Stage 2...")
    t0_s2 = time.time()
    m2.optimize()
    t1_s2 = time.time()

    seq_s2_result = {
        'status': m2.Status,
        'feasible': False,
        'runtime': t1_s2 - t0_s2,
        'variable_count': m2.NumVars,
        'constraint_count': m2.NumConstrs
    }

    if m2.Status == 2 or (m2.Status == 9 and m2.SolCount > 0):
        seq_s2_result['status_str'] = 'OPTIMAL' if m2.Status == 2 else 'TIME_LIMIT_INCUMBENT'
        seq_s2_result['feasible'] = True
        seq_s2_result['opex'] = m2.ObjVal
        seq_s2_result['gap'] = m2.MIPGap

        print(f"\nSeq S2 Result:")
        print(f"  Status: {seq_s2_result['status_str']}")
        print(f"  OPEX: {m2.ObjVal/10000:.2f} 万元")
        print(f"  Gap: {m2.MIPGap*100:.4f}%")
        print(f"  Runtime: {t1_s2-t0_s2:.2f}s")

    elif m2.Status == 3:
        seq_s2_result['status_str'] = 'INFEASIBLE'
        print(f"\nSeq S2: INFEASIBLE (Status=3)")
        print(f"  Runtime: {t1_s2-t0_s2:.2f}s")

        # Compute IIS
        print("\n  Computing IIS...")
        m2.computeIIS()
        iis_constrs = [c.ConstrName for c in m2.getConstrs() if c.IISConstr]
        seq_s2_result['IIS_count'] = len(iis_constrs)
        print(f"  IIS constraints: {len(iis_constrs)}")

    else:
        seq_s2_result['status_str'] = f'Status={m2.Status}'
        if m2.Status == 9:
            seq_s2_result['status_str'] += '_NO_INCUMBENT'
        print(f"\nSeq S2: {seq_s2_result['status_str']}")
        print(f"  Runtime: {t1_s2-t0_s2:.2f}s")

    results['sequential_s2'] = seq_s2_result

    # ============================================================
    # INTEGRATED: Joint Investment + Operations Optimization
    # ============================================================

    print("\n" + "="*70)
    print("INTEGRATED: Joint Investment + Operations Optimization")
    print("="*70)

    m3 = gp.Model("Integrated_LT" + str(lt_value))

    m3.setParam('OutputFlag', 1)
    m3.setParam('MIPGap', 0.001)
    m3.setParam('TimeLimit', 1800)

    # Investment variables
    x_C_int, x_S_int, x_K_int = {}, {}, {}
    y_C_int, y_S_int, y_K_int = {}, {}, {}
    C_t, S_t, K_t = {}, {}, {}

    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            x_C_int[c,t] = m3.addVar(vtype=GRB.BINARY, name=f'x_C_{c}_{t}')
            y_C_int[c,t] = m3.addVar(vtype=GRB.BINARY, name=f'y_C_{c}_{t}')
        for s in range(len(p['Delta_S_options'])):
            x_S_int[s,t] = m3.addVar(vtype=GRB.BINARY, name=f'x_S_{s}_{t}')
            y_S_int[s,t] = m3.addVar(vtype=GRB.BINARY, name=f'y_S_{s}_{t}')
        for k in range(len(p['Delta_K_options'])):
            x_K_int[k,t] = m3.addVar(vtype=GRB.BINARY, name=f'x_K_{k}_{t}')
            y_K_int[k,t] = m3.addVar(vtype=GRB.BINARY, name=f'y_K_{k}_{t}')

        C_t[t] = m3.addVar(lb=0, name=f'C_{t}')
        S_t[t] = m3.addVar(lb=0, name=f'S_{t}')
        K_t[t] = m3.addVar(lb=0, name=f'K_{t}')

    # Operational variables
    a_arr_int, a_dep_int, z_int = {}, {}, {}
    I_trailer_int, Q_depart_int = {}, {}
    q_comp_int, I_HP_int, q_disp_int = {}, {}, {}

    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                a_arr_int[t,w,h] = m3.addVar(vtype=GRB.BINARY, name=f'a_arr_{t}_{w}_{h}')
                a_dep_int[t,w,h] = m3.addVar(vtype=GRB.BINARY, name=f'a_dep_{t}_{w}_{h}')
                z_int[t,w,h] = m3.addVar(vtype=GRB.BINARY, name=f'z_{t}_{w}_{h}')
                I_trailer_int[t,w,h] = m3.addVar(lb=0, name=f'I_trailer_{t}_{w}_{h}')
                Q_depart_int[t,w,h] = m3.addVar(lb=0, name=f'Q_depart_{t}_{w}_{h}')
                q_comp_int[t,w,h] = m3.addVar(lb=0, name=f'q_comp_{t}_{w}_{h}')
                I_HP_int[t,w,h] = m3.addVar(lb=0, name=f'I_HP_{t}_{w}_{h}')
                q_disp_int[t,w,h] = m3.addVar(lb=0, name=f'q_disp_{t}_{w}_{h}')

    m3.update()

    # Investment constraints
    for c in range(len(p['Delta_C_options'])):
        m3.addConstr(gp.quicksum(x_C_int[c,t] for t in range(1, T+1)) <= 1)
    for s in range(len(p['Delta_S_options'])):
        m3.addConstr(gp.quicksum(x_S_int[s,t] for t in range(1, T+1)) <= 1)
    for k in range(len(p['Delta_K_options'])):
        m3.addConstr(gp.quicksum(x_K_int[k,t] for t in range(1, T+1)) <= 1)

    # Lead time constraints
    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            m3.addConstr(y_C_int[c,t] == gp.quicksum(x_C_int[c,tau] for tau in range(1, max(0, t-p['LT_C'])+1)))
        for s in range(len(p['Delta_S_options'])):
            m3.addConstr(y_S_int[s,t] == gp.quicksum(x_S_int[s,tau] for tau in range(1, max(0, t-p['LT_S'])+1)))
        for k in range(len(p['Delta_K_options'])):
            m3.addConstr(y_K_int[k,t] == gp.quicksum(x_K_int[k,tau] for tau in range(1, max(0, t-p['LT_K'])+1)))

        # Total capacity
        m3.addConstr(C_t[t] == p['C_0'] + gp.quicksum(p['Delta_C_options'][c][0]*y_C_int[c,t] for c in range(len(p['Delta_C_options']))))
        m3.addConstr(S_t[t] == p['S_0'] + gp.quicksum(p['Delta_S_options'][s][0]*y_S_int[s,t] for s in range(len(p['Delta_S_options']))))
        m3.addConstr(K_t[t] == p['K_srv_0'] + gp.quicksum(p['Delta_K_options'][k][0]*y_K_int[k,t] for k in range(len(p['Delta_K_options']))))

    # Service capacity constraints (K constraint)
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            G_peak = weeks_data[w+1]['G_peak']
            m3.addConstr(K_t[t] >= rho_t * G_peak, name=f'service_capacity_t{t}_w{w}')

    # Operational constraints
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']

            for h in range(p['H']):
                # Inventory dynamics
                if h == 0:
                    m3.addConstr(z_int[t,w,h] == a_arr_int[t,w,h] - a_dep_int[t,w,h])
                    m3.addConstr(I_trailer_int[t,w,h] == p['Q_trailer']*a_arr_int[t,w,h] - q_comp_int[t,w,h] - Q_depart_int[t,w,h])
                    m3.addConstr(I_HP_int[t,w,h] == p['I_HP_0'] + q_comp_int[t,w,h] - q_disp_int[t,w,h])
                else:
                    m3.addConstr(z_int[t,w,h] == z_int[t,w,h-1] + a_arr_int[t,w,h] - a_dep_int[t,w,h])
                    m3.addConstr(I_trailer_int[t,w,h] == I_trailer_int[t,w,h-1] + p['Q_trailer']*a_arr_int[t,w,h] - q_comp_int[t,w,h] - Q_depart_int[t,w,h])
                    m3.addConstr(I_HP_int[t,w,h] == I_HP_int[t,w,h-1] + q_comp_int[t,w,h] - q_disp_int[t,w,h])

                # Capacity and logical constraints
                m3.addConstr(z_int[t,w,h] <= 1)
                m3.addConstr(I_trailer_int[t,w,h] <= p['M'] * z_int[t,w,h])
                m3.addConstr(Q_depart_int[t,w,h] <= p['M'] * a_dep_int[t,w,h])
                m3.addConstr(q_comp_int[t,w,h] <= C_t[t])
                m3.addConstr(q_comp_int[t,w,h] <= p['M'] * z_int[t,w,h])
                m3.addConstr(I_HP_int[t,w,h] <= S_t[t])
                m3.addConstr(q_disp_int[t,w,h] == rho_t * demand[h])

                # Sequencing
                if h > 0:
                    m3.addConstr(a_dep_int[t,w,h] <= z_int[t,w,h-1])
                    m3.addConstr(a_arr_int[t,w,h] <= 1 - z_int[t,w,h-1])
                m3.addConstr(a_arr_int[t,w,h] + a_dep_int[t,w,h] <= 1)

            # Weekly boundary
            m3.addConstr(I_HP_int[t,w,p['H']-1] == p['I_HP_0'])
            m3.addConstr(z_int[t,w,p['H']-1] == 0)

    # Objective: Minimize CAPEX + OPEX
    capex_int = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            gp.quicksum(p['Delta_C_options'][c][1]*x_C_int[c,t] for c in range(len(p['Delta_C_options']))) +
            gp.quicksum(p['Delta_S_options'][s][1]*x_S_int[s,t] for s in range(len(p['Delta_S_options']))) +
            gp.quicksum(p['Delta_K_options'][k][1]*x_K_int[k,t] for k in range(len(p['Delta_K_options'])))
        )
        for t in range(1, T+1)
    )

    opex_int = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        gp.quicksum(
            p['c_H2']*q_disp_int[t,w,h] + p['c_elec']*q_comp_int[t,w,h] + p['c_trailer']*a_arr_int[t,w,h]
            for h in range(p['H'])
        )
        for t in range(1, T+1) for w in range(p['W'])
    )

    m3.setObjective(capex_int + opex_int, GRB.MINIMIZE)

    print(f"\nOptimizing Integrated...")
    print(f"  Model size: {m3.NumVars} vars, {m3.NumConstrs} constrs")

    t0_int = time.time()
    m3.optimize()
    t1_int = time.time()

    int_result = {
        'status': m3.Status,
        'feasible': False,
        'runtime': t1_int - t0_int,
        'variable_count': m3.NumVars,
        'constraint_count': m3.NumConstrs
    }

    if m3.SolCount > 0:
        int_result['feasible'] = True
        int_result['total_cost'] = m3.ObjVal
        int_result['gap'] = m3.MIPGap
        int_result['best_bound'] = m3.ObjBound

        # Compute CAPEX and OPEX separately
        capex_val = sum(
            (1/(1+p['discount_rate'])**(t-1)) * (
                sum(
                    p['Delta_C_options'][c][1]*x_C_int[c,t].X for c in range(len(p['Delta_C_options']))
                ) + sum(
                    p['Delta_S_options'][s][1]*x_S_int[s,t].X for s in range(len(p['Delta_S_options']))
                ) + sum(
                    p['Delta_K_options'][k][1]*x_K_int[k,t].X for k in range(len(p['Delta_K_options']))
                )
            )
            for t in range(1, T+1)
        )

        opex_val = sum(
            (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] * sum(
                p['c_H2']*q_disp_int[t,w,h].X + p['c_elec']*q_comp_int[t,w,h].X + p['c_trailer']*a_arr_int[t,w,h].X
                for h in range(p['H'])
            )
            for t in range(1, T+1) for w in range(p['W'])
        )

        int_result['capex'] = capex_val
        int_result['opex'] = opex_val

        # Extract investments
        investments_int = []
        for t in range(1, T+1):
            for c in range(len(p['Delta_C_options'])):
                if x_C_int[c,t].X > 0.5:
                    cap, cost = p['Delta_C_options'][c]
                    investments_int.append([t, 'C', cap, cost])
            for s in range(len(p['Delta_S_options'])):
                if x_S_int[s,t].X > 0.5:
                    cap, cost = p['Delta_S_options'][s]
                    investments_int.append([t, 'S', cap, cost])
            for k in range(len(p['Delta_K_options'])):
                if x_K_int[k,t].X > 0.5:
                    cap, cost = p['Delta_K_options'][k]
                    investments_int.append([t, 'K', cap, cost])

        int_result['investments'] = investments_int

        # Extract capacity
        capacity_int = {}
        for t in range(1, T+1):
            capacity_int[str(t)] = {
                'C': C_t[t].X,
                'S': S_t[t].X,
                'K': K_t[t].X
            }
        int_result['capacity'] = capacity_int

        if m3.Status == 2:
            int_result['status_str'] = 'OPTIMAL'
        elif m3.Status == 9:
            int_result['status_str'] = 'TIME_LIMIT_INCUMBENT'

        print(f"\nIntegrated Result:")
        print(f"  Status: {int_result['status_str']}")
        print(f"  Total Cost: {int_result['total_cost']/10000:.2f} 万元")
        print(f"  CAPEX: {int_result['capex']/10000:.2f} 万元")
        print(f"  OPEX: {int_result['opex']/10000:.2f} 万元")
        print(f"  Gap: {int_result['gap']:.6f} ({int_result['gap']*100:.4f}%)")
        print(f"  Runtime: {t1_int-t0_int:.2f}s")
        print(f"  Investments: {len(investments_int)}")
        for inv in investments_int:
            print(f"    T={inv[0]}: {inv[1]}+{inv[2]} ({inv[3]/10000:.0f}万元)")

        # Export full hourly solution (8400 hours)
        print(f"\nExporting full hourly solution (8400 hours)...")
        hourly_data = []
        for t in range(1, T+1):
            rho_t = rho[t-1]
            C_val = capacity_int[str(t)]['C']
            S_val = capacity_int[str(t)]['S']
            K_val = capacity_int[str(t)]['K']

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
                        'q_comp': q_comp_int[t,w,h].X,
                        'q_disp': q_disp_int[t,w,h].X,
                        'I_HP': I_HP_int[t,w,h].X,
                        'trailer_presence': z_int[t,w,h].X,
                        'trailer_arrival': a_arr_int[t,w,h].X,
                        'trailer_departure': a_dep_int[t,w,h].X,
                        'trailer_inventory': I_trailer_int[t,w,h].X,
                        'trailer_delivery': Q_depart_int[t,w,h].X
                    })

        hourly_df = pd.DataFrame(hourly_data)
        hourly_file = f'leadtime{lt_value}_growth15_integrated_hourly.csv'
        hourly_df.to_csv(hourly_file, index=False, float_format='%.6f')
        print(f"  Saved {len(hourly_data)} hourly records to {hourly_file}")

    elif m3.Status == 3:
        int_result['status_str'] = 'INFEASIBLE'
        print(f"\nIntegrated: INFEASIBLE (Status=3)")
        print(f"  Runtime: {t1_int-t0_int:.2f}s")

    else:
        int_result['status_str'] = f'Status={m3.Status}_NO_INCUMBENT'
        print(f"\nIntegrated: {int_result['status_str']}")
        print(f"  Runtime: {t1_int-t0_int:.2f}s")

    results['integrated'] = int_result

    return results


if __name__ == '__main__':
    if len(sys.argv) > 1:
        lt_value = int(sys.argv[1])
    else:
        lt_value = 1  # Default: LT=1 (baseline)

    if lt_value not in [0, 1, 2]:
        print(f"Error: LT must be 0, 1, or 2 (got {lt_value})")
        sys.exit(1)

    results = run_leadtime_sensitivity(lt_value)

    # Save results
    output_file = f'leadtime{lt_value}_sensitivity_result.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Results saved to: {output_file}")
    print("="*70)
