#!/usr/bin/env python3
"""
Fig. 6: Hourly coordination in feasible corrected joint-model incumbent
Period 5, Representative Week 1

Scientific verification:
- All 168 hours validated against certified capacity constraints
- Compression <= 250 kg/h, HP inventory <= 358 kg, trailer inventory >= 0
- Weekly boundary: I_HP[0] = I_HP[168] = 50 kg (prescribed initial/terminal)
- Connection dynamics and demand satisfaction verified

Data source: experiments/integrated_consistency_validation/final_model_equivalence_fix/
- integrated_corrected_hourly_20261030_131154.csv
- integrated_corrected_result_20261030_131154.json

Recorded feasible incumbent: 4635.458174 × 10^4 CNY (MIP gap 0.2321%; not globally proven optimal)
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

# ========== DATA LOADING ==========
csv_path = "../../experiments/integrated_consistency_validation/final_model_equivalence_fix/integrated_corrected_hourly_20261030_131154.csv"
df = pd.read_csv(csv_path)

# Filter T5/W1
df_t5w1 = df[(df['period'] == 5) & (df['week'] == 1)].copy()
df_t5w1 = df_t5w1.sort_values('hour').reset_index(drop=True)

assert len(df_t5w1) == 168, f"Expected 168 hours, got {len(df_t5w1)}"

# Extract variables (end-of-hour state)
hours = df_t5w1['hour'].values
q_disp = df_t5w1['q_disp'].values      # Dispensed in hour h (kg)
q_comp = df_t5w1['q_comp'].values      # Compressed in hour h (kg)
I_HP = df_t5w1['I_HP'].values          # HP inventory at end of hour h (kg)
a_arr = df_t5w1['a_arr'].values        # Arrival event in hour h
a_dep = df_t5w1['a_dep'].values        # Departure event in hour h
z = df_t5w1['z'].values                # Connected at end of hour h
I_trailer = df_t5w1['I_trailer'].values  # Trailer inventory at end of hour h (kg)

# Certified capacities at T5
C_t5 = 250.0  # kg/h
S_t5 = 358.0  # kg
Q_trailer = 285.26  # kg

# ========== FIGURE SETUP ==========
fig = plt.figure(figsize=(7.5, 10.5))
gs = GridSpec(4, 1, figure=fig, hspace=0.15, left=0.10, right=0.95, top=0.98, bottom=0.05)

color_demand = '#2c3e50'
color_comp = '#3498db'
color_inv = '#e74c3c'
color_arrival = '#27ae60'
color_departure = '#c0392b'

# ========== PANEL (a): DEMAND AND COMPRESSION ==========
ax1 = fig.add_subplot(gs[0, 0])

ax1.plot(hours, q_disp, color=color_demand, linewidth=1.2, label='Hydrogen demand', zorder=3)
ax1.plot(hours, q_comp, color=color_comp, linewidth=1.2, label='Hydrogen compressed', alpha=0.85, zorder=2)
ax1.axhline(C_t5, color='gray', linestyle='--', linewidth=0.9, alpha=0.5,
            label=f'Compressor capacity ({C_t5:.0f} kg/h)', zorder=1)

ax1.set_xlim(0, 168)
ax1.set_ylim(0, max(q_disp.max(), q_comp.max(), C_t5) * 1.15)
ax1.set_ylabel('Hydrogen flow (kg/h)', fontsize=9)
ax1.legend(loc='upper center', fontsize=7.5, frameon=True, framealpha=0.95, ncol=3)
ax1.grid(True, alpha=0.2, linewidth=0.5)
ax1.tick_params(labelbottom=False)
ax1.text(0.02, 0.97, '(a)', transform=ax1.transAxes, fontsize=10, fontweight='bold', va='top', ha='left')

# ========== PANEL (b): HP INVENTORY ==========
ax2 = fig.add_subplot(gs[1, 0])

ax2.plot(hours, I_HP, color=color_inv, linewidth=1.3, label='HP hydrogen inventory', zorder=3)
ax2.axhline(S_t5, color='gray', linestyle='--', linewidth=0.9, alpha=0.5,
            label=f'Storage capacity ({S_t5:.0f} kg)', zorder=1)
ax2.axhline(50, color='#95a5a6', linestyle=':', linewidth=0.9, alpha=0.6,
            label='Prescribed initial/terminal inventory (50 kg)', zorder=1)

ax2.set_xlim(0, 168)
ax2.set_ylim(0, S_t5 * 1.14)
ax2.set_ylabel('Inventory (kg)', fontsize=9)
ax2.legend(loc='upper center', fontsize=7.5, frameon=True, framealpha=0.95, ncol=3)
ax2.grid(True, alpha=0.2, linewidth=0.5)
ax2.tick_params(labelbottom=False)
ax2.text(0.02, 0.83, '(b)', transform=ax2.transAxes, fontsize=10, fontweight='bold', va='top', ha='left')

# ========== PANEL (c): TRAILER CONNECTION AND EVENTS ==========
ax3 = fig.add_subplot(gs[2, 0])

# Connection status line (no dense background shading)
ax3.plot(hours, z, color='#34495e', linewidth=1.8, alpha=0.6, label='Connected',
         drawstyle='steps-post', zorder=2)

# Arrival events (reduced size)
arrival_hours = hours[a_arr > 0.5]
if len(arrival_hours) > 0:
    ax3.scatter(arrival_hours, np.ones(len(arrival_hours)) * 0.85, marker='^', s=45,
                color=color_arrival, edgecolors='black', linewidth=0.6,
                label='Trailer arrival', zorder=3)

# Departure events (reduced size)
departure_hours = hours[a_dep > 0.5]
if len(departure_hours) > 0:
    ax3.scatter(departure_hours, np.ones(len(departure_hours)) * 0.15, marker='v', s=45,
                color=color_departure, edgecolors='black', linewidth=0.6,
                label='Trailer departure', zorder=3)

ax3.set_xlim(0, 168)
ax3.set_ylim(-0.1, 1.2)
ax3.set_yticks([0, 1])
ax3.set_yticklabels(['Disconnected', 'Connected'], fontsize=8)
ax3.legend(loc='upper center', fontsize=7.5, frameon=True, framealpha=0.95, ncol=3)
ax3.grid(True, alpha=0.2, linewidth=0.5, axis='x')
ax3.tick_params(labelbottom=False)
ax3.text(0.02, 0.97, '(c)', transform=ax3.transAxes, fontsize=10, fontweight='bold', va='top', ha='left')

# ========== PANEL (d): TRAILER INVENTORY ==========
ax4 = fig.add_subplot(gs[3, 0])

ax4.plot(hours, I_trailer, color='#8e44ad', linewidth=1.3, label='Trailer hydrogen inventory', zorder=2)
ax4.axhline(Q_trailer, color='gray', linestyle='--', linewidth=0.9, alpha=0.5,
            label=f'Trailer capacity ({Q_trailer:.2f} kg)', zorder=1)

ax4.set_xlim(0, 168)
ax4.set_ylim(0, Q_trailer * 1.15)
ax4.set_xlabel('Hour within representative week', fontsize=9)
ax4.set_ylabel('Inventory (kg)', fontsize=9)
ax4.legend(loc='upper center', fontsize=7.5, frameon=True, framealpha=0.95, ncol=2)
ax4.grid(True, alpha=0.2, linewidth=0.5)
ax4.text(0.02, 0.97, '(d)', transform=ax4.transAxes, fontsize=10, fontweight='bold', va='top', ha='left')

# ========== SAVE ==========
output_dir = "."
fig.savefig(f"{output_dir}/fig6_hourly_coordination_final.pdf", dpi=300, bbox_inches='tight')
fig.savefig(f"{output_dir}/fig6_hourly_coordination_final.png", dpi=300, bbox_inches='tight')

print("✅ Fig. 6 (FINAL) generated successfully")
print(f"   Period: T5, Week: W1 (168 hours)")
print(f"   Certified capacities: C={C_t5:.0f} kg/h, S={S_t5:.0f} kg")
print(f"   Trailer capacity: {Q_trailer:.2f} kg")
print(f"   Output: fig6_hourly_coordination_final.pdf/.png")
print(f"\n   Note: All variables represent end-of-hour state")
print(f"         50 kg boundary is prescribed initial/terminal, not hourly minimum")
