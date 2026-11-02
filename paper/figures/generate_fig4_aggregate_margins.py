"""
Figure 4: Aggregate Capacity Margins - Sequential Investment Plan
==================================================================

Publication-ready visualization showing that the Sequential investment plan
satisfies all aggregated capacity constraints, despite failing hourly
operational feasibility test.

Data source: results/current/core_evidence_v2/raw/aggregate_feasibility_margins_v2.csv
Scenario: Sequential_Baseline ONLY (50 records, T1-T5 × W1-W10)

Three-panel layout:
(a) Hydrogen-capacity margin heatmaps (1h, 2h, 4h)
(b) Annual minimum hydrogen margins (kg)
(c) Annual minimum service margin (min/h)

Author: Generated for HRS Dispatch Paper - SETA Submission
Date: 2026-10-26
Version: FINAL
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from pathlib import Path

# SETA journal publication standards
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

# File paths
DATA_DIR = Path(__file__).parent.parent.parent / 'results' / 'current' / 'core_evidence_v2' / 'raw'
OUTPUT_DIR = Path(__file__).parent
DATA_FILE = DATA_DIR / 'aggregate_feasibility_margins_v2.csv'

print("="*70)
print("Figure 4: Aggregate Capacity Margins - Sequential Investment Plan")
print("="*70)

# Load and filter data
print(f"\n[1/6] Loading aggregate margin data...")
df = pd.read_csv(DATA_FILE)
print(f"   Total records: {len(df)}")
print(f"   Scenarios: {df['scenario'].unique().tolist()}")

# Filter Sequential_Baseline ONLY
seq_data = df[df['scenario'] == 'Sequential_Baseline'].copy()
print(f"\n[2/6] Filtered Sequential_Baseline: {len(seq_data)} records")

assert len(seq_data) == 50, f"ERROR: Expected 50 records (5 periods × 10 weeks), got {len(seq_data)}"

# Data integrity checks
print(f"\n[3/6] Data integrity verification...")
periods = sorted(seq_data['t'].unique())
weeks = sorted(seq_data['week'].unique())
print(f"   Planning periods: {periods}")
print(f"   Representative weeks: {weeks}")

assert periods == [1,2,3,4,5], "ERROR: Periods should be 1-5"
assert weeks == list(range(1,11)), "ERROR: Weeks should be 1-10"

# Check for negative margins (all should be non-negative)
negative_1h = (seq_data['slack_1h'] < 0).sum()
negative_2h = (seq_data['slack_2h'] < 0).sum()
negative_4h = (seq_data['slack_4h'] < 0).sum()
negative_K = (seq_data['slack_K'] < 0).sum()

print(f"   Negative margins found:")
print(f"      1-hour: {negative_1h} (should be 0)")
print(f"      2-hour: {negative_2h} (should be 0)")
print(f"      4-hour: {negative_4h} (should be 0)")
print(f"      Service: {negative_K} (should be 0)")

assert negative_1h == 0, "ERROR: All 1h margins should be non-negative"
assert negative_2h == 0, "ERROR: All 2h margins should be non-negative"
assert negative_4h == 0, "ERROR: All 4h margins should be non-negative"
assert negative_K == 0, "ERROR: All service margins should be non-negative"

print("   ✓ All margins are non-negative (constraints satisfied)")

# Find global minimum margins
print(f"\n[4/6] Computing global and annual minimum margins...")
min_1h_global = seq_data['slack_1h'].min()
min_2h_global = seq_data['slack_2h'].min()
min_4h_global = seq_data['slack_4h'].min()
min_K_global = seq_data['slack_K'].min()

min_1h_loc = seq_data.loc[seq_data['slack_1h'].idxmin()]
min_2h_loc = seq_data.loc[seq_data['slack_2h'].idxmin()]
min_4h_loc = seq_data.loc[seq_data['slack_4h'].idxmin()]
min_K_loc = seq_data.loc[seq_data['slack_K'].idxmin()]

print(f"   Global minimum margins:")
print(f"      1-hour: {min_1h_global:.4f} kg at T{int(min_1h_loc['t'])}/W{int(min_1h_loc['week'])}")
print(f"      2-hour: {min_2h_global:.4f} kg at T{int(min_2h_loc['t'])}/W{int(min_2h_loc['week'])}")
print(f"      4-hour: {min_4h_global:.4f} kg at T{int(min_4h_loc['t'])}/W{int(min_4h_loc['week'])}")
print(f"      Service: {min_K_global:.4f} min/h at T{int(min_K_loc['t'])}/W{int(min_K_loc['week'])}")

# Compute annual minimums
annual_mins = seq_data.groupby('t').agg({
    'slack_1h': 'min',
    'slack_2h': 'min',
    'slack_4h': 'min',
    'slack_K': 'min'
}).reset_index()

print(f"\n   Annual minimum margins:")
print(f"   {'Period':<8} {'1h (kg)':<12} {'2h (kg)':<12} {'4h (kg)':<12} {'Service (min/h)':<18}")
print("   " + "-"*62)
for _, row in annual_mins.iterrows():
    print(f"   T{int(row['t']):<7} {row['slack_1h']:<12.4f} {row['slack_2h']:<12.4f} {row['slack_4h']:<12.4f} {row['slack_K']:<18.4f}")

# Reshape data for heatmaps
print(f"\n[5/6] Reshaping data for heatmaps...")
margin_1h = seq_data.pivot(index='week', columns='t', values='slack_1h').values
margin_2h = seq_data.pivot(index='week', columns='t', values='slack_2h').values
margin_4h = seq_data.pivot(index='week', columns='t', values='slack_4h').values

print(f"   Heatmap shapes: {margin_1h.shape} (expected: (10, 5))")

# Create figure with compact two-row layout
print(f"\n[6/6] Generating two-row layout figure...")
fig = plt.figure(figsize=(12, 7.5))
gs = GridSpec(2, 3, figure=fig, height_ratios=[1, 0.85],
              hspace=0.28, wspace=0.35, left=0.08, right=0.95, top=0.95, bottom=0.08)

# Color scheme - sequential blue (positive margins)
cmap = plt.cm.Blues
vmin_h2 = 0
vmax_h2 = max(margin_1h.max(), margin_2h.max(), margin_4h.max())

# Row 1: Panel (a) - Three heatmaps for hydrogen margins
ax_1h = fig.add_subplot(gs[0, 0])
ax_2h = fig.add_subplot(gs[0, 1])
ax_4h = fig.add_subplot(gs[0, 2])

# 1-hour margin heatmap
im1 = ax_1h.imshow(margin_1h, cmap=cmap, aspect='auto', vmin=vmin_h2, vmax=vmax_h2)
ax_1h.set_xticks(range(5))
ax_1h.set_xticklabels([f'T{t}' for t in range(1,6)])
ax_1h.set_yticks(range(10))
ax_1h.set_yticklabels([f'W{w}' for w in range(1,11)])
ax_1h.set_title('1-hour margin', fontweight='bold', fontsize=10)
ax_1h.set_ylabel('Representative week', fontweight='bold')
ax_1h.text(0.02, 0.98, '(a)', transform=ax_1h.transAxes,
           fontsize=12, fontweight='bold', va='top', ha='left',
           bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='none'))

# 2-hour margin heatmap
im2 = ax_2h.imshow(margin_2h, cmap=cmap, aspect='auto', vmin=vmin_h2, vmax=vmax_h2)
ax_2h.set_xticks(range(5))
ax_2h.set_xticklabels([f'T{t}' for t in range(1,6)])
ax_2h.set_yticks(range(10))
ax_2h.set_yticklabels([])
ax_2h.set_title('2-hour margin', fontweight='bold', fontsize=10)

# 4-hour margin heatmap
im3 = ax_4h.imshow(margin_4h, cmap=cmap, aspect='auto', vmin=vmin_h2, vmax=vmax_h2)
ax_4h.set_xticks(range(5))
ax_4h.set_xticklabels([f'T{t}' for t in range(1,6)])
ax_4h.set_yticks(range(10))
ax_4h.set_yticklabels([])
ax_4h.set_title('4-hour margin', fontweight='bold', fontsize=10)

# Shared colorbar for hydrogen margins (positioned to the right)
cbar_ax = fig.add_axes([0.96, 0.58, 0.015, 0.30])
cbar = fig.colorbar(im3, cax=cbar_ax)
cbar.set_label('Aggregated margin (kg)', fontweight='bold', fontsize=9)

# Row 2: Panel (b) and (c) side by side
ax_h2_min = fig.add_subplot(gs[1, :2])  # Spans first two columns
ax_K_min = fig.add_subplot(gs[1, 2])     # Third column

# Panel (b): Annual minimum hydrogen margins
periods_list = annual_mins['t'].values
ax_h2_min.plot(periods_list, annual_mins['slack_1h'], marker='o', linewidth=2.5,
               markersize=7, markerfacecolor='white', markeredgecolor='#2E5F9E',
               markeredgewidth=2, label='1-hour', color='#2E5F9E')
ax_h2_min.plot(periods_list, annual_mins['slack_2h'], marker='s', linewidth=2.5,
               markersize=7, markerfacecolor='white', markeredgecolor='#4A7BA7',
               markeredgewidth=2, label='2-hour', color='#4A7BA7')
ax_h2_min.plot(periods_list, annual_mins['slack_4h'], marker='^', linewidth=2.5,
               markersize=7, markerfacecolor='white', markeredgecolor='#6B9AC4',
               markeredgewidth=2, label='4-hour', color='#6B9AC4')
ax_h2_min.set_xlabel('Planning period', fontweight='bold')
ax_h2_min.set_ylabel('Minimum hydrogen margin (kg)', fontweight='bold')
ax_h2_min.set_xticks([1,2,3,4,5])
ax_h2_min.set_xticklabels([f'T{t}' for t in range(1,6)])
ax_h2_min.grid(True, alpha=0.25, linestyle=':', linewidth=0.6)
ax_h2_min.legend(loc='upper center', bbox_to_anchor=(0.35, 0.98), framealpha=0.95, fontsize=9, ncol=3)
ax_h2_min.text(0.02, 0.98, '(b)', transform=ax_h2_min.transAxes,
               fontsize=12, fontweight='bold', va='top', ha='left',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', linewidth=0.8))

# Panel (c): Annual minimum service margin (dark gray, consistent with Fig 3)
ax_K_min.plot(periods_list, annual_mins['slack_K'], marker='d', linewidth=2.5,
              markersize=7, markerfacecolor='white', markeredgecolor='#4A4A4A',
              markeredgewidth=2, color='#4A4A4A')
ax_K_min.set_xlabel('Planning period', fontweight='bold')
ax_K_min.set_ylabel('Minimum service\nmargin (min/h)', fontweight='bold')
ax_K_min.set_xticks([1,2,3,4,5])
ax_K_min.set_xticklabels([f'T{t}' for t in range(1,6)])
ax_K_min.grid(True, alpha=0.25, linestyle=':', linewidth=0.6)
ax_K_min.text(0.02, 0.98, '(c)', transform=ax_K_min.transAxes,
              fontsize=12, fontweight='bold', va='top', ha='left',
              bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='none'))

# Save figure
print(f"\nSaving publication-ready figure...")
output_files = {
    'pdf': OUTPUT_DIR / 'fig4_aggregate_capacity_margins.pdf',
    'svg': OUTPUT_DIR / 'fig4_aggregate_capacity_margins.svg',
    'png': OUTPUT_DIR / 'fig4_aggregate_capacity_margins.png'
}

for fmt, filepath in output_files.items():
    plt.savefig(filepath, format=fmt, bbox_inches='tight', dpi=300)
    file_size = filepath.stat().st_size / 1024
    print(f"   ✓ Saved: {filepath.name} ({file_size:.1f} KB)")

plt.close()

print("\n" + "="*70)
print("FIGURE 4 GENERATION COMPLETE")
print("="*70)
