# Hourly Feasibility in HRS Capacity Expansion — Research Code

This repository contains **curated Python implementations** supporting the paper on aggregate capacity screening and hourly feasibility for a single tube-trailer hydrogen refueling station (HRS). It is a source-code release, **not an openly reproducible empirical dataset**. Full numerical reproduction requires the restricted representative-week input, the relevant hourly warm start (or permission to regenerate it), and a valid Gurobi license.

## Models included

| Paper name | Source | Scope |
|---|---|---|
| A1/A2 | `experiments/verify_s0_158_sequential.py` | Aggregate CAPEX investment and fixed-investment hourly verification |
| B | `experiments/integrated_capex_control/run_integrated_capex_only.py` | Minimum CAPEX with complete hourly constraints |
| D | `experiments/fixed_investment_opex_control/run_fixed_investment_opex.py` | OPEX optimization at Model B's fixed investment |
| D export | `experiments/integrated_consistency_validation/export_model_d_solution.py` | Generate the 8,400-hour trajectory for C+ warm start |
| C+ | `experiments/integrated_consistency_validation/final_model_equivalence_fix/run_integrated_corrected.py` | Joint CAPEX + OPEX, with each **option** purchasable at most once across five years |
| Supplementary | `experiments/forced_compressor_counterfactual_v2.py`, `run_growth_sensitivity.py`, `run_leadtime_sensitivity.py`, `run_s0_sensitivity_screening.py` | Counterfactual and sensitivity scripts; see limitations below |

Do **not** substitute the superseded joint model found elsewhere in the original project. The corrected C+ source above corresponds to the recorded 0.2321% MIP-gap result.

## Quick start

1. Install Python and Gurobi; activate your own Gurobi license. `pip install -r requirements.txt`.
2. Run `python scripts/check_package.py`. This checks included scientific result metadata without solving MILPs.
3. For empirical runs, obtain permission to access the representative-week dataset and place its **unmodified** CSV at `data/processed/representative_weeks_FixedEP_W10_FINAL.csv`. Run `python scripts/check_package.py --input`.
4. Execute the original scripts using the working-directory-safe launcher:

```bash
python scripts/run_experiment.py a
python scripts/run_experiment.py b
python scripts/run_experiment.py d
python scripts/run_experiment.py d-export
python scripts/run_experiment.py c
python scripts/run_experiment.py forced
```

C+ requires an 8,400-hour Model D schedule: the launcher locates the latest generated valid CSV/JSON pair or the original archived pair (if supplied to an authorized user). Typical full solves may require substantial compute time and RAM, and floating-point solver output may differ across hardware/version. An `OPTIMAL` solver status may reflect a specified **nonzero** MIP-gap threshold.

The sensitivity and plot scripts are preserved for transparency, but have **not** been independently re-executed in this packaging environment. Their historical outputs may have different run budgets and should not be mistaken for uniformly certified global optima.

## Recorded reference-case results

All money values in `10^4 CNY`. This is a *record of supplied result files*, not fresh solver certification by the packager.

| Model | CAPEX | OPEX | Status / note |
|---|---:|---:|---|
| A1/A2 | 379.29 | — | A1 OPTIMAL; A2 INFEASIBLE |
| B | 635.541838 | 4246.077010 | OPTIMAL for CAPEX; OPEX of incidental feasible dispatch |
| D | 635.541838 | 3999.916338 | Author rerun: TIME_LIMIT, 0.1283% MIP gap; earlier archived run: 0.0998% gap |
| C+ | 635.541838 | 3999.916336 | TIME_LIMIT, best-known total 4635.458174; gap 0.2321% |

See `results/reference/paper_reference_case.json` for the corresponding numerical record.

## Data confidentiality and scope

Original business transaction records, enterprise spreadsheets/images, the actual 1,680-row representative-week demand matrix, and demand-derived 8,400-hour trajectories are **excluded**. The CSV is available subject to the data owner's permission and the authors' reasonable-request conditions; availability is not guaranteed to every requester. Inspect `data/processed/README.md`.

The code contains operating-model simplifications (hourly time steps, independent representative weeks, no compressor pressure dynamics or vehicle queues) as described in the paper. The scripts have not been modernized into a new software framework; only necessary packaging changes were made.

## Availability of figure-generation inputs

The plotting scripts in `paper/figures/` have been retained for provenance, but
some require restricted hourly trajectories or historical supporting CSV exports
not supplied with the public release. Do not assume the public package can
regenerate every manuscript figure without separately authorized inputs.
For the published case, the recorded scalar results and corrected C+ script
are the reference; the authors should independently inspect figure input files
before using any plotting script.

## Repository status, licensing, and limitations

The original research source code is licensed under the [BSD 3-Clause License](LICENSE), copyright (c) 2026 Siyu Liu. This license does not license restricted station data or third-party dependencies such as Gurobi. Users must obtain their own solver license. The model formulations were not changed during publication preparation; explanatory text, output-unit labels, and packaging were updated.

The author re-executed the core reference-case models with Gurobi 13.0.1 on Windows in November 2026. See [REPRODUCTION_STATUS.md](REPRODUCTION_STATUS.md) for the observed results and solver qualifications, especially the difference between a matching feasible Model D cost and its nonmatching time-limit gap. The input data and hour-by-hour warm start remain restricted; this repository does not provide a public end-to-end numerical reproduction.

The public release excludes an older Model D export-metadata JSON whose reported zero MIP gap was a serialization error. The exporter source now records `m.MIPGap` and `m.ObjBound` directly. The archived research baseline and the independent rerun are documented separately. The earlier metadata may still be visible in repository history; it must not be used as an optimality certificate.


## Code license

Copyright (c) 2026 Siyu Liu. The original research source code is licensed under [BSD-3-Clause](LICENSE). The station data and proprietary solver have separate access/licensing requirements.
