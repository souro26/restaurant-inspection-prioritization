-- ============================================================
-- 08_build_features.sql
-- Purpose:
--     Build historical features for each prediction example.
--
--     All features use information strictly before the
--     prediction cutoff.
--
--     No target information is used here.
-- ============================================================

CREATE OR REPLACE TABLE processed.features AS
WITH historical_inspections AS (
    SELECT
        p.camis,
        p.cutoff_date,
        COUNT(i.inspection_date) AS inspection_count,
        MAX(i.inspection_date) AS last_inspection_date,
        MAX(i.score) AS max_historical_score,
        AVG(i.score) AS average_historical_score,
        COUNT(i.inspection_date) FILTER (
            WHERE i.inspection_date >= p.cutoff_date - INTERVAL '365 days'
        ) AS inspections_last_365d
    FROM processed.prediction_population p
    LEFT JOIN processed.inspections i
        ON i.camis = p.camis
       AND i.inspection_date < p.cutoff_date
    GROUP BY
        p.camis,
        p.cutoff_date
),

historical_violations AS (
    SELECT
        p.camis,
        p.cutoff_date,
        COUNT(v.violation_code) AS total_violations,
        COUNT(*) FILTER (
            WHERE v.critical_flag = 'Critical'
        ) AS critical_violations,
        COUNT(v.violation_code) FILTER (
            WHERE v.inspection_date >= p.cutoff_date - INTERVAL '365 days'
        ) AS violations_last_365d,
        COUNT(*) FILTER (
            WHERE v.inspection_date >= p.cutoff_date - INTERVAL '365 days'
              AND v.critical_flag = 'Critical'
        ) AS critical_violations_last_365d
    FROM processed.prediction_population p
    LEFT JOIN processed.violations v
        ON v.camis = p.camis
       AND v.inspection_date < p.cutoff_date
    GROUP BY
        p.camis,
        p.cutoff_date
)

SELECT
    h.camis,
    h.cutoff_date,
    h.inspection_count,
    v.total_violations,
    v.critical_violations,
    CASE
        WHEN h.inspection_count = 0 THEN 0.0
        ELSE
            1.0 * v.critical_violations
            / h.inspection_count
    END AS critical_violation_rate,
    h.last_inspection_date,
    CASE
        WHEN h.last_inspection_date IS NULL THEN NULL
        ELSE h.cutoff_date - h.last_inspection_date
    END AS days_since_last_inspection,
    h.max_historical_score,
    h.average_historical_score,
    h.inspections_last_365d,
    v.violations_last_365d,
    v.critical_violations_last_365d,
    CASE
        WHEN h.inspection_count = 0 THEN 0
        ELSE 1
    END AS has_history
FROM historical_inspections h
JOIN historical_violations v
    ON v.camis = h.camis
   AND v.cutoff_date = h.cutoff_date;