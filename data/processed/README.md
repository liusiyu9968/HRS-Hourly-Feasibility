# Restricted empirical input

The file `representative_weeks_FixedEP_W10_FINAL.csv` is **NOT INCLUDED** in the public package. The authors state that processed representative-week data may be supplied upon reasonable request. Its unmodified original SHA-256 digest is `f369a035b6efd129e1a149d9d08c14920188f92b4fd359d5f0540aaad55ad9ef`. The final reference models expect exactly this file at this location.

Required columns: `hour`, `demand_kg`, `service_minutes`, `representative_week_id`, `weight`. The actual processed input also contains `order_count`, `is_zero_demand`, `week_start`, `original_date`, `scheme_type`, `is_critical`. Each of the ten weeks has 168 hourly rows (1,680 total). Weights are `[1,1,1,1,1,7,14,12,4,10]` for representative-week IDs 1–10.

**Do not redistribute the restricted file without permission.** Synthetic or modified input will not reproduce the paper's numerical results and may fail the original script's SHA-256 check.
