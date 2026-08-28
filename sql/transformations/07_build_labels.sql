-- 07_build_labels.sql
-- Purpose:
--     Attach the observed target outcome to each retrospective
--     restaurant decision snapshot.

CREATE OR REPLACE TABLE processed.labels AS
SELECT
    p.camis,
    p.cutoff_inspection_id,
    p.cutoff_date,
    p.cutoff_inspection_type,
    p.cutoff_is_cycle_initial,
    p.cutoff_is_cycle_reinspection,
    p.target_inspection_id,
    p.target_inspection_date,
    p.target_inspection_type,
    p.days_to_target,
    CAST(i.has_critical_violation AS INTEGER) AS target_critical,
    CASE
        WHEN i.has_critical_violation THEN 'critical_outcome'
        ELSE 'no_critical_outcome'
    END AS target_label
FROM processed.prediction_population p
JOIN processed.inspections i
    ON i.inspection_id = p.target_inspection_id
WHERE i.is_eligible_target_event = TRUE
  AND p.target_inspection_date > p.cutoff_date;