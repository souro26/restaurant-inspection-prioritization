-- 04_build_inspection_events.sql
-- Purpose:
--     Transform violation-level records into one row per
--     inspection event.

CREATE OR REPLACE TABLE processed.inspections AS
SELECT
    camis,
    inspection_date,
    inspection_type,

    MAX(score) AS score,
    MAX(grade) AS grade,
    MAX(grade_date) AS grade_date,
    MAX(action) AS action,

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
    ) > 0 AS has_critical_violation

FROM processed.deduplicated_inspection_rows
WHERE camis IS NOT NULL
  AND inspection_date IS NOT NULL
  AND inspection_date <> DATE '1900-01-01'
GROUP BY
    camis,
    inspection_date,
    inspection_type;