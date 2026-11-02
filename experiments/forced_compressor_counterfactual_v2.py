"""
Forced Compressor Counterfactual v2.0

反事实实验：强制Sequential Stage1在T=1投资C+50，检验Stage2是否仍然INFEASIBLE

Model Version: Model Freeze v1.0
Test Configuration:
- S₀ = 158 kg
- Growth = 15%
- LT = 1
- Central Case
- Final representative weeks

Experiment:
1. Sequential Stage1 with constraint: x_C[0,1] = 1 (forced C+50 at T=1)
2. Record Stage1 results (investments, CAPEX, status)
3. Run Sequential Stage2 with fixed investment plan from Stage1
4. Record Stage2 results (status, runtime, IIS count, key conflicts)

Question: Does Stage2 remain INFEASIBLE after forced early C investment?
"""

import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import time
import json
import sys
sys.path.insert(0, '../data/parameters')
from unified_params import get_params

def run_forced_stage1(s0_value):
    """Sequential Stage1 with forced C+50 investment at T=1"""
    print(f"\n{'='*70}")
    print(f"Forced Compressor Stage 1: S0={s0_value} kg")
    print("Constraint: x_C[0,1] = 1 (forced C+50 at T=1)")
    print("="*70)

    params = get_params('central')
    df = pd.read_csv('../data/processed/representative_weeks_FixedEP_W10_FINAL.csv', encoding='utf-8-sig')
    df['hour'] = pd.to_datetime(df['hour'])

    # Aggregate representative week data
    weeks_data = {}
    for week_id in sorted(df['representative_week_id'].unique()):
        week_data = df[df['representative_week_id'] == week_id].sort_values('hour')
        demand = week_data['demand_kg'].values
        service = week_data['service_minutes'].values
        weeks_data[int(week_id)] = {
            'D_1h': demand.max(),
            'D_2h': max([demand[i:i+2].sum() for i in range(167)]),
            'D_4h': max([demand[i:i+4].sum() for i in range(165)]),
            'G_peak': service.max(),
            'weight': week_data['weight'].values[0]
        }

    p = params.copy()
    p.update({
        'T': 5,
        'W': len(weeks_data),
        'rho': [1.00, 1.15, 1.3225, 1.5209, 1.7490],
        'omega': [weeks_data[w+1]['weight'] for w in range(len(weeks_data))],
        'S_0': s0_value
    })

    T, W = p['T'], p['W']
    m = gp.Model("ForcedSeqS1")
    m.setParam('OutputFlag', 1)
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 300)

    # Variables
    x_C, x_S, x_K = {}, {}, {}
    y_C, y_S, y_K = {}, {}, {}
    C_total, S_total, K_total = {}, {}, {}

    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            x_C[c,t] = m.addVar(vtype=GRB.BINARY)
            y_C[c,t] = m.addVar(vtype=GRB.BINARY)
        for s in range(len(p['Delta_S_options'])):
            x_S[s,t] = m.addVar(vtype=GRB.BINARY)
            y_S[s,t] = m.addVar(vtype=GRB.BINARY)
        for k in range(len(p['Delta_K_options'])):
            x_K[k,t] = m.addVar(vtype=GRB.BINARY)
            y_K[k,t] = m.addVar(vtype=GRB.BINARY)
        C_total[t] = m.addVar(lb=0)
        S_total[t] = m.addVar(lb=0)
        K_total[t] = m.addVar(lb=0)

    m.update()

    # FORCED CONSTRAINT: Must invest C+50 at T=1
    m.addConstr(x_C[0,1] == 1, name='forced_C_at_T1')
    print(f"\n添加强制约束: x_C[0,1] = 1 (C+50 at T=1)")

    # Standard constraints
    for c in range(len(p['Delta_C_options'])):
        m.addConstr(gp.quicksum(x_C[c,t] for t in range(1, T+1)) <= 1)
    for s in range(len(p['Delta_S_options'])):
        m.addConstr(gp.quicksum(x_S[s,t] for t in range(1, T+1)) <= 1)
    for k in range(len(p['Delta_K_options'])):
        m.addConstr(gp.quicksum(x_K[k,t] for t in range(1, T+1)) <= 1)

    for t in range(1, T+1):
        for c in range(len(p['Delta_C_options'])):
            m.addConstr(y_C[c,t] == gp.quicksum(x_C[c,tau] for tau in range(1, max(0, t-p['LT_C'])+1)))
        for s in range(len(p['Delta_S_options'])):
            m.addConstr(y_S[s,t] == gp.quicksum(x_S[s,tau] for tau in range(1, max(0, t-p['LT_S'])+1)))
        for k in range(len(p['Delta_K_options'])):
            m.addConstr(y_K[k,t] == gp.quicksum(x_K[k,tau] for tau in range(1, max(0, t-p['LT_K'])+1)))

        m.addConstr(C_total[t] == p['C_0'] + gp.quicksum(p['Delta_C_options'][c][0]*y_C[c,t] for c in range(len(p['Delta_C_options']))))
        m.addConstr(S_total[t] == p['S_0'] + gp.quicksum(p['Delta_S_options'][s][0]*y_S[s,t] for s in range(len(p['Delta_S_options']))))
        m.addConstr(K_total[t] == p['K_srv_0'] + gp.quicksum(p['Delta_K_options'][k][0]*y_K[k,t] for k in range(len(p['Delta_K_options']))))

    # Aggregated capacity constraints
    for t in range(1, T+1):
        rho = p['rho'][t-1]
        B_avail = m.addVar(lb=0)
        m.addConstr(B_avail == S_total[t] - 50)

        for w in range(W):
            week = weeks_data[w+1]
            m.addConstr(K_total[t] >= rho * week['G_peak'])
            m.addConstr(rho * week['D_1h'] <= C_total[t] + B_avail)
            m.addConstr(rho * week['D_2h'] <= 2*C_total[t] + B_avail)
            m.addConstr(rho * week['D_4h'] <= 4*C_total[t] + B_avail)

    # Objective
    capex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            gp.quicksum(p['Delta_C_options'][c][1]*x_C[c,t] for c in range(len(p['Delta_C_options']))) +
            gp.quicksum(p['Delta_S_options'][s][1]*x_S[s,t] for s in range(len(p['Delta_S_options']))) +
            gp.quicksum(p['Delta_K_options'][k][1]*x_K[k,t] for k in range(len(p['Delta_K_options'])))
        )
        for t in range(1, T+1)
    )
    m.setObjective(capex, GRB.MINIMIZE)

    print(f"\n开始求解Forced Stage 1...")
    t0 = time.time()
    m.optimize()
    t1 = time.time()

    result = {'s0': s0_value, 'stage': 1, 'forced': True, 'solve_time': t1-t0}

    if m.Status == GRB.OPTIMAL or (m.Status == 9 and m.SolCount > 0):
        result['feasible'] = True
        result['capex'] = m.ObjVal / 10000

        # Extract investment plan
        investments = []
        for t in range(1, T+1):
            for c in range(len(p['Delta_C_options'])):
                if x_C[c,t].X > 0.5:
                    cap, cost = p['Delta_C_options'][c]
                    investments.append((t, 'C', cap, cost/10000))
            for s in range(len(p['Delta_S_options'])):
                if x_S[s,t].X > 0.5:
                    cap, cost = p['Delta_S_options'][s]
                    investments.append((t, 'S', cap, cost/10000))
            for k in range(len(p['Delta_K_options'])):
                if x_K[k,t].X > 0.5:
                    cap, cost = p['Delta_K_options'][k]
                    investments.append((t, 'K', cap, cost/10000))

        result['investments'] = investments

        print(f"\n可行")
        print(f"  CAPEX: {result['capex']:.2f}万元")
        print(f"  时间: {t1-t0:.2f}秒")
        print(f"\n投资方案:")
        for inv_t, eq_type, cap, cost in investments:
            marker = " (FORCED)" if inv_t == 1 and eq_type == 'C' else ""
            print(f"    T={inv_t}: {eq_type}+{cap} ({cost:.0f}万){marker}")

    else:
        result['feasible'] = False
        result['status'] = m.Status
        print(f"\n不可行 (Status={m.Status})")
        print(f"  时间: {t1-t0:.2f}秒")

    return result


