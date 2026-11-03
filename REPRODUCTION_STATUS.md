# Author-run reference-case reproduction (November 2026)

The following outcomes were reported from **independent local reruns by the first author** of the curated reference-case scripts using an authorized 1,680-row representative-week dataset. This is a factual record of the displayed Gurobi outputs; the public code archive does not distribute the empirical CSV or the demand-derived 8,400-row warm-start schedule. The code release packager did not rerun Gurobi.

**Environment reported:** Windows 11, Python 3.14.2, `gurobipy`/Gurobi 13.0.1, Intel Core Ultra 7 255H, up to 16 solver threads. Representative-week input SHA-256: `f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef`.

All monetary figures are in `10^4 CNY` (10,000 CNY); statuses and MIP gaps apply to each model's **own** objective.

| Model | Observed run | Objective / cost | Stopping certificate |
|---|---|---:|---|
| A1: aggregate-screened CAPEX | Investment at t=2: S+100, K+120; t=3: S+200 | CAPEX 379.286694 | Investment stage solved to optimality |
| A2: hourly check at A1 investments | Five-period schedule with compressor held at 100 kg/h | No feasible schedule | `INFEASIBLE` (`Status=3`), computed IIS: 9 constraints |
| B: hourly-constrained CAPEX | t=1 C+50; t=2 S+200, K+120; t=3 C+100 | CAPEX 635.541838; incidental OPEX 4246.077010 | `OPTIMAL` (`Status=2`), MIP gap 0.0000%; runtime 20.46 s |
| D: fixed B investments, OPEX | Same fixed investment portfolio | OPEX 3999.916338; total 4635.458176 | **Author rerun** `TIME_LIMIT` (`Status=9`), gap 0.1283%, bound 3994.785342; runtime 1805.97 s |
| C+: joint CAPEX+OPEX | Same investment schedule in reported feasible incumbent | CAPEX 635.541838; OPEX 3999.916336; total 4635.458174 | `TIME_LIMIT` (`Status=9`), gap 0.2321%, bound 4624.697857; runtime 1805.28 s |

The original archived D optimization attained the **same OPEX** with a reported **0.0998% gap**, meeting a 0.1% requested gap tolerance. The independent author rerun attained the same feasible OPEX but a **0.1283% gap** at the time limit. Thus the feasible **cost** was reproduced, while the D stopping certificate was **not identical**. The older `model_d_solution_export_20261029_221345.json` incorrectly serialized gap `0`; that obsolete metadata is intentionally not included in the public release tree.

The C+ author rerun independently matched the original recorded 4635.458174 total, 4624.697857 best bound and 0.2321% gap. Gurobi accepted the saved Model D MIP start (8,400 hourly entries). The C+ log contained a maximum constraint-violation warning of approximately `1e-6`; this is a numerical feasibility qualification, not an assertion of exact-zero residual.

## Scope of reproduction

* A and B: objective values and solver statuses reproduced as indicated.
* D: best known feasible operating cost reproduced; original gap/status not reproduced at the 1800 s cutoff.
* C+: feasible total and nonzero MIP gap reproduced; **global optimum was not proven**.
* Sensitivity experiments, all figures, and privacy-restricted datasets were not independently rebuilt as part of these author reruns.

No enterprise records, restricted representative-week rows, hourly solution CSVs, `.sol` files, Gurobi license material, or workstation-specific absolute paths are published here.
