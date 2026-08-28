-- 04_build_inspection_events.sql
-- Purpose:
-- Transform violation-level records into one row per inspection event.

CREATE OR REPLACE TABLE processed.inspections AS
SELECT
    md5(
        CONCAT_WS(
            '|',
            camis,
            CAST(inspection_date AS VARCHAR),
            COALESCE(inspection_type, 'UNKNOWN')
        )
    ) AS inspection_id,
    camis,
    inspection_date,
    COALESCE(inspection_type, 'UNKNOWN') AS inspection_type,
    CASE
        WHEN COALESCE(inspection_type, 'UNKNOWN') IN (
            'Cycle Inspection / Initial Inspection',
            'Cycle Inspection / Re-inspection'
        ) THEN TRUE
        ELSE FALSE
    END AS is_cycle_inspection,
    CASE
        WHEN COALESCE(inspection_type, 'UNKNOWN')
            = 'Cycle Inspection / Initial Inspection'
        THEN TRUE
        ELSE FALSE
    END AS is_cycle_initial,
    CASE
        WHEN COALESCE(inspection_type, 'UNKNOWN')
            = 'Cycle Inspection / Re-inspection'
        THEN TRUE
        ELSE FALSE
    END AS is_cycle_reinspection,
    CASE
        WHEN COALESCE(inspection_type, 'UNKNOWN')
            = 'Cycle Inspection / Initial Inspection'
        THEN TRUE
        ELSE FALSE
    END AS is_eligible_target_event,
    CASE
        WHEN COALESCE(inspection_type, 'UNKNOWN') IN (
            'Cycle Inspection / Initial Inspection',
            'Cycle Inspection / Re-inspection'
        )
        THEN TRUE
        ELSE FALSE
    END AS is_eligible_historical_event,
    MAX(score) AS score,
    MAX(grade) AS grade,
    MAX(grade_date) AS grade_date,
    MAX(action) AS action,
    COUNT(*) AS source_row_count,
    COUNT(violation_code) AS total_violations,
    COUNT(*) FILTER (
        WHERE critical_flag = 'Critical'
    ) AS critical_violation_count,
    COUNT(*) FILTER (
        WHERE critical_flag = 'Not Critical'
    ) AS noncritical_violation_count,
    COUNT(violation_code) > 0 AS has_any_violation,
    COUNT(*) FILTER (
        WHERE critical_flag = 'Critical'
    ) > 0 AS has_critical_violation,
    COUNT(DISTINCT score) FILTER (
        WHERE score IS NOT NULL
    ) AS distinct_score_count,
    COUNT(DISTINCT grade) FILTER (
        WHERE grade IS NOT NULL
    ) AS distinct_grade_count,
    COUNT(DISTINCT action) FILTER (
        WHERE action IS NOT NULL
    ) AS distinct_action_count
FROM processed.deduplicated_inspection_rows
WHERE camis IS NOT NULL
  AND inspection_date IS NOT NULL
  AND inspection_date <> DATE '1900-01-01'
GROUP BY
    camis,
    inspection_date,
    COALESCE(inspection_type, 'UNKNOWN');