"""
Fixed-Investment OPEX Minimization Control Experiment
======================================================

Purpose:
    After fixing all investment decisions from Model B (Integrated-CAPEX-only),
    re-optimize hourly operational dispatch to minimize OPEX.

Design:
    - Fix Model B's four investment purchases (timing + modules)
    - Fix Model B's five-year capacity trajectory
    - Optimize hourly dispatch only
    - Minimize discounted OPEX (NOT CAPEX)

Model Freeze: v1.0
Configuration: Growth=15%, LT=1, S₀=158, Central Case
Code Base: run_leadtime_sensitivity.py (Integrated operational constraints)
Modification: Fixed capacity parameters, OPEX-only objective

Usage:
    python run_fixed_investment_opex.py

Output:
    - fixed_investment_opex_result.json
    - fixed_investment_opex_gurobi.log
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


def verify_capacity_trajectory(investments, initial_C, initial_S, initial_K, LT, T):
    """
    Compute capacity trajectory from investment decisions and verify against expected.

    Returns: dict of capacity per period
    """
    # Initialize capacities
    C = {t: initial_C for t in range(1, T+1)}
    S = {t: initial_S for t in range(1, T+1)}
    K = {t: initial_K for t in range(1, T+1)}

    # Apply investments with lead time
    for inv in investments:
        purchase_period = inv['period']
        asset = inv['asset']
        capacity = inv['capacity']

        # Investment becomes operational after LT periods
        operational_period = purchase_period + LT

        if operational_period <= T:
            if asset == 'C':
                for t in range(operational_period, T+1):
                    C[t] += capacity
            elif asset == 'S':
                for t in range(operational_period, T+1):
                    S[t] += capacity
            elif asset == 'K':
                for t in range(operational_period, T+1):
                    K[t] += capacity

    return {'C': C, 'S': S, 'K': K}


def run_fixed_investment_opex():
    """
    Fixed-investment OPEX minimization model.

    Investment path locked to Model B's certified optimal decisions.
    Only hourly operational dispatch is optimized.
    """

    # ============================================================
    # LOAD MODEL B INVESTMENT PATH
    # ============================================================

    print("="*70)
    print("FIXED-INVESTMENT OPEX MINIMIZATION CONTROL EXPERIMENT")
    print("="*70)
    print("Purpose: Re-optimize hourly dispatch under Model B's fixed investment")
    print("="*70)

    model_b_result_file = '../integrated_capex_control/integrated_capex_only_result_20261028_212724.json'

    print(f"\nLoading Model B result: {model_b_result_file}")
    with open(model_b_result_file, 'r', encoding='utf-8') as f:
        model_b = json.load(f)

    # Extract locked investment decisions
    locked_investments = model_b['investments']
    locked_capex = model_b['costs']['capex']
    locked_opex_raw = model_b['costs']['opex']

    print(f"\nModel B (Integrated-CAPEX-only):")
    print(f"  Status: {model_b['solver']['status_str']}")
    print(f"  CAPEX: {locked_capex/10000:.6f} 万元 (OPTIMAL, proven)")
    print(f"  OPEX (raw): {locked_opex_raw/10000:.6f} 万元 (from CAPEX-minimizing dispatch)")

    print(f"\nLocked investment purchases ({len(locked_investments)} purchases):")
    for inv in locked_investments:
        print(f"  t={inv['period']}: {inv['asset']} +{inv['capacity']} → {inv['cost']/10000:.2f} 万元")

    # ============================================================
    # CONFIGURATION (LOCKED TO MODEL B)
    # ============================================================

    s0 = model_b['configuration']['s0']
    growth_rate = model_b['configuration']['growth_rate']
    lt_value = model_b['configuration']['LT']

    print(f"\nConfiguration (locked to Model B):")
    print(f"  Growth rate: {growth_rate*100:.0f}%")
    print(f"  Lead time: LT={lt_value}")
    print(f"  Initial storage: S₀={s0} kg")

    # Load parameters
    params = get_params('central')

    # Compute capacity trajectory from locked investments
    T = 5
    capacity_trajectory = verify_capacity_trajectory(
        locked_investments,
        initial_C=params['C_0'],
        initial_S=s0,
        initial_K=params['K_srv_0'],
        LT=lt_value,
        T=T
    )

    # Fixed capacity parameters (NOT decision variables)
    C_fixed = capacity_trajectory['C']
    S_fixed = capacity_trajectory['S']
    K_fixed = capacity_trajectory['K']

    print(f"\nFixed capacity trajectory (from locked investments):")
    print(f"{'Period':<8} {'C (kg/h)':<12} {'S (kg)':<12} {'K (min/h)':<12}")
    print("-"*44)
    for t in range(1, T+1):
        print(f"t={t:<6} {C_fixed[t]:<12.1f} {S_fixed[t]:<12.1f} {K_fixed[t]:<12.1f}")

    # Verify against Model B's reported capacity
    expected_capacity = model_b['capacity']
    for t in range(1, T+1):
        assert abs(C_fixed[t] - expected_capacity[str(t)]['C']) < 0.01, f"C mismatch at t={t}"
        assert abs(S_fixed[t] - expected_capacity[str(t)]['S']) < 0.01, f"S mismatch at t={t}"
        assert abs(K_fixed[t] - expected_capacity[str(t)]['K']) < 0.01, f"K mismatch at t={t}"
    print(f"✅ Capacity trajectory verified against Model B")

    # ============================================================
    # DATA INPUT (VERIFY HASH)
    # ============================================================

    data_file = '../../data/processed/representative_weeks_FixedEP_W10_FINAL.csv'
    expected_hash = model_b['configuration']['data_hash']

    print(f"\nData file: {data_file}")
    print(f"Computing SHA256 hash...")
    actual_hash = compute_file_hash(data_file)
    print(f"  Expected: {expected_hash}")
    print(f"  Actual:   {actual_hash}")

    if actual_hash != expected_hash:
        raise ValueError("Data file hash mismatch! Cannot proceed with comparison.")
    print(f"✅ Data file hash verified")

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
    rho = [(1 + growth_rate)**(t-1) for t in range(1, T+1)]
    print(f"Growth multipliers: {[f'{r:.4f}' for r in rho]}")

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

    # ============================================================
    # BUILD MODEL D: FIXED-INVESTMENT OPEX MINIMIZATION
    # ============================================================

    print("\n" + "="*70)
    print("BUILDING MODEL D: FIXED-INVESTMENT OPEX MINIMIZATION")
    print("="*70)

    m = gp.Model("Fixed_Investment_OPEX")

    m.setParam('OutputFlag', 1)
    m.setParam('LogFile', 'fixed_investment_opex_gurobi.log')
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 1800)  # 30 minutes
    m.setParam('Threads', 0)

    print(f"\nSolver configuration:")
    print(f"  MIP Gap target: 0.1%")
    print(f"  Time limit: 1800s (30 minutes)")

    print(f"\nDecision variables: Hourly operational dispatch ONLY")
    print(f"  Investment decisions: FIXED (from Model B)")

    # ============================================================
    # OPERATIONAL VARIABLES (IDENTICAL TO INTEGRATED)
    # ============================================================

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
    # HOURLY OPERATIONAL CONSTRAINTS (IDENTICAL TO INTEGRATED)
    # ============================================================

    print(f"\nAdding hourly operational constraints...")
    print(f"  (Identical to Integrated model, lines 485-518 in run_leadtime_sensitivity.py)")

    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            demand = weeks_data[w+1]['demand']

            for h in range(p['H']):
                # Inventory dynamics
                if h == 0:
                    m.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
                    m.addConstr(
                        I_trailer[t,w,h] == p['Q_trailer']*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h]
                    )
                    m.addConstr(
                        I_HP[t,w,h] == p['I_HP_0'] + q_comp[t,w,h] - q_disp[t,w,h]
                    )
                else:
                    m.addConstr(
                        z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h]
                    )
                    m.addConstr(
                        I_trailer[t,w,h] == I_trailer[t,w,h-1] + p['Q_trailer']*a_arr[t,w,h]
                                           - q_comp[t,w,h] - Q_depart[t,w,h]
                    )
                    m.addConstr(
                        I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h]
                    )

                # Capacity and logical constraints (★ FIXED CAPACITY)
                m.addConstr(z[t,w,h] <= 1)
                m.addConstr(I_trailer[t,w,h] <= p['M'] * z[t,w,h])
                m.addConstr(Q_depart[t,w,h] <= p['M'] * a_dep[t,w,h])
                m.addConstr(q_comp[t,w,h] <= C_fixed[t])  # ★ FIXED from Model B
                m.addConstr(q_comp[t,w,h] <= p['M'] * z[t,w,h])
                m.addConstr(I_HP[t,w,h] <= S_fixed[t])   # ★ FIXED from Model B
                m.addConstr(q_disp[t,w,h] == rho_t * demand[h])  # Exact demand

                # Sequencing constraints
                if h > 0:
                    m.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                    m.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                m.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)

            # Weekly boundary conditions
            m.addConstr(I_HP[t,w,p['H']-1] == p['I_HP_0'])
            m.addConstr(z[t,w,p['H']-1] == 0)

    # Service capacity verification (fixed capacity, parameter check)
    print(f"\nVerifying service capacity satisfaction...")
    service_violations = []
    for t in range(1, T+1):
        rho_t = p['rho'][t-1]
        for w in range(p['W']):
            G_peak = weeks_data[w+1]['G_peak']
            required_K = rho_t * G_peak
            if K_fixed[t] < required_K - 1e-3:
                service_violations.append((t, w+1, K_fixed[t], required_K))
                print(f"  WARNING: t={t}, w={w+1}: K_fixed={K_fixed[t]:.1f} < required {required_K:.1f}")

    if service_violations:
        print(f"  Found {len(service_violations)} service capacity violations")
        print(f"  Fixed capacity may not satisfy service demand peaks")
    else:
        print(f"✅ Service capacity constraints satisfied for all periods and weeks")

    m.update()
    print(f"\nFinal model size:")
    print(f"  Variables: {m.NumVars:,}")
    print(f"  Constraints: {m.NumConstrs:,}")

    # ============================================================
    # OBJECTIVE: MINIMIZE OPEX ONLY
    # ============================================================

    print("\n" + "="*70)
    print("OBJECTIVE FUNCTION: MINIMIZE OPEX ONLY")
    print("="*70)

    opex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] *
        gp.quicksum(
            p['c_H2']*q_disp[t,w,h] + p['c_elec']*q_comp[t,w,h] + p['c_trailer']*a_arr[t,w,h]
            for h in range(p['H'])
        )
        for t in range(1, T+1) for w in range(p['W'])
    )

    m.setObjective(opex, GRB.MINIMIZE)

    print(f"Objective: min OPEX")
    print(f"  OPEX = Σ β^(t-1) × ω_w × (c_H2×q_disp + c_elec×q_comp + c_trailer×a_arr)")
    print(f"  CAPEX: NOT in objective (sunk cost, fixed at {locked_capex/10000:.6f} 万元)")

    # ============================================================
    # SOLVE
    # ============================================================

    print("\n" + "="*70)
    print("SOLVING MODEL D")
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
        'experiment': 'fixed_investment_opex',
        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
        'model_b_reference': {
            'result_file': model_b_result_file,
            'capex': locked_capex,
            'capex_万元': locked_capex / 10000,
            'opex_raw': locked_opex_raw,
            'opex_raw_万元': locked_opex_raw / 10000,
            'investments': locked_investments,
            'capacity_trajectory': {str(t): {'C': C_fixed[t], 'S': S_fixed[t], 'K': K_fixed[t]}
                                   for t in range(1, T+1)}
        },
        'configuration': {
            'model_version': 'Model Freeze v1.0',
            'growth_rate': growth_rate,
            'LT': lt_value,
            's0': s0,
            'scenario': 'Central Case',
            'objective': 'min OPEX (fixed investment from Model B)',
            'data_file': data_file,
            'data_hash': actual_hash
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

        # Optimized OPEX (objective value)
        opex_optimized = m.ObjVal
        result['costs'] = {
            'opex_optimized': opex_optimized,
            'opex_optimized_万元': opex_optimized / 10000
        }

        # Compute OPEX breakdown
        opex_H2 = sum(
            (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] * sum(
                p['c_H2']*q_disp[t,w,h].X for h in range(p['H'])
            )
            for t in range(1, T+1) for w in range(p['W'])
        )

        opex_elec = sum(
            (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] * sum(
                p['c_elec']*q_comp[t,w,h].X for h in range(p['H'])
            )
            for t in range(1, T+1) for w in range(p['W'])
        )

        opex_trailer = sum(
            (1/(1+p['discount_rate'])**(t-1)) * p['omega'][w] * sum(
                p['c_trailer']*a_arr[t,w,h].X for h in range(p['H'])
            )
            for t in range(1, T+1) for w in range(p['W'])
        )

        result['costs']['opex_breakdown'] = {
            'hydrogen': opex_H2,
            'hydrogen_万元': opex_H2 / 10000,
            'electricity': opex_elec,
            'electricity_万元': opex_elec / 10000,
            'trailer': opex_trailer,
            'trailer_万元': opex_trailer / 10000
        }

        # Verify breakdown sums to total
        opex_total_check = opex_H2 + opex_elec + opex_trailer
        if abs(opex_total_check - opex_optimized) > 1e-2:
            print(f"  WARNING: OPEX breakdown mismatch ({opex_total_check:.2f} vs {opex_optimized:.2f})")

        # Total cost (CAPEX + optimized OPEX)
        total_cost = locked_capex + opex_optimized
        result['costs']['total_cost'] = total_cost
        result['costs']['total_cost_万元'] = total_cost / 10000

        # Dispatch improvement over Model B raw
        delta_opex_dispatch = locked_opex_raw - opex_optimized
        result['comparison'] = {
            'model_b_opex_raw': locked_opex_raw,
            'model_b_opex_raw_万元': locked_opex_raw / 10000,
            'model_d_opex_optimized': opex_optimized,
            'model_d_opex_optimized_万元': opex_optimized / 10000,
            'delta_opex_dispatch': delta_opex_dispatch,
            'delta_opex_dispatch_万元': delta_opex_dispatch / 10000,
            'delta_opex_dispatch_pct': (delta_opex_dispatch / locked_opex_raw * 100) if locked_opex_raw > 0 else 0
        }

        # Status string
        if m.Status == 2:
            result['solver']['status_str'] = 'OPTIMAL'
            print(f"\n✅ OPTIMAL solution found (proven minimum OPEX)")
        elif m.Status == 9:
            result['solver']['status_str'] = 'TIME_LIMIT'
            print(f"\n⏱ TIME_LIMIT reached with feasible incumbent")
            print(f"  Best bound: {m.ObjBound/10000:.6f} 万元")
            print(f"  True minimum OPEX is between {m.ObjBound/10000:.6f} and {opex_optimized/10000:.6f} 万元")
        else:
            result['solver']['status_str'] = f'Status={m.Status}_INCUMBENT'
            print(f"\n✅ Feasible solution found (Status={m.Status})")

        print(f"\nCosts:")
        print(f"  CAPEX (fixed): {locked_capex/10000:.6f} 万元")
        print(f"  OPEX (optimized): {opex_optimized/10000:.6f} 万元")
        print(f"  Total Cost: {total_cost/10000:.6f} 万元")
        print(f"  MIP Gap: {m.MIPGap*100:.4f}%")

        print(f"\nOPEX breakdown:")
        print(f"  Hydrogen purchase: {opex_H2/10000:.6f} 万元 ({opex_H2/opex_optimized*100:.2f}%)")
        print(f"  Compression electricity: {opex_elec/10000:.6f} 万元 ({opex_elec/opex_optimized*100:.2f}%)")
        print(f"  Trailer arrival: {opex_trailer/10000:.6f} 万元 ({opex_trailer/opex_optimized*100:.2f}%)")

        print(f"\nComparison with Model B raw dispatch:")
        print(f"  Model B OPEX (raw): {locked_opex_raw/10000:.6f} 万元")
        print(f"  Model D OPEX (optimized): {opex_optimized/10000:.6f} 万元")
        print(f"  Dispatch improvement: {delta_opex_dispatch/10000:.6f} 万元 ({delta_opex_dispatch/locked_opex_raw*100:.4f}%)")

        # Verification: OPEX_D ≤ OPEX_B_raw
        if opex_optimized > locked_opex_raw + 1e-3:
            print(f"\n❌ WARNING: Optimized OPEX ({opex_optimized:.2f}) > Model B raw OPEX ({locked_opex_raw:.2f})")
            print(f"   This violates optimization bound! Check model differences.")
            result['verification'] = {'opex_bound': 'VIOLATED'}
        else:
            print(f"\n✅ Verification: OPEX_D ≤ OPEX_B_raw (optimization bound satisfied)")
            result['verification'] = {'opex_bound': 'SATISFIED'}

    else:
        result['solver']['feasible'] = False

        if m.Status == 3:
            result['solver']['status_str'] = 'INFEASIBLE'
            print(f"\n❌ INFEASIBLE")
            print(f"   Fixed investment from Model B should be hourly-feasible!")
            print(f"   Check model differences or parameter changes.")

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
    print("FIXED-INVESTMENT OPEX MINIMIZATION CONTROL EXPERIMENT")
    print("="*70)
    print()
    print("Purpose: Re-optimize hourly dispatch under Model B's fixed investment")
    print("         to obtain minimum achievable OPEX for fair economic comparison")
    print()
    print("Design:")
    print("  - Investment path: FIXED from Model B (Integrated-CAPEX-only)")
    print("  - Hourly constraints: IDENTICAL to Integrated model")
    print("  - Objective: min OPEX (NOT CAPEX)")
    print()
    print("Comparison:")
    print("  - Model B raw: CAPEX-minimizing dispatch → OPEX 4246.08万元")
    print("  - Model D: Fixed investment, OPEX-optimized → OPEX [TO BE DETERMINED]")
    print()
    print("="*70)
    print()

    # Run experiment
    result = run_fixed_investment_opex()

    # Save results
    output_file = f"fixed_investment_opex_result_{result['timestamp']}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Results saved to: {output_file}")
    print(f"✅ Gurobi log saved to: fixed_investment_opex_gurobi.log")

    return result


if __name__ == '__main__':
    main()
