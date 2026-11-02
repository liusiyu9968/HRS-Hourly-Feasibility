"""
Integrated-CAPEX-only Control Experiment
=========================================

Purpose:
    Isolate the effect of hourly operational constraints from objective function choice.

Design:
    - Same hourly operational constraints as Integrated (CAPEX+OPEX)
    - Same investment constraints as Integrated
    - **Different objective: min CAPEX only** (not CAPEX+OPEX)

Research Question:
    Is the CAPEX divergence between Sequential S1 and Integrated due to:
    (A) Objective function difference (CAPEX-only vs CAPEX+OPEX), or
    (B) Constraint representation (aggregated vs hourly)?

Control Logic:
    - Sequential S1: min CAPEX, aggregated constraints → 379.29万元 (infeasible hourly)
    - Final joint CAPEX+OPEX reference: feasible incumbent 4635.458174 (10^4 CNY),
      with CAPEX 635.541838 (10^4 CNY), TIME_LIMIT, MIP gap 0.2321%.
    - This control minimizes CAPEX only subject to hourly constraints.

Interpretation:
    - The reference CAPEX-only run reaches 635.541838 (10^4 CNY).
    - The joint model's recorded incumbent uses the same investment portfolio;
      this does not prove global lifecycle-cost optimality.

Model Freeze: v1.0
Configuration: Growth=15%, LT=1, S₀=158, Central Case (same as Core Baseline)
Code Base: run_leadtime_sensitivity.py (Integrated section, lines 406-620)
Modification: Single line (objective function)

Usage:
    python run_integrated_capex_only.py

Output:
    - integrated_capex_only_result.json
    - Three-model comparison table
    - Investment trajectory comparison
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
import time
import json
import sys
import hashlib
from datetime import datetime

sys.path.insert(0, '../../data/parameters')
from unified_params import get_params


def compute_file_hash(filepath):
    """Compute SHA256 hash of data file to verify input consistency."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def run_integrated_capex_only():
    """
    Integrated model with CAPEX-only objective.

    Identical to Integrated (CAPEX+OPEX) except objective function.
    All hourly operational constraints preserved.
    """

    # ============================================================
    # CONFIGURATION (LOCKED TO CORE BASELINE)
    # ============================================================

    s0 = 158
    growth_rate = 0.15  # 15% CAGR
    lt_value = 1  # 1-year lead time

    print("="*70)
    print("INTEGRATED-CAPEX-ONLY CONTROL EXPERIMENT")
    print("="*70)
    print(f"Model Freeze v1.0")
    print(f"Configuration: S0={s0}, Growth=15%, LT={lt_value}, Central Case")
    print(f"Objective: min CAPEX (NOT CAPEX+OPEX)")
    print(f"Constraints: Full hourly operational constraints (same as Integrated)")
    print("="*70)

    # Load parameters
    params = get_params('central')
    params['LT_C'] = lt_value
    params['LT_S'] = lt_value
    params['LT_K'] = lt_value

    # Load representative weeks
    data_file = '../../data/processed/representative_weeks_FixedEP_W10_FINAL.csv'
    print(f"\nData file: {data_file}")
    print(f"Computing file hash...")
    file_hash = compute_file_hash(data_file)
    print(f"SHA256: {file_hash[:16]}...{file_hash[-16:]}")

    df = pd.read_csv(data_file, encoding='utf-8-sig')
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
            'G_peak': service.max(),
            'weight': week_data['weight'].values[0]
        }

    print(f"Loaded {len(weeks_data)} representative weeks")
    print(f"Weekly weights: {[weeks_data[w+1]['weight'] for w in range(len(weeks_data))]}")
    print(f"Total weight: {sum(weeks_data[w+1]['weight'] for w in range(len(weeks_data)))}")

    # Growth multipliers
    T = 5
    rho = [(1 + growth_rate)**(t-1) for t in range(1, T+1)]
    print(f"\nGrowth multipliers (rho): {[f'{r:.4f}' for r in rho]}")

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

    print(f"\nModel configuration:")
    print(f"  Planning periods: T={T}")
    print(f"  Representative weeks: W={p['W']}")
    print(f"  Hours per week: H={p['H']}")
    print(f"  Initial capacities: C₀={p['C_0']} kg/h, S₀={s0} kg, K₀={p['K_srv_0']} kg/min")
    print(f"  Lead times: LT_C={p['LT_C']}, LT_S={p['LT_S']}, LT_K={p['LT_K']}")
    print(f"  Discount rate: r={p['discount_rate']*100:.0f}%")

    # ============================================================
    # BUILD INTEGRATED MODEL (CAPEX-ONLY OBJECTIVE)
    # ============================================================

    print("\n" + "="*70)
    print("BUILDING MODEL")
    print("="*70)

    m = gp.Model("Integrated_CAPEX_only")

    m.setParam('OutputFlag', 1)
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 1800)  # 30 minutes (same as baseline)
    m.setParam('Threads', 0)

    print(f"\nSolver configuration:")
    print(f"  MIP Gap target: 0.1%")
    print(f"  Time limit: 1800s (30 minutes)")

    # Investment decision variables
    x_C, x_S, x_K = {}, {}, {}
    y_C, y_S, y_K = {}, {}, {}
    C_t, S_t, K_t = {}, {}, {}

    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            x_C[c,t] = m.addVar(vtype=GRB.BINARY, name=f'x_C_{c}_{t}')
            y_C[c,t] = m.addVar(vtype=GRB.BINARY, name=f'y_C_{c}_{t}')
        for s in range(len(p['Delta_S_options'])):
            x_S[s,t] = m.addVar(vtype=GRB.BINARY, name=f'x_S_{s}_{t}')
            y_S[s,t] = m.addVar(vtype=GRB.BINARY, name=f'y_S_{s}_{t}')
        for k in range(len(p['Delta_K_options'])):
            x_K[k,t] = m.addVar(vtype=GRB.BINARY, name=f'x_K_{k}_{t}')
            y_K[k,t] = m.addVar(vtype=GRB.BINARY, name=f'y_K_{k}_{t}')

        C_t[t] = m.addVar(lb=0, name=f'C_{t}')
        S_t[t] = m.addVar(lb=0, name=f'S_{t}')
        K_t[t] = m.addVar(lb=0, name=f'K_{t}')

    # Operational variables (hourly dispatch)
    a_arr, a_dep, z = {}, {}, {}
    I_trailer, Q_depart = {}, {}
    q_comp, I_HP, q_disp = {}, {}, {}

    for t in range(1, T+1):
        for w in range(p['W']):
            for h in range(p['H']):
                a_arr[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f'a_arr_{t}_{w}_{h}')
                a_dep[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f'a_dep_{t}_{w}_{h}')
                z[t,w,h] = m.addVar(vtype=GRB.BINARY, name=f'z_{t}_{w}_{h}')
                I_trailer[t,w,h] = m.addVar(lb=0, name=f'I_trailer_{t}_{w}_{h}')
                Q_depart[t,w,h] = m.addVar(lb=0, name=f'Q_depart_{t}_{w}_{h}')
                q_comp[t,w,h] = m.addVar(lb=0, name=f'q_comp_{t}_{w}_{h}')
                I_HP[t,w,h] = m.addVar(lb=0, name=f'I_HP_{t}_{w}_{h}')
                q_disp[t,w,h] = m.addVar(lb=0, name=f'q_disp_{t}_{w}_{h}')

    m.update()

    print(f"\nModel size:")
    print(f"  Variables: {m.NumVars:,}")

    # ============================================================
    # INVESTMENT CONSTRAINTS (IDENTICAL TO INTEGRATED)
    # ============================================================

    print(f"\nAdding investment constraints...")

    # Each expansion option used at most once
    for c in range(len(p['Delta_C_options'])):
        m.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1, name=f'once_C_{c}')
    for s in range(len(p['Delta_S_options'])):
        m.addConstr(gp.quicksum(x_S[s,t] for t in range(1, T+1)) <= 1, name=f'once_S_{s}')
    for k in range(len(p['Delta_K_options'])):
        m.addConstr(gp.quicksum(x_K[k,t] for t in range(1, T+1)) <= 1, name=f'once_K_{k}')

    # Lead time constraints
    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            m.addConstr(
                y_C[c,t] == gp.quicksum(x_C[c,tau] for tau in range(1, max(1, t-p['LT_C']+1))),
                name=f'lt_C_{c}_{t}'
            )
        for s in range(len(p['Delta_S_options'])):
            m.addConstr(
                y_S[s,t] == gp.quicksum(x_S[s,tau] for tau in range(1, max(1, t-p['LT_S']+1))),
                name=f'lt_S_{s}_{t}'
            )
        for k in range(len(p['Delta_K_options'])):
            m.addConstr(
                y_K[k,t] == gp.quicksum(x_K[k,tau] for tau in range(1, max(1, t-p['LT_K']+1))),
                name=f'lt_K_{k}_{t}'
            )

        # Total capacity
        m.addConstr(
            C_t[t] == p['C_0'] + gp.quicksum(p['Delta_C_options'][c][0]*y_C[c,t] for c in range(len(p['Delta_C_options']))),
            name=f'cap_C_{t}'
        )
        m.addConstr(
            S_t[t] == p['S_0'] + gp.quicksum(p['Delta_S_options'][s][0]*y_S[s,t] for s in range(len(p['Delta_S_options']))),
            name=f'cap_S_{t}'
        )
        m.addConstr(
            K_t[t] == p['K_srv_0'] + gp.quicksum(p['Delta_K_options'][k][0]*y_K[k,t] for k in range(len(p['Delta_K_options']))),
            name=f'cap_K_{t}'
        )

    # Service capacity constraints (aggregated weekly)
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            G_peak = weeks_data[w+1]['G_peak']
            m.addConstr(K_t[t] >= rho_t * G_peak, name=f'service_t{t}_w{w+1}')

    # ============================================================
    # HOURLY OPERATIONAL CONSTRAINTS (IDENTICAL TO INTEGRATED)
    # ============================================================

    print(f"Adding hourly operational constraints...")
    print(f"  Total hours: {T} periods × {p['W']} weeks × {p['H']} hours = {T*p['W']*p['H']:,} hour-constraints")

    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']

            for h in range(p['H']):
                # Inventory dynamics
                if h == 0:
                    m.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h], name=f'z_init_t{t}_w{w}_h{h}')
                    m.addConstr(
                        I_trailer[t,w,h] == p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h],
                        name=f'I_tr_init_t{t}_w{w}_h{h}'
                    )
                    m.addConstr(
                        I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h],
                        name=f'I_HP_init_t{t}_w{w}_h{h}'
                    )
                else:
                    m.addConstr(
                        z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h],
                        name=f'z_dyn_t{t}_w{w}_h{h}'
                    )
                    m.addConstr(
                        I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h],
                        name=f'I_tr_dyn_t{t}_w{w}_h{h}'
                    )
                    m.addConstr(
                        I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h],
                        name=f'I_HP_dyn_t{t}_w{w}_h{h}'
                    )

                # Capacity and logical constraints
                m.addConstr(z[t,w,h] <= 1, name=f'z_max_t{t}_w{w}_h{h}')
                m.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h], name=f'I_tr_gate_t{t}_w{w}_h{h}')
                m.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h], name=f'Q_dep_gate_t{t}_w{w}_h{h}')
                m.addConstr(q_comp[t,w,h] <= C_t[t], name=f'comp_cap_t{t}_w{w}_h{h}')  # HOURLY COMPRESSION CONSTRAINT
                m.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h], name=f'comp_gate_t{t}_w{w}_h{h}')
                m.addConstr(I_HP[t,w,h] <= S_t[t], name=f'stor_cap_t{t}_w{w}_h{h}')  # HOURLY STORAGE CONSTRAINT
                m.addConstr(q_disp[t,w,h] == rho_t * demand[h], name=f'demand_t{t}_w{w}_h{h}')  # EXACT DEMAND SATISFACTION

                # Sequencing constraints
                if h > 0:
                    m.addConstr(a_dep[t,w,h] <= z[t,w,h-1], name=f'dep_seq_t{t}_w{w}_h{h}')
                    m.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1], name=f'arr_seq_t{t}_w{w}_h{h}')
                m.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1, name=f'arr_dep_excl_t{t}_w{w}_h{h}')

            # Weekly boundary conditions
            m.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'], name=f'I_HP_boundary_t{t}_w{w}')
            m.addConstr(z[t,w,p['H']-1] == 0, name=f'z_boundary_t{t}_w{w}')

    m.update()
    print(f"\nFinal model size:")
    print(f"  Variables: {m.NumVars:,}")
    print(f"  Constraints: {m.NumConstrs:,}")

    # ============================================================
    # OBJECTIVE FUNCTION: MIN CAPEX ONLY (CONTROL MODIFICATION)
    # ============================================================

    print("\n" + "="*70)
    print("OBJECTIVE FUNCTION")
    print("="*70)

    # CAPEX term (discounted investment cost)
    capex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            gp.quicksum(p['Delta_C_options'][c][1]*x_C[c,t] for c in range(len(p['Delta_C_options']))) +
            gp.quicksum(p['Delta_S_options'][s][1]*x_S[s,t] for s in range(len(p['Delta_S_options']))) +
            gp.quicksum(p['Delta_K_options'][k][1]*x_K[k,t] for k in range(len(p['Delta_K_options'])))
        )
        for t in range(1, T+1)
    )

    # OPEX term (defined for post-solve computation, NOT in objective)
    opex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        gp.quicksum(
            p['c_H2']*q_disp[t,w,h] + p['c_elec']*q_comp[t,w,h] + p['c_trailer']*a_arr[t,w,h]
            for h in range(p['H'])
        )
        for t in range(1, T+1) for w in range(p['W'])
    )

    # ★★★ CONTROL MODIFICATION: Minimize CAPEX only ★★★
    m.setObjective(capex, GRB.MINIMIZE)

    print(f"Objective: min CAPEX")
    print(f"  CAPEX term: Investment cost (discounted)")
    print(f"  OPEX term: NOT in objective (computed post-solve)")
    print(f"\n★ This is the ONLY difference from Integrated (CAPEX+OPEX) ★")

    # ============================================================
    # SOLVE
    # ============================================================

    print("\n" + "="*70)
    print("SOLVING")
    print("="*70)

    t_start = time.time()
    m.optimize()
    t_end = time.time()

    runtime = t_end - t_start

    print(f"\nSolver terminated:")
    print(f"  Status: {m.Status}")
    print(f"  Runtime: {runtime:.2f}s ({runtime/60:.1f} min)")

    # ============================================================
    # EXTRACT RESULTS
    # ============================================================

    result = {
        'experiment': 'integrated_capex_only',
        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
        'configuration': {
            'model_version': 'Model Freeze v1.0',
            'growth_rate': growth_rate,
            'LT': lt_value,
            's0': s0,
            'scenario': 'Central Case',
            'objective': 'min CAPEX (NOT CAPEX+OPEX)',
            'data_file': data_file,
            'data_hash': file_hash
        },
        'solver': {
            'status': m.Status,
            'runtime': runtime,
            'variable_count': m.NumVars,
            'constraint_count': m.NumConstrs
        }
    }

    if m.SolCount > 0:
        result['solver']['feasible'] = True
        result['solver']['gap'] = m.MIPGap
        result['solver']['best_bound'] = m.ObjBound

        # Compute CAPEX (objective value)
        capex_val = m.ObjVal
        result['costs'] = {
            'capex': capex_val,
            'capex_万元': capex_val / 10000
        }

        # Compute OPEX (from dispatch solution)
        opex_val = sum(
            (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] * sum(
                p['c_H2']*q_disp[t,w,h].X + p['c_elec']*q_comp[t,w,h].X + p['c_trailer']*a_arr[t,w,h].X
                for h in range(p['H'])
            )
            for t in range(1, T+1) for w in range(p['W'])
        )
        result['costs']['opex'] = opex_val
        result['costs']['opex_万元'] = opex_val / 10000
        result['costs']['opex_note'] = "Computed from CAPEX-minimizing dispatch; NOT minimum OPEX for this investment"

        # Total cost
        result['costs']['total'] = capex_val + opex_val
        result['costs']['total_万元'] = (capex_val + opex_val) / 10000

        # Status string
        if m.Status == 2:
            result['solver']['status_str'] = 'OPTIMAL'
            print(f"\n✅ OPTIMAL solution found")
        elif m.Status == 9:
            result['solver']['status_str'] = 'TIME_LIMIT'
            print(f"\n⏱ TIME_LIMIT reached with feasible incumbent")
        else:
            result['solver']['status_str'] = f'Status={m.Status}_INCUMBENT'
            print(f"\n✅ Feasible solution found (Status={m.Status})")

        print(f"\nCosts:")
        print(f"  CAPEX: {capex_val/10000:.2f} 万元")
        print(f"  OPEX: {opex_val/10000:.2f} 万元 (from CAPEX-minimizing dispatch)")
        print(f"  Total: {(capex_val+opex_val)/10000:.2f} 万元")
        print(f"  MIP Gap: {m.MIPGap*100:.4f}%")

        # Extract investments
        investments = []
        for t in range(1, T+1):
            for c in range(len(p['Delta_C_options'])):
                if x_C[c,t].X > 0.5:
                    cap, cost = p['Delta_C_options'][c]
                    investments.append({'period': t, 'asset': 'C', 'capacity': cap, 'cost': cost})
            for s in range(len(p['Delta_S_options'])):
                if x_S[s,t].X > 0.5:
                    cap, cost = p['Delta_S_options'][s]
                    investments.append({'period': t, 'asset': 'S', 'capacity': cap, 'cost': cost})
            for k in range(len(p['Delta_K_options'])):
                if x_K[k,t].X > 0.5:
                    cap, cost = p['Delta_K_options'][k]
                    investments.append({'period': t, 'asset': 'K', 'capacity': cap, 'cost': cost})

        result['investments'] = investments

        print(f"\nInvestment plan ({len(investments)} investments):")
        for inv in investments:
            print(f"  t={inv['period']}: {inv['asset']} +{inv['capacity']} → {inv['cost']/10000:.2f} 万元")

        # Capacity trajectory
        capacity = {}
        for t in range(1, T+1):
            capacity[str(t)] = {
                'C': C_t[t].X,
                'S': S_t[t].X,
                'K': K_t[t].X
            }
        result['capacity'] = capacity

        print(f"\nCapacity trajectory:")
        print(f"{'Period':<8} {'C (kg/h)':<12} {'S (kg)':<12} {'K (kg/min)':<12}")
        print("-"*44)
        for t in range(1, T+1):
            cap = capacity[str(t)]
            print(f"t={t:<6} {cap['C']:<12.1f} {cap['S']:<12.1f} {cap['K']:<12.1f}")

    else:
        result['solver']['feasible'] = False

        if m.Status == 3:
            result['solver']['status_str'] = 'INFEASIBLE'
            print(f"\n❌ INFEASIBLE")

            # Compute IIS
            print(f"\nComputing IIS...")
            m.computeIIS()
            iis_constrs = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
            result['solver']['IIS_count'] = len(iis_constrs)
            result['solver']['IIS_constraints'] = iis_constrs[:20]
            print(f"  IIS size: {len(iis_constrs)} constraints")
        else:
            result['solver']['status_str'] = f'Status={m.Status}_NO_INCUMBENT'
            print(f"\n❌ No feasible solution found (Status={m.Status})")

    return result


def main():
    print("\n")
    print("="*70)
    print("INTEGRATED-CAPEX-ONLY CONTROL EXPERIMENT")
    print("="*70)
    print()
    print("Purpose: Isolate hourly constraint effect from objective function choice")
    print()
    print("Design:")
    print("  - Same hourly constraints as Integrated (CAPEX+OPEX)")
    print("  - Different objective: min CAPEX only (not CAPEX+OPEX)")
    print()
    print("Comparison:")
    print("  - Sequential S1: min CAPEX, aggregated → 379.29万元 (infeasible)")
    print("  - Integrated C+: min CAPEX+OPEX, hourly → see corrected recorded result")
    print("  - This: min CAPEX, hourly → [TO BE DETERMINED]")
    print()
    print("="*70)
    print()

    # Run experiment
    result = run_integrated_capex_only()

    # Save results
    output_file = f"integrated_capex_only_result_{result['timestamp']}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Results saved to: {output_file}")

    return result


if __name__ == '__main__':
    main()
