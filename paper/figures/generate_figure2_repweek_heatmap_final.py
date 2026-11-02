"""
Figure 2: Representative Week Demand Heatmap - FINAL VERSION
============================================================

Publication-ready visualization with NO Unicode markers, NO internal title,
NO legend box. Clean layout for Overleaf LaTeX integration.

Data source: data/processed/representative_weeks_FixedEP_W10_FINAL.csv
Output formats: PDF, SVG, PNG

Requirements:
- 10 representative weeks × 168 hours
- Y-axis: W1 (1) to W10 (10) format, weights in parentheses
- X-axis: Hour within representative week (0-167)
- Colorbar: Hydrogen demand (kg/h), actual data range
- Critical weeks W1-W5 distinguished by subtle left color bar
- NO special Unicode characters (★, ○)
- NO internal title (handled by LaTeX \caption)
- NO legend box

Author: Generated for HRS Dispatch Paper - SETA Submission
Date: 2026-10-26
Version: FINAL
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pathlib import Path

# Publication settings - SETA journal standards
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

# File paths
DATA_DIR = Path(__file__).parent.parent.parent / 'data' / 'processed'
OUTPUT_DIR = Path(__file__).parent
DATA_FILE = DATA_DIR / 'representative_weeks_FixedEP_W10_FINAL.csv'

print("="*70)
print("Figure 2: Representative Week Demand Heatmap - FINAL VERSION")
print("="*70)

# Load data
print(f"\n[1/6] Loading data from: {DATA_FILE}")
df = pd.read_csv(DATA_FILE)
print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")

# Data verification
print("\n[2/6] Verifying data integrity...")
unique_weeks = sorted(df['representative_week_id'].unique())
total_weight = df.groupby('representative_week_id')['weight'].first().sum()
demand_min = df['demand_kg'].min()
demand_max = df['demand_kg'].max()
missing_vals = df['demand_kg'].isna().sum()

print(f"   Representative weeks: {len(unique_weeks)} (expected 10)")
print(f"   Total weight sum: {total_weight:.1f} (expected 52)")
print(f"   Demand range: [{demand_min:.2f}, {demand_max:.2f}] kg/h")
print(f"   Missing values: {missing_vals} (expected 0)")
print(f"   Total data records: {len(df)} (expected 1680 + 1 header = 1681)")

assert len(unique_weeks) == 10, "ERROR: Expected 10 representative weeks"
assert abs(total_weight - 52) < 0.01, "ERROR: Total weight should be 52"
assert missing_vals == 0, "ERROR: No missing demand values allowed"
assert len(df) == 1680, "ERROR: Expected 1680 hourly records (10 weeks × 168 hours)"

print("   ✓ Data integrity verified")

# Reshape data to 10 weeks × 168 hours matrix
print("\n[3/6] Reshaping data into heatmap matrix...")
heatmap_data = []
week_metadata = []

for week_id in unique_weeks:
    week_df = df[df['representative_week_id'] == week_id].sort_values('hour')
    demand_series = week_df['demand_kg'].values
    weight = week_df['weight'].iloc[0]
    is_critical = week_df['is_critical'].iloc[0]

    assert len(demand_series) == 168, f"ERROR: Week {week_id} has {len(demand_series)} hours, expected 168"

    heatmap_data.append(demand_series)
    week_metadata.append({
        'week_id': week_id,
        'weight': int(weight),
        'is_critical': is_critical
    })

    status = "critical" if is_critical else "non-critical"
    print(f"   W{week_id}: {len(demand_series)} hours, weight={int(weight)}, {status}")

heatmap_matrix = np.array(heatmap_data)
print(f"   Final matrix shape: {heatmap_matrix.shape} (expected: (10, 168))")

# Print critical week identification
critical_weeks = [info['week_id'] for info in week_metadata if info['is_critical']]
noncritical_weeks = [info['week_id'] for info in week_metadata if not info['is_critical']]
print(f"   Critical weeks (W1-W5): {critical_weeks}")
print(f"   Non-critical weeks (W6-W10): {noncritical_weeks}")

# Create figure - FINAL LAYOUT
print("\n[4/6] Generating publication-ready heatmap...")
fig, ax = plt.subplots(figsize=(10, 5))

# Plot heatmap with actual data range - unified blue colormap (matching Fig 4)
im = ax.imshow(heatmap_matrix, cmap='Blues', aspect='auto',
               interpolation='nearest', vmin=0, vmax=demand_max)

# X-axis: Hour within representative week
hour_ticks = [0, 24, 48, 72, 96, 120, 144, 167]
ax.set_xticks(hour_ticks)
ax.set_xticklabels(hour_ticks)
ax.set_xlabel('Hour within representative week', fontsize=11, fontweight='bold')

# Y-axis: W1 (1) to W10 (10) format - NO Unicode characters
y_labels = []
for info in week_metadata:
    week_id = info['week_id']
    weight = info['weight']
    y_labels.append(f"W{week_id} ({weight})")

ax.set_yticks(range(len(unique_weeks)))
ax.set_yticklabels(y_labels)
ax.set_ylabel('Representative week', fontsize=11, fontweight='bold')

# Add minimal left color bar to distinguish critical weeks (W1-W5)
# Very thin bar at the left edge of the heatmap
for idx, info in enumerate(week_metadata):
    if info['is_critical']:
        # Critical weeks: dark blue thin bar
        rect = Rectangle((-0.8, idx-0.45), 0.6, 0.9,
                        facecolor='#2E5F9E', edgecolor='none',
                        clip_on=False)
        ax.add_patch(rect)
    else:
        # Non-critical weeks: light gray thin bar
        rect = Rectangle((-0.8, idx-0.45), 0.6, 0.9,
                        facecolor='#C0C0C0', edgecolor='none',
                        clip_on=False)
        ax.add_patch(rect)

# Add horizontal grid lines to separate weeks
for i in range(len(unique_weeks)-1):
    ax.axhline(i+0.5, color='gray', linewidth=0.6, linestyle='-', alpha=0.4)

# Add vertical lines for day boundaries (every 24 hours)
for day in [24, 48, 72, 96, 120, 144]:
    ax.axvline(day-0.5, color='white', linewidth=0.4, linestyle='--', alpha=0.4)

# Colorbar: Hydrogen demand (kg/h) - horizontal, bottom
cbar = plt.colorbar(im, ax=ax, orientation='horizontal',
                    pad=0.12, aspect=35, shrink=0.8)
cbar.set_label('Hydrogen demand (kg/h)', fontsize=10, fontweight='bold')

# NO internal title (LaTeX \caption will provide it)
# NO legend box (critical week distinction via left color bar)

# Adjust layout
plt.tight_layout()

# Save in multiple formats
print("\n[5/6] Saving figure in multiple formats...")
output_files = {
    'pdf': OUTPUT_DIR / 'figure2_repweek_heatmap_final.pdf',
    'svg': OUTPUT_DIR / 'figure2_repweek_heatmap_final.svg',
    'png': OUTPUT_DIR / 'figure2_repweek_heatmap_final.png'
}

for fmt, filepath in output_files.items():
    plt.savefig(filepath, format=fmt, bbox_inches='tight', dpi=300)
    file_size = filepath.stat().st_size / 1024  # KB
    print(f"   ✓ Saved: {filepath.name} ({file_size:.1f} KB)")

plt.close()

# Final verification report
print("\n[6/6] Data verification summary:")
print("="*70)
print("DATA INTEGRITY CHECK:")
print(f"  ✓ Total records processed: {len(df)} (1680 hourly records)")
print(f"  ✓ Representative weeks: {len(unique_weeks)} (W1-W10)")
print(f"  ✓ Hours per week: {heatmap_matrix.shape[1]} (168)")
print(f"  ✓ Total weight: {total_weight:.1f} weeks (should be 52)")
print(f"  ✓ Demand range: [{demand_min:.4f}, {demand_max:.4f}] kg/h")
print(f"  ✓ Peak demand: {demand_max:.4f} kg/h (W{df.loc[df['demand_kg'].idxmax(), 'representative_week_id']:.0f})")
print(f"  ✓ Missing values: {missing_vals}")
print(f"  ✓ Critical weeks: W1-W5 ({len(critical_weeks)} weeks)")
print(f"  ✓ Non-critical weeks: W6-W10 ({len(noncritical_weeks)} weeks)")
print()
print("WEEK WEIGHT BREAKDOWN:")
for info in week_metadata:
    status = "critical    " if info['is_critical'] else "non-critical"
    print(f"  W{info['week_id']:<2d} ({status}): weight = {info['weight']:>2d} weeks")
print(f"  Total: {sum(info['weight'] for info in week_metadata)} weeks")
print()
print("VISUALIZATION FEATURES:")
print("  ✓ Y-axis format: W1 (1) to W10 (10), weights in parentheses")
print("  ✓ X-axis: Hour within representative week (0-167)")
print("  ✓ Colorbar: Horizontal, bottom, actual data range")
print("  ✓ Critical week distinction: Left color bar (dark blue)")
print("  ✓ NO Unicode characters (NO ★ or ○)")
print("  ✓ NO internal title (LaTeX \\caption handles it)")
print("  ✓ NO legend box (left color bar is self-explanatory)")
print()
print("OUTPUT FILES:")
for fmt, filepath in output_files.items():
    print(f"  - {filepath.name} ({fmt.upper()} format)")
print()
print("LATEX CAPTION (suggested):")
print("  Hourly hydrogen demand profiles for the ten selected representative")
print("  weeks. Numbers in parentheses indicate annual week weights; W1-W5")
print("  denote critical weeks. The profiles correspond to the base demand")
print("  dataset before future-demand growth adjustments.")
print("="*70)
print("\n✓ Figure 2 FINAL VERSION generation complete!")
print("  All data verified, no fabrication, ready for SETA submission.")
print("="*70)
