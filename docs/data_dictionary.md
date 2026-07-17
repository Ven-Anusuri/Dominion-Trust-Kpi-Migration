# Data Dictionary

## dim_branch (300 rows)
| Column | Type | Description |
|---|---|---|
| branch_id | INTEGER | Branch key |
| branch_code | TEXT | Code, e.g. `SMA001` (tier prefix + number) |
| branch_name | TEXT | Branch display name |
| tier | TEXT | Small / Medium / Large |
| province, city | TEXT | Location |
| manager_count, advisor_count, teller_count, employee_count | INTEGER | Headcount by role |
| opening_year | INTEGER | Year opened |

## dim_employee (2,400 rows)
| Column | Type | Description |
|---|---|---|
| employee_id | INTEGER | Employee key |
| branch_id, branch_code, tier, province, city | — | Branch attributes |
| role | TEXT | Manager / Advisor / Teller |
| first_name, last_name | TEXT | Name |
| hire_date | TEXT | ISO date |

## dim_role_weights (11 rows)
Role × pillar weight (`weight_pct`). Rows exist only for pillars applicable to a role — e.g. Teller has only Banking units (70) and LEI (30).

## fact_sales (28,800 rows — employee × month)
Monthly actuals: `lending_actual`, `investing_actual`, `banking_units_actual`, `lei_actual`.

## fact_targets (28,800 rows — employee × month)
Monthly targets: `target_lending`, `target_investing`, `target_banking_units`, `target_lei`, `target_compliance`.

## fact_lei_survey (28,800 rows — employee × month)
`survey_response_count`, `lei_score` (customer experience survey detail behind the LEI pillar).

## fact_compliance (3,600 rows — branch × month)
`compliance_score`, `risk_score`, `exceptions_count`. Branch grain — compliance is a manager/branch-level accountability.

## Views
| View | Purpose |
|---|---|
| `vw_employee_monthly_score` | Pillar pct-to-target + weighted total score per employee/month; role exclusions applied |
| `vw_employee_rank` | Adds `rank_within_role` (company-wide) and `rank_within_branch` |
| `vw_branch_monthly_score` | Branch-level aggregation scored with Manager weights (incl. compliance) |
| `vw_branch_pacing` | Adds RAG banding: Green ≥ 1.0, Amber ≥ 0.9, Red < 0.9 |