def run_forced_stage2(s0_value, fixed_investments):
    """Sequential Stage2 with forced investment plan"""
    print(f"\n{'='*70}")
    print(f"Forced Compressor Stage 2: S0={s0_value} kg")
    print(f"固定投资方案: {len(fixed_investments)}项 (含强制C+50)")
    print("="*70)

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

    p = params.copy()
    p.update({
        'T': 5,
        'W': len(weeks_data),
        'rho': [1.00, 1.15, 1.3225, 1.5209, 1.7490],
        'omega': [weeks_data[w+1]['weight'] for w in range(len(weeks_data))],
        'S_0': s0_value
    })

    # Calculate capacities from forced investment plan
    C_fixed = {t: 100 for t in range(1, 6)}
    S_fixed = {t: s0_value for t in range(1, 6)}
    K_fixed = {t: 120 for t in range(1, 6)}

    for inv_t, eq_type, cap, _ in fixed_investments:
        op_t = inv_t + 1  # LT=1
        if eq_type == 'C':
            for t in range(op_t, 6):
                C_fixed[t] += cap
        elif eq_type == 'S':
            for t in range(op_t, 6):
                S_fixed[t] += cap
        elif eq_type == 'K':
            for t in range(op_t, 6):
                K_fixed[t] += cap

    print(f"\n容量轨迹 (含强制C+50):")
    for t in range(1, 6):
        print(f"  T={t}: C={C_fixed[t]} kg/h, S={S_fixed[t]} kg, K={K_fixed[t]} min/h")

    T, W, H = 5, len(weeks_data), 168
    m = gp.Model("ForcedSeqS2")
    m.setParam('OutputFlag', 1)
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 1800)

    # Operational variables
    a_arr, a_dep, z = {}, {}, {}
    I_trailer, Q_depart = {}, {}
    q_comp, I_HP, q_disp = {}, {}, {}

    for t in range(1, T+1):
        for w in range(W):
            for h in range(H):
                a_arr[t,w,h] = m.addVar(vtype=GRB.BINARY)
                a_dep[t,w,h] = m.addVar(vtype=GRB.BINARY)
                z[t,w,h] = m.addVar(vtype=GRB.BINARY)
                I_trailer[t,w,h] = m.addVar(lb=0)
                Q_depart[t,w,h] = m.addVar(lb=0)
                q_comp[t,w,h] = m.addVar(lb=0)
                I_HP[t,w,h] = m.addVar(lb=0)
                q_disp[t,w,h] = m.addVar(lb=0)

    m.update()

    # Operational constraints
    for t in range(1, T+1):
        rho = p['rho'][t-1]
        for w in range(W):
            demand = weeks_data[w+1]['demand']

            for h in range(H):
                if h == 0:
                    m.addConstr(z[t,w,h] == a_arr[t,w,h] - a_dep[t,w,h])
                    m.addConstr(I_trailer[t,w,h] == 285.26*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m.addConstr(I_HP[t,w,h] == 50 + q_comp[t,w,h] - q_disp[t,w,h])
                else:
                    m.addConstr(z[t,w,h] == z[t,w,h-1] + a_arr[t,w,h] - a_dep[t,w,h])
                    m.addConstr(I_trailer[t,w,h] == I_trailer[t,w,h-1] + 285.26*a_arr[t,w,h] - q_comp[t,w,h] - Q_depart[t,w,h])
                    m.addConstr(I_HP[t,w,h] == I_HP[t,w,h-1] + q_comp[t,w,h] - q_disp[t,w,h])

                m.addConstr(z[t,w,h] <= 1)
                m.addConstr(I_trailer[t,w,h] <= 1000 * z[t,w,h])
                m.addConstr(Q_depart[t,w,h] <= 1000 * a_dep[t,w,h])
                m.addConstr(q_comp[t,w,h] <= C_fixed[t])
                m.addConstr(q_comp[t,w,h] <= 1000 * z[t,w,h])
                m.addConstr(I_HP[t,w,h] <= S_fixed[t])
                m.addConstr(q_disp[t,w,h] == rho * demand[h])

                if h > 0:
                    m.addConstr(a_dep[t,w,h] <= z[t,w,h-1])
                    m.addConstr(a_arr[t,w,h] <= 1 - z[t,w,h-1])
                m.addConstr(a_arr[t,w,h] + a_dep[t,w,h] <= 1)

            m.addConstr(I_HP[t,w,H-1] == 50)
            m.addConstr(z[t,w,H-1] == 0)

    opex = sum(
        (1/1.08**(t-1)) * p['omega'][w] *
        sum(35*q_disp[t,w,h] + 5*q_comp[t,w,h] + 1000*a_arr[t,w,h] for h in range(H))
        for t in range(1, T+1) for w in range(W)
    )
    m.setObjective(opex, GRB.MINIMIZE)

    print(f"\n开始求解Forced Stage 2 (TimeLimit=1800s)...")
    t0 = time.time()
    m.optimize()
    t1 = time.time()

    result = {'s0': s0_value, 'stage': 2, 'forced': True, 'solve_time': t1-t0}

    if m.Status == 2 or (m.Status == 9 and m.SolCount > 0):
        result['feasible'] = True
        result['status'] = 'OPTIMAL' if m.Status == 2 else 'TIME_LIMIT'
        result['opex'] = m.ObjVal / 10000
        result['gap'] = m.MIPGap

        print(f"\n可行")
        print(f"  状态: {result['status']}")
        print(f"  OPEX: {result['opex']:.2f}万元")
        print(f"  Gap: {result['gap']*100:.4f}%")
        print(f"  时间: {t1-t0:.2f}秒")

    else:
        result['feasible'] = False
        result['status'] = m.Status

        print(f"\n不可行 (Status={m.Status})")
        print(f"  时间: {t1-t0:.2f}秒")

        if m.Status == 3:  # INFEASIBLE
            print("\n开始IIS诊断...")
            m.computeIIS()
            iis_constrs = [c for c in m.getConstrs() if c.IISConstr]
            result['iis_count'] = len(iis_constrs)
            print(f"  IIS约束数: {len(iis_constrs)}")

            # Categorize IIS constraints
            c_constraints = []
            s_constraints = []
            other_constraints = []

            for c in iis_constrs[:20]:  # Show first 20
                name = c.ConstrName
                if 'q_comp' in name and 'C_fixed' in str(c):
                    c_constraints.append(name)
                elif 'I_HP' in name and 'S_fixed' in str(c):
                    s_constraints.append(name)
                else:
                    other_constraints.append(name)

            result['iis_breakdown'] = {
                'compression': len(c_constraints),
                'storage': len(s_constraints),
                'other': len(other_constraints)
            }

            print(f"\n  IIS分类:")
            print(f"    压缩容量约束: {len(c_constraints)}")
            print(f"    储氢容量约束: {len(s_constraints)}")
            print(f"    其他约束: {len(other_constraints)}")

    return result


if __name__ == '__main__':
    s0 = 158

    print("="*70)
    print(f"Forced Compressor Counterfactual v2.0")
    print(f"Model Freeze v1.0 | S0={s0} kg | growth=15% | LT=1")
    print("="*70)

    # Forced Stage 1
    s1_result = run_forced_stage1(s0)

    if not s1_result['feasible']:
        print(f"\nForced Stage 1不可行（异常），终止")
        result = {'s0': s0, 'forced_stage1': s1_result}
    else:
        # Forced Stage 2
        s2_result = run_forced_stage2(s0, s1_result['investments'])
        result = {
            's0': s0,
            'model_version': 'Model Freeze v1.0',
            'forced_stage1': s1_result,
            'forced_stage2': s2_result
        }

    # Save results
    with open(f'forced_compressor_counterfactual_v2.json', 'w') as f:
        json.dump(result, f, indent=2)

    print("="*70)
    print("反事实实验结果总结")
    print("="*70)
    print(f"S0={s0} Forced Compressor:")
    print(f"  Forced Stage 1: {'可行' if s1_result['feasible'] else '不可行'}")
    if s1_result['feasible']:
        print(f"    CAPEX: {s1_result['capex']:.2f}万元")
        print(f"    投资数: {len(s1_result['investments'])}项 (含强制C+50 at T=1)")
        print(f"  Forced Stage 2: {'可行' if s2_result['feasible'] else '不可行'}")
        if not s2_result['feasible']:
            print(f"    Status: {s2_result['status']}")
            if 'iis_count' in s2_result:
                print(f"    IIS约束数: {s2_result['iis_count']}")
                if 'iis_breakdown' in s2_result:
                    breakdown = s2_result['iis_breakdown']
                    print(f"    IIS分类: C={breakdown['compression']}, S={breakdown['storage']}, 其他={breakdown['other']}")

    print(f"\n核心问题回答:")
    if s1_result['feasible'] and not s2_result['feasible']:
        print(f"  [YES] 强制提前C+50后，Stage2仍然INFEASIBLE")
        print(f"  [YES] 证明：单一投资调整不足以修复Sequential的结构性缺陷")
    elif s1_result['feasible'] and s2_result['feasible']:
        print(f"  [WARNING] 强制提前C+50后，Stage2变为FEASIBLE")
        print(f"  [WARNING] 说明：提前C投资可能足以修复（需进一步分析）")

    print(f"\n结果已保存到: forced_compressor_counterfactual_v2.json")
