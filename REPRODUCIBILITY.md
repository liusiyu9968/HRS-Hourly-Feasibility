# Reproduction details and important limitations

### Software
The original reference runs used Gurobi 13.0.1 on Windows with up to 16 threads. The author subsequently repeated the core reference cases locally with Python 3.14.2, Gurobi 13.0.1, and authorized input. Those results are documented in [REPRODUCTION_STATUS.md](REPRODUCTION_STATUS.md); the current release packager did not perform a separate solver rerun. Different platforms, threads, starts, and time limits may change bounds and stopping status even if the best feasible schedule matches.

### Run sequence
1. `python scripts/check_package.py --input` (requires authorized empirical CSV).
2. `python scripts/run_experiment.py a` for A1 / A2.
3. `python scripts/run_experiment.py b` for B.
4. `python scripts/run_experiment.py d` for OPEX control (uses published Model B investment path by default).
5. `python scripts/run_experiment.py d-export` to generate a full Model D operating trajectory and its summary, needed for the C+ MIP start.
6. `python scripts/run_experiment.py c` for the corrected C+ formulation.

These scripts create timestamped results in their own experiment folders. Outputs are **not** guaranteed to be bitwise identical on subsequent solves. The D-export regeneration can be expensive; a previous full-hour export is available only in the author-only replication archive. The corrected C+ formulation has 67,275 pre-presolve variables and 109,301 constraints in the archived run. The archived C+ run terminated at about 1806.67 s (nominal 1800 s limit) with a 0.2321% gap; the author's November rerun terminated at 1805.28 s with the same 0.2321% gap and bound. Both report a time-limited feasible incumbent, not a proven global minimum.

### Sensitivity runs
Use `python scripts/run_experiment.py growth -- 10` or `-- 20`, and `python scripts/run_experiment.py leadtime -- 0` or `-- 2`. `storage` runs the original sequential screening sensitivity scan; consult the original source code before use because it may test more levels than the paper's selected S0 cases. Sensitivity outputs were not re-certified as the same exact integrated formulation with the corrected warm start.

### Baseline script compatibility
`unified_params.py` has a `S_0=250` default inherited from earlier work; the included **final case** scripts override this to `S_0=158`. Do not treat the default as the published baseline. Some legacy commentary may refer to older results; only the corrected C+ script and the recorded reference JSON are authoritative for the paper's joint baseline.

### Data and warm-start handling
The original empirical dataset has a SHA-256 checksum `f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef`. It should never be republished from the author-only archive without authorization. For a newly generated warm start, use the launcher to discover the most recent matching D-export pair. Avoid changing file contents simply to force a checksum match.

### Scientific interpretation
A1 aggregated constraints are neither proven necessary nor sufficient for the complete hourly feasible set. Model B and A1 share an identical CAPEX objective but differ in their constraint systems. Model D's OPEX improvement is relative to B's incidental dispatch. Fixed-demand hydrogen purchase and equal within-week high-pressure inventory boundaries keep modeled purchase and compression quantities invariant at fixed input; arrival costs cause the reported dispatch-dependent OPEX variation.


### Public metadata provenance

An earlier archived Model D export summary serialized a zero MIP gap even though the underlying tolerance-based termination did not certify zero gap. It has been excluded from the current release tree. `results/reference/paper_reference_case.json` retains the original reported D tolerance-based result; the author's independent rerun retained the same feasible OPEX but terminated at 0.1283% gap. This distinction is essential when citing solver certificates.
