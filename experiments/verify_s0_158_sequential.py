"""
S_0=158 Sequential完整验证: Stage 1 + Stage 2
用于审计，避免仅凭外推断言
"""
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import time
import json
import sys
sys.path.insert(0, '../data/parameters')
from unified_params import get_params

def run_sequential_stage1(s0_value):
    """Stage 1: 聚合容量规划"""
    print(f"\n{'='*70}")
    print(f"Sequential Stage 1: S_0={s0_value} kg")
    print("="*70)

    params = get_params('central')
    df = pd.read_csv('../data/processed/representative_weeks_FixedEP_W10_FINAL.csv', encoding='utf-8-sig')
    df['hour'] = pd.to_datetime(df['hour'])

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
    m = gp.Model("SeqS1")
    m.setParam('OutputFlag', 0)
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 300)

    # 变量
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

    # 约束
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

    # 聚合容量约束
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

    # 目标
    capex = gp.quicksum(
        (1/(1+p['discount_rate'])**(t-1)) * (
            gp.quicksum(p['Delta_C_options'][c][1]*x_C[c,t] for c in range(len(p['Delta_C_options']))) +
            gp.quicksum(p['Delta_S_options'][s][1]*x_S[s,t] for s in range(len(p['Delta_S_options']))) +
            gp.quicksum(p['Delta_K_options'][k][1]*x_K[k,t] for k in range(len(p['Delta_K_options'])))
        )
        for t in range(1, T+1)
    )
    m.setObjective(capex, GRB.MINIMIZE)

    print(f"\n开始求解Stage 1...")
    t0 = time.time()
    m.optimize()
    t1 = time.time()

    result = {'s0': s0_value, 'stage': 1, 'solve_time': t1-t0}

    if m.Status == GRB.OPTIMAL:
        result['feasible'] = True
        result['capex'] = m.ObjVal / 10000

        # 提取投资方案
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
            print(f"    T={inv_t}: {eq_type}+{cap} ({cost:.0f}万)")

    else:
        result['feasible'] = False
        result['status'] = m.Status
        print(f"\n不可行 (Status={m.Status})")
        print(f"  时间: {t1-t0:.2f}秒")

    return result


def run_sequential_stage2(s0_value, fixed_investments):
    """Stage 2: 完整运营验证"""
    print(f"\n{'='*70}")
    print(f"Sequential Stage 2: S_0={s0_value} kg")
    print(f"固定投资方案: {len(fixed_investments)}项")
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

    # 计算各期容量
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

    print(f"\n容量轨迹:")
    for t in range(1, 6):
        print(f"  T={t}: C={C_fixed[t]} kg/h, S={S_fixed[t]} kg, K={K_fixed[t]} min/h")

    T, W, H = 5, len(weeks_data), 168
    m = gp.Model("SeqS2")
    m.setParam('OutputFlag', 0)
    m.setParam('MIPGap', 0.001)
    m.setParam('TimeLimit', 1800)

    # 运营变量
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

    # 运营约束
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

    print(f"\n开始求解Stage 2 (TimeLimit=1800s)...")
    t0 = time.time()
    m.optimize()
    t1 = time.time()

    result = {'s0': s0_value, 'stage': 2, 'solve_time': t1-t0}

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
            iis_constrs = [c.ConstrName for c in m.getConstrs() if c.IISConstr]
            result['iis_count'] = len(iis_constrs)
            print(f"  IIS约束数: {len(iis_constrs)}")

    return result


if __name__ == '__main__':
    s0 = 158

    print("="*70)
    print(f"S_0={s0} Sequential完整验证 (审计用)")
    print("="*70)

    # Stage 1
    s1_result = run_sequential_stage1(s0)

    if not s1_result['feasible']:
        print(f"\nStage 1不可行，终止")
        result = {'s0': s0, 'seq_stage1': s1_result}
    else:
        # Stage 2
        s2_result = run_sequential_stage2(s0, s1_result['investments'])
        result = {
            's0': s0,
            'seq_stage1': s1_result,
            'seq_stage2': s2_result
        }

    # 保存结果
    with open(f's0_158_sequential_audit.json', 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*70}")
    print("审计结果总结")
    print("="*70)
    print(f"S_0={s0} Sequential:")
    print(f"  Stage 1: {'可行' if s1_result['feasible'] else '不可行'}")
    if s1_result['feasible']:
        print(f"    CAPEX: {s1_result['capex']:.2f}万元")
        print(f"    投资数: {len(s1_result['investments'])}项")
        print(f"  Stage 2: {'可行' if s2_result['feasible'] else '不可行'}")
        if not s2_result['feasible']:
            print(f"    Status: {s2_result['status']}")
            if 'iis_count' in s2_result:
                print(f"    IIS约束数: {s2_result['iis_count']}")

    print(f"\n结果已保存到: s0_158_sequential_audit.json")
