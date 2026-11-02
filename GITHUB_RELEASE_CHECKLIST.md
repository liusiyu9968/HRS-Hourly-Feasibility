# GitHub publication checklist (author action required)

The staging bundle has not been publicly released, and it is not licensed yet.

Before making the repository public:
1. Obtain all code owners' and institution's approval for redistribution.
2. Choose and add a real `LICENSE` file; no license is assumed by the package.
3. Test the package with licensed Gurobi and authorized empirical data on a fresh machine; save a factual record of what ran.
4. Recheck that the GitHub commit contains NO restricted data, raw records, hourly trajectories, authentication material, or solver license file.
5. Verify the two included archived non-sensitive output JSON files are tracked by Git.
6. Only after publication, create the permanent DOI archive and edit the paper's Code availability statement.

Packaging adjustments from supplied v1 (no optimization equations changed):
- `.gitignore` now allows the two reference result JSON files to be committed.
- Removed obsolete old-incumbent comparisons from Model B's introductory comments.
- Corrected the stale Fig. 3 script status note (historical gap 1.64% => reference gap 0.2321%).
- Clarified Fig. 6 comment as time-limited feasible incumbent, not globally optimal solution.
- Corrected an output-only K capacity unit label; clarified shared parameter assumptions.
- Documented that several plotting scripts require non-public or omitted supporting CSVs.

Static tests: ZIP validity, Python syntax, recorded scalar consistency and SHA256 manifest.
Not tested: fresh MILP solver run or end-to-end figure reproduction.
