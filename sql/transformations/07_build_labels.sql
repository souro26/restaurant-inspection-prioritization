-- 07_build_labels.sql
-- Purpose:
--     Attach the observed outcome of the target inspection to
--     each retrospective restaurant decision snapshot.

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

    i.total_violations AS target_total_violations,
    i.critical_violation_count AS target_critical_violation_count,
    i.noncritical_violation_count AS target_noncritical_violation_count,
    i.score AS target_score,
    i.grade AS target_grade,
    i.action AS target_action,

    CAST(
        i.critical_violation_count >= 1
        AS INTEGER
    ) AS target_any_critical,
    CAST(
        i.critical_violation_count >= 2
        AS INTEGER
    ) AS target_two_or_more_critical,
    CAST(
        i.critical_violation_count >= 3
        AS INTEGER
    ) AS target_three_or_more_critical,
    CAST(
        i.critical_violation_count >= 4
        AS INTEGER
    ) AS target_four_or_more_critical,
    CAST(
        i.critical_violation_count >= 3
        AS INTEGER
    ) AS target_high_severity,

    CASE
        WHEN i.critical_violation_count >= 3
            THEN 'high_severity_critical_outcome'
        ELSE 'below_high_severity_threshold'
    END AS target_label

FROM processed.prediction_population AS p
INNER JOIN processed.inspections AS i
    ON i.inspection_id = p.target_inspection_id

WHERE i.is_eligible_target_event = TRUE
  AND p.target_inspection_date > p.cutoff_date;