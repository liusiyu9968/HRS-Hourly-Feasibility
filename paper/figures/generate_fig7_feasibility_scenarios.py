"""
Figure 7: Feasibility Outcomes Across Demand-Growth and Lead-Time Scenarios
============================================================================

Publication-ready visualization comparing Sequential and Integrated formulation
feasibility across a 3×3 grid of demand growth rates and construction lead times.

Data source: fig7_feasibility_scenarios_verified.csv
- Verified from actual experiment JSON results
- Sequential: Stage 2 hourly verification status
- Integrated: Joint planning-operation model status

Classification:
- Feasible: Confirmed feasible solve (status 2 or 9 with incumbent)
- Infeasible: Confirmed infeasible (status 3, no incumbent)
- Not tested: No valid experiment record found

Verified coverage:
- Sequential: 5 tested (all Infeasible), 4 not tested
- Integrated: 3 Feasible, 2 Infeasible, 4 not tested

Author: Generated for HRS Dispatch Paper - SETA Submission
Date: 2026-10-27
Version: FINAL (Layout Corrected)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# SETA journal publication standards
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.titlesize'] = 10
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

# File paths
DATA_DIR = Path(__file__).parent
OUTPUT_DIR = Path(__file__).parent

print("="*70)
print("Figure 7: Feasibility Outcomes Across Scenarios (Layout Corrected)")
print("="*70)

# Load verified scenario data
print("\n[1/5] Loading verified feasibility scenarios...")
df = pd.read_csv(DATA_DIR / 'fig7_feasibility_scenarios_verified.csv')

# Remove duplicate records
df_dedup = df.drop_duplicates(subset=['growth_rate', 'lead_time', 'formulation'], keep='first')
print(f"   Total records: {len(df)} (after deduplication: {len(df_dedup)})")

# Define scenario grid
growth_levels = [10, 15, 20]
lt_levels = [0, 1, 2]

# Color scheme (accessible, print-friendly)
colors = {
    'Feasible': '#2E5F9E',      # Deep blue
    'Infeasible': '#999999',     # Medium gray
    'Not tested': '#F5F5F5'      # Very light gray
}

# Create classification matrices
print("\n[2/5] Building classification matrices...")

def get_classification(df, growth, lt, formulation):
    """Extract classification for a specific scenario."""
    match = df[(df['growth_rate']==growth) &
               (df['lead_time']==lt) &
               (df['formulation']==formulation)]
    if len(match) == 0:
        return 'Not tested'
    return match.iloc[0]['classification']

# Build matrices
sequential_matrix = np.zeros((3, 3), dtype=object)
integrated_matrix = np.zeros((3, 3), dtype=object)

for i, lt in enumerate(lt_levels):
    for j, growth in enumerate(growth_levels):
        sequential_matrix[i, j] = get_classification(df_dedup, growth, lt, 'Sequential')
        integrated_matrix[i, j] = get_classification(df_dedup, growth, lt, 'Integrated')

# Create two-panel figure with compressed height
print("\n[3/5] Generating two-panel feasibility comparison...")

fig, (ax_seq, ax_int) = plt.subplots(1, 2, figsize=(10, 3.8))
fig.subplots_adjust(wspace=0.35, top=0.88, bottom=0.18)

# Helper function to plot scenario grid
def plot_scenario_grid(ax, matrix, panel_label, title):
    """Plot a 3x3 scenario classification grid."""

    # Draw cells
    for i in range(3):
        for j in range(3):
            classification = matrix[i, j]
            color = colors[classification]

            # Draw cell rectangle
            rect = mpatches.Rectangle((j, 2-i), 1, 1,
                                     facecolor=color,
                                     edgecolor='white',
                                     linewidth=2)
            ax.add_patch(rect)

            # Add text label
            if classification == 'Not tested':
                label = 'NT'
                fontsize = 11
                fontweight = 'normal'
                text_color = '#666666'
            elif classification == 'Feasible':
                label = 'F'
                fontsize = 12
                fontweight = 'bold'
                text_color = 'white'
            else:  # Infeasible
                label = 'I'
                fontsize = 12
                fontweight = 'bold'
                text_color = 'white'

            ax.text(j + 0.5, 2-i + 0.5, label,
                   ha='center', va='center',
                   fontsize=fontsize, fontweight=fontweight,
                   color=text_color)

    # Set axis properties
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    ax.set_aspect('equal')

    # X-axis (growth rate)
    ax.set_xticks([0.5, 1.5, 2.5])
    ax.set_xticklabels(['10%', '15%', '20%'])
    ax.set_xlabel('Annual demand growth rate', fontweight='bold')

    # Y-axis (lead time)
    ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_yticklabels(['2', '1', '0'])
    ax.set_ylabel('Construction lead time (years)', fontweight='bold')

    # Single title line (no subtitle)
    ax.set_title(f'{panel_label} {title}', fontsize=10, fontweight='bold', pad=10)

    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Remove tick marks
    ax.tick_params(left=False, bottom=False)

# Panel (a): Sequential
plot_scenario_grid(ax_seq, sequential_matrix,
                  '(a) Sequential —', 'hourly verification')

# Panel (b): Integrated
plot_scenario_grid(ax_int, integrated_matrix,
                  '(b) Integrated —', 'joint optimization')

# Create shared legend below panels
legend_elements = [
    mpatches.Patch(facecolor=colors['Feasible'], edgecolor='white', linewidth=1,
                  label='Feasible (F)'),
    mpatches.Patch(facecolor=colors['Infeasible'], edgecolor='white', linewidth=1,
                  label='Infeasible (I)'),
    mpatches.Patch(facecolor=colors['Not tested'], edgecolor='gray', linewidth=1,
                  label='Not tested (NT)')
]

fig.legend(handles=legend_elements, loc='lower center', ncol=3,
          frameon=False, bbox_to_anchor=(0.5, -0.02))

plt.tight_layout(rect=[0, 0.08, 1, 1])

# Save figure
print("\n[4/5] Saving publication-ready figure...")
output_files = {
    'pdf': OUTPUT_DIR / 'fig7_feasibility_scenarios.pdf',
    'svg': OUTPUT_DIR / 'fig7_feasibility_scenarios.svg',
    'png': OUTPUT_DIR / 'fig7_feasibility_scenarios.png'
}

for fmt, filepath in output_files.items():
    plt.savefig(filepath, format=fmt, bbox_inches='tight', dpi=300)
    file_size = filepath.stat().st_size / 1024
    print(f"   [OK] Saved: {filepath.name} ({file_size:.1f} KB)")

plt.close()

# Generate summary statistics
print("\n[5/5] Generating summary statistics...")

summary = {
    'Sequential': {
        'Feasible': (sequential_matrix == 'Feasible').sum(),
        'Infeasible': (sequential_matrix == 'Infeasible').sum(),
        'Not tested': (sequential_matrix == 'Not tested').sum()
    },
    'Integrated': {
        'Feasible': (integrated_matrix == 'Feasible').sum(),
        'Infeasible': (integrated_matrix == 'Infeasible').sum(),
        'Not tested': (integrated_matrix == 'Not tested').sum()
    }
}

print("\n" + "="*70)
print("FIGURE 7 GENERATION COMPLETE (LAYOUT CORRECTED)")
print("="*70)

print("\nScenario classification summary:")
for form in ['Sequential', 'Integrated']:
    print(f"\n  {form}:")
    for status in ['Feasible', 'Infeasible', 'Not tested']:
        count = summary[form][status]
        print(f"    {status}: {count}/9")

print("\nLayout improvements:")
print("  - Removed overlapping title/subtitle structure")
print("  - Single-line panel titles: '(a) Sequential — hourly verification'")
print("  - Removed redundant (a)/(b) boxes inside grid")
print("  - Compressed figure height (3.8 inches)")
print("  - Maintained cell size for legibility at single-column width")

print("\nNote: Classifications based on verified experiment results.")
