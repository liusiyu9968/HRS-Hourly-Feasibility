"""
Scenario parameter assumptions for the case study
================================================
The common parameter set contains fixed economic scenarios, not independently
validated procurement quotations. The original S_0=250 default is historical;
the paper reference scripts override initial storage to S_0=158.
"""

# Central Case参数（推荐基准）
PARAMS_CENTRAL = {
    # 压缩机扩容
    'Delta_C_options': [
        (50, 1400000),   # 50 kg/h, 140万元
        (100, 2000000)   # 100 kg/h, 200万元
    ],

    # 储罐扩容
    'Delta_S_options': [
        (100, 700000),   # 100 kg, 70万元 (7000元/kg)
        (200, 1400000)   # 200 kg, 140万元 (7000元/kg)
    ],

    # 服务设备扩容
    'Delta_K_options': [
        (60, 1200000),   # +1台加氢机, 120万元
        (120, 2100000)   # +2台加氢机, 210万元
    ],

    # 其他参数保持不变
    'C_0': 100,
    'S_0': 250,  # Baseline storage
    'K_srv_0': 120,
    'Q_trailer': 285.26,
    'I_HP_0': 50,
    'c_H2': 35,
    'c_elec': 5,
    'c_trailer': 1000,
    'discount_rate': 0.08,
    'LT_C': 1,
    'LT_S': 1,
    'LT_K': 1,
    'M': 1000
}

# Old参数（对比用）
PARAMS_OLD = {
    'Delta_C_options': [(50, 500000), (100, 800000)],
    'Delta_S_options': [(100, 300000), (200, 500000)],
    'Delta_K_options': [(60, 1200000), (120, 2000000)],
    'C_0': 100, 'S_0': 250, 'K_srv_0': 120,
    'Q_trailer': 285.26, 'I_HP_0': 50,
    'c_H2': 35, 'c_elec': 5, 'c_trailer': 1000,
    'discount_rate': 0.08,
    'LT_C': 1, 'LT_S': 1, 'LT_K': 1,
    'M': 1000
}

# Optimistic Case（敏感性测试用）
PARAMS_OPTIMISTIC = {
    'Delta_C_options': [(50, 1400000), (100, 2000000)],
    'Delta_S_options': [(100, 250000), (200, 500000)],  # 低价储罐
    'Delta_K_options': [(60, 1200000), (120, 2100000)],
    'C_0': 100, 'S_0': 250, 'K_srv_0': 120,
    'Q_trailer': 285.26, 'I_HP_0': 50,
    'c_H2': 35, 'c_elec': 5, 'c_trailer': 1000,
    'discount_rate': 0.08,
    'LT_C': 1, 'LT_S': 1, 'LT_K': 1,
    'M': 1000
}

def get_params(case='central'):
    """获取参数集"""
    if case == 'central':
        return PARAMS_CENTRAL.copy()
    elif case == 'old':
        return PARAMS_OLD.copy()
    elif case == 'optimistic':
        return PARAMS_OPTIMISTIC.copy()
    else:
        raise ValueError(f"Unknown case: {case}")
