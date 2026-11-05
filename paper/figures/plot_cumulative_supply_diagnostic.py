#!/usr/bin/env python3
"""
Diagnostic: cumulative demand vs. optimistic cumulative hydrogen-supply upper bound,
first 12 hours of representative week 2, period t=5 (rho = 1.7490).

Data: data/processed/representative_weeks_FixedEP_W10_FINAL.csv (representative_week_id == 2)
Demand coefficient rho_5 = 1.7490, as used in experiments/verify_s0_158_sequential.py.

D(0) = 0,  D(n) = 1.7490 * sum_{h=0}^{n-1} d_{2,h}
U(n) = 50 + 100 n   (initial 50 kg + 100 kg/h compression, ignoring trailer connection
                     and other operating constraints; an optimistic bound, not a schedule)

Full numerical precision is kept; only display labels are rounded.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Arial'
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['font.size'] = 9
plt.rcParams['axes.linewidth'] = 0.8

# ========== DATA ==========
BASE = 'D:/0 crucial personal files/Hydrogen Refueling Station Dispatch/'
CSV = BASE + 'data/processed/representative_weeks_FixedEP_W10_FINAL.csv'
RHO_T5 = 1.7490
WEEK_ID = 2
N_HOURS = 12

df = pd.read_csv(CSV, encoding='utf-8-sig')
df['hour'] = pd.to_datetime(df['hour'])
week = df[df['representative_week_id'] == WEEK_ID].sort_values('hour')
assert len(week) == 168, f"Expected 168 hours, got {len(week)}"

d = week['demand_kg'].values[:N_HOURS]
n = np.arange(N_HOURS + 1)
D = np.concatenate([[0.0], RHO_T5 * np.cumsum(d)])
U = 50.0 + 100.0 * n
gap = D - U


# Reported shortfalls must match the data
assert f"{gap[1]:.2f}" == "12.60", gap[1]
assert f"{gap[3]:.2f}" == "84.37", gap[3]
# Largest shortfall within the displayed 12 hours (not the whole-week maximum)
n_peak = int(np.argmax(gap))
assert n_peak == 7 and f"{gap[7]:.2f}" == "137.35", (n_peak, gap[7])

# ========== STYLE (consistent with Figs. 3-5) ==========
color_demand = '#2E5F9E'
color_supply = '#555555'
color_gap = '#c0392b'

fig, ax = plt.subplots(figsize=(7.5, 4.0))
fig.subplots_adjust(left=0.10, right=0.96, top=0.96, bottom=0.14)

# Lines are visual guides only; the data are the integer-hour points.
ax.plot(n, D, color=color_demand, linewidth=1.2, alpha=0.5, zorder=2)
ax.plot(n, D, color=color_demand, linestyle='none', marker='o', markersize=3.8,
        markeredgecolor=color_demand, markeredgewidth=0.4, zorder=3,
        label=r'Cumulative demand $D(n)$')
ax.plot(n, U, color=color_supply, linewidth=1.2, linestyle='--', alpha=0.5, zorder=2)
ax.plot(n, U, color=color_supply, linestyle='none', marker='s', markersize=3.8,
        markeredgecolor=color_supply, markeredgewidth=0.4, zorder=3,
        label=r'Optimistic supply upper bound $U(n)=50+100n$')

# ========== SHORTFALL LABELS ==========
# Short leaders; label positions chosen in empty areas near each gap.
labels = {1: (1.25, 20), 3: (3.25, 215), 7: (7.25, 500)}
for k, (lx, ly) in labels.items():
    ax.plot([k, k], [U[k], D[k]], color=color_gap, linewidth=1.8,
            solid_capstyle='butt', zorder=4)
    ax.annotate(f'{gap[k]:.2f} kg at $n={k}$',
                xy=(k, (D[k] + U[k]) / 2), xytext=(lx, ly),
                color=color_gap, fontsize=8, ha='left', va='center',
                arrowprops=dict(arrowstyle='-', color=color_gap, linewidth=0.6,
                                shrinkA=2, shrinkB=1), zorder=5)

ax.set_xlim(-0.4, N_HOURS + 0.4)
ax.set_ylim(-20, max(D.max(), U.max()) * 1.05)
ax.set_xticks(n)
ax.set_xlabel('Hours elapsed since start of representative week, $n$', fontsize=9)
ax.set_ylabel('Cumulative hydrogen (kg)', fontsize=9)
ax.grid(True, axis='y', alpha=0.2, linewidth=0.5)
ax.legend(loc='upper left', fontsize=8, frameon=True, framealpha=0.95)

# ========== SAVE ==========
out = BASE + 'paper/figures/fig_cumulative_supply_diagnostic'
fig.savefig(out + '.pdf', facecolor='white')
fig.savefig(out + '.png', dpi=600, facecolor='white')
plt.close(fig)

print(f"Saved: {out}.pdf / .png")
for k in (1, 3, 7):
    print(f"n={k}: D={D[k]!r}, U={U[k]}, shortfall={gap[k]!r}")
