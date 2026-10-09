# Squad scoring design (Phase 2, not implemented)

Model `squad-v1` will be deterministic for identical squad, data snapshot, scenarios,
configuration and model version. It is a quality assessment, not a validated IPL
win prediction. No LLM supplies numerical scores.

| Dimension | Weight | Responsibility |
| --- | --- | --- |
| Player quality and form | 25% | Role-relative performance and supported recent form |
| Balance and role coverage | 25% | Positions, keeper, domestic/overseas, backups |
| Batting depth and finishing | 15% | Viable batting order and finishing coverage |
| Bowling combinations | 15% | Pace/spin mix and powerplay/death coverage |
| Conditions adaptability | 10% | Supported scenario deltas, not duplicate baseline quality |
| Budget efficiency | 10% | Pre-auction reference value versus actual spend |

Each dimension normalizes to 0-100 using versioned, frozen reference cohorts;
overall = sum(weight * dimension) / 100. Calibration thresholds, cohort minimums,
recency windows and rounding must be fixed and tested before implementing a
numerical report. These weights alone do not define a validated scoring model.

Use role-specific metrics rather than one universal player rating. Shrink sparse
observations toward a documented broader reference only where supported; disclose
coverage. Missing values are not zeros. If required dimensions cannot be computed,
overall is unavailable, not silently reweighted. Do not directly count one metric
in multiple categories; audit correlations during historical calibration.

Neutral, home/away, batting/spin/pace-friendly and high-dew scenarios are modular.
Enable only those supported by data or clearly labeled model assumptions, with
uncertainty visible. No invented venue dimensions or condition-specific precision.

Reports retain category contributions, normalization inputs, weaknesses/strengths,
valid XI alternatives, backup suggestions from eligible available players, budget
explanations, source coverage and freshness. Mandatory violations are distinct
from strategic weaknesses. Tie-breaking uses stable IDs. No feasible XI is an
explicit result, never repaired with fictitious players.

Tests must cover weight sum, bounds, missing/stale data, repeatability, legal XI
constraints, historical snapshot preservation and explanation-to-metric traceability.