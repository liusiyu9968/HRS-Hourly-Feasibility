# Code release review notes

## Selection and provenance

The original user ZIP contains ~396 archive entries, including superseded models, invalid result sets, engineering audit reports, raw enterprise spreadsheets and site photographs. These items are intentionally excluded from this curated code release. The published reference joint run uses `experiments/integrated_consistency_validation/final_model_equivalence_fix/run_integrated_corrected.py`, not the historical 4700.59 x 10^4 CNY / 1.64% incumbent or the 0.488% gap run from an earlier non-equivalent investment formulation. The corrected C+ JSON and source code were both included. The corrected log supplied in the user project reports 67,275 variables, 109,301 constraints, total objective CNY 46,354,581.74237, best bound CNY 46,246,978.57473 and 0.2321% gap.

## Non-optimization repairs to packaging

1. Removed hardcoded Gurobi LicenseID assignments from selected source scripts; users supply their own license.
2. Added an environment-based way to select the Model D warm-start CSV/JSON pair for C+, retaining the old relative defaults. This affects input-file resolution, not model mathematics.
3. Fixed result serialization in the D-export and C+ scripts so the saved MIP gap and best bound use `m.MIPGap` and `m.ObjBound` even after an `OPTIMAL` (tolerance-based) stop. The uploaded archived D-export JSON wrote a zero gap at `OPTIMAL` regardless of the actual achieved gap; the final paper's documented D-gap is ~0.0998%. **Archived JSON is not silently edited.**
4. Removed a superseded 701.48 value from the B script's printed explanatory boilerplate; no model constraints or objectives were changed.

## Validation performed

- All selected Python source files compiled as Python syntax.
- Corrected C+ source and recorded JSON match reference outputs.
- The author-only 1,680-row empirical CSV passes SHA-256, representative-week ID and weighting checks.
- Public package excludes enterprise raw data, the representative-week CSV, hour-level trajectories, solver license identifiers and local machine configuration.
- An executable Gurobi solver was absent, so no numerical MILP reproduction, IIS recalculation, or sensitivity rerun was performed.

## Remaining actions for authors

- Verify ownership and permission to redistribute code and restricted inputs.
- Select a publication license (none is invented by this archive).
- Test a fresh run on a clean machine with Gurobi 13.0.1; compare results with the paper using tolerances.
- Confirm the repository contains only files authorized for public release.
- Deposit the public package and add its actual URL / DOI to the manuscript Code availability statement.
- Never publish the separate author-only replication ZIP without permission.
