# Migration Notes: Tableau → Power BI

This document tracks the migration of the Dominion Trust Branch Performance Scorecard from Tableau to Power BI — what translated directly, what had to be redesigned, and why.

## Migration approach

The solution was built Tableau-first with all scoring logic in SQLite views. The Power BI rebuild deliberately moved that logic into DAX measures rather than importing the pre-computed views, to compare the two architectures and exercise DAX at depth.

## Logic translation map

| Concept | SQL / Tableau | Power BI / DAX |
|---|---|---|
| Pillar pct-to-target | `actual / target` in view | `DIVIDE([Actual], [Target])` measure |
| Safe division | `NULLIF(target, 0)` guard | `DIVIDE()` (returns BLANK on zero) |
| Role-weighted total score | Weights joined from `dim_role_weights`, summed in view | Weighted measure composed from pillar measures + weight lookup |
| Role exclusions (Teller: no Lending/Investing; Advisor/Teller: no Compliance) | `CASE WHEN role = 'Teller' THEN NULL …` | Conditional measure logic; missing weight rows naturally exclude pillars |
| Rank within role (company-wide) | `RANK() OVER (PARTITION BY role, month_number ORDER BY score DESC)` | `RANKX` with `ALLEXCEPT` keeping role + month context |
| Rank within branch | `RANK() OVER (PARTITION BY branch_id, month_number …)` | `RANKX` with `ALLEXCEPT` keeping branch + month context |
| RAG banding | `CASE WHEN score >= 1.0 THEN 'Green' …` view column | `SWITCH(TRUE(), …)` measure (responds to filter context) |
| Branch score (Manager weights) | Dedicated view aggregating to branch grain | Branch-grain measures over the same model |

## Key architectural differences

**Where logic lives.** SQL views pre-compute results at a fixed grain; every consumer sees identical numbers. DAX computes at query time against the filter context — more flexible (one measure re-ranks under any filter), but correctness must be validated per visual.

**Ranking context.** In SQL, ranking scope is explicit in `PARTITION BY`. In DAX, scope comes from manipulating filter context (`ALLEXCEPT`, `ALLSELECTED`), which is more powerful but easier to get subtly wrong — validated by reconciling RANKX output against `vw_employee_rank`.

**Relationships and fan-out.** Tableau's extract-per-view approach sidestepped modeling; Power BI's model relates tables directly, which surfaced fan-out when facts were related at mismatched grain. Resolved with lookup/calculated logic instead of direct fact-to-fact relationships (see README, Problems #3).

## Validation

Every DAX measure was reconciled against the SQLite views (same employee, month, and score to 4 decimal places) before the Tableau logic was considered fully migrated.

## Status

- [x] Data model imported and relationships defined
- [x] Pillar and weighted-score measures
- [x] RANKX ranking (branch + role contexts)
- [x] RAG banding
- [x] Final dashboard layout parity with Tableau version
- [x] Publish .pbix to this repo (`powerbi/dominion_trust_scorecard.pbix`)
