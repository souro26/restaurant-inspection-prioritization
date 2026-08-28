-- 08_build_features.sql
-- Purpose:
-- Build leakage-safe historical features for each retrospective
-- restaurant decision snapshot.

CREATE OR REPLACE TABLE processed.features AS
WITH historical_inspections AS (
    SELECT
        p.camis,
        p.cutoff_inspection_id,
        p.cutoff_date,
        COUNT(i.inspection_id) AS prior_cycle_inspection_count,
        COUNT(*) FILTER (
            WHERE i.is_cycle_initial
        ) AS prior_cycle_initial_count,
        COUNT(*) FILTER (
            WHERE i.is_cycle_reinspection
        ) AS prior_cycle_reinspection_count,
        COUNT(*) FILTER (
            WHERE i.has_critical_violation
        ) AS prior_critical_inspection_count,
        COUNT(*) FILTER (
            WHERE i.is_cycle_initial
              AND i.has_critical_violation
        ) AS prior_cycle_initial_critical_count,
        COUNT(*) FILTER (
            WHERE i.is_cycle_reinspection
              AND i.has_critical_violation
        ) AS prior_cycle_reinspection_critical_count,
        SUM(COALESCE(i.critical_violation_count, 0))
            AS prior_critical_violation_count,
        MAX(i.inspection_date) AS last_cycle_inspection_date,
        MAX(
            CASE
                WHEN i.has_critical_violation
                THEN i.inspection_date
            END
        ) AS last_critical_inspection_date,
        MAX(i.score) AS max_historical_score,
        AVG(i.score) AS average_historical_score,
        COUNT(*) FILTER (
            WHERE i.inspection_date >= p.cutoff_date - INTERVAL '365 days'
        ) AS cycle_inspections_last_365d,
        COUNT(*) FILTER (
            WHERE i.inspection_date >= p.cutoff_date - INTERVAL '365 days'
              AND i.has_critical_violation
        ) AS critical_cycle_inspections_last_365d,
        AVG(
            CASE
                WHEN i.inspection_date >= p.cutoff_date - INTERVAL '365 days'
                THEN i.score
            END
        ) AS average_score_last_365d
    FROM processed.prediction_population p
    LEFT JOIN processed.inspections i
      ON i.camis = p.camis
     AND i.inspection_date <= p.cutoff_date
     AND i.is_eligible_historical_event = TRUE
    GROUP BY
        p.camis,
        p.cutoff_inspection_id,
        p.cutoff_date
),
historical_violations AS (
    SELECT
        p.camis,
        p.cutoff_inspection_id,
        p.cutoff_date,
        COUNT(v.violation_code) AS prior_total_violations,
        COUNT(*) FILTER (
            WHERE v.critical_flag = 'Critical'
        ) AS prior_critical_violation_rows,
        COUNT(v.violation_code) FILTER (
            WHERE v.inspection_date >= p.cutoff_date - INTERVAL '365 days'
        ) AS violations_last_365d,
        COUNT(*) FILTER (
            WHERE v.critical_flag = 'Critical'
              AND v.inspection_date >= p.cutoff_date - INTERVAL '365 days'
        ) AS critical_violations_last_365d
    FROM processed.prediction_population p
    LEFT JOIN processed.violations v
      ON v.camis = p.camis
     AND v.inspection_date <= p.cutoff_date
     AND v.inspection_type IN (
        'Cycle Inspection / Initial Inspection',
        'Cycle Inspection / Re-inspection'
     )
    GROUP BY
        p.camis,
        p.cutoff_inspection_id,
        p.cutoff_date
),
base_features AS (
    SELECT
        h.camis,
        h.cutoff_inspection_id,
        h.cutoff_date,
        h.prior_cycle_inspection_count,
        h.prior_cycle_initial_count,
        h.prior_cycle_reinspection_count,
        h.prior_critical_inspection_count,
        h.prior_cycle_initial_critical_count,
        h.prior_cycle_reinspection_critical_count,
        h.prior_critical_violation_count,
        CASE
            WHEN h.prior_cycle_inspection_count = 0 THEN 0.0
            ELSE
                1.0 * h.prior_critical_inspection_count
                / h.prior_cycle_inspection_count
        END AS prior_critical_inspection_rate,
        h.last_cycle_inspection_date,
        DATE_DIFF(
            'day',
            h.last_cycle_inspection_date,
            h.cutoff_date
        ) AS days_since_last_cycle_inspection,
        h.last_critical_inspection_date,
        DATE_DIFF(
            'day',
            h.last_critical_inspection_date,
            h.cutoff_date
        ) AS days_since_last_critical_inspection,
        h.max_historical_score,
        h.average_historical_score,
        h.average_score_last_365d,
        h.cycle_inspections_last_365d,
        h.critical_cycle_inspections_last_365d,
        COALESCE(v.prior_total_violations, 0)
            AS prior_total_violations,
        COALESCE(v.prior_critical_violation_rows, 0)
            AS prior_critical_violation_rows,
        COALESCE(v.violations_last_365d, 0)
            AS violations_last_365d,
        COALESCE(v.critical_violations_last_365d, 0)
            AS critical_violations_last_365d
    FROM historical_inspections h
    LEFT JOIN historical_violations v
      ON v.cutoff_inspection_id = h.cutoff_inspection_id
),
final_features AS (
    SELECT
        *,
        CASE
            WHEN prior_cycle_initial_count = 0 THEN '0'
            WHEN prior_cycle_initial_count = 1 THEN '1'
            WHEN prior_cycle_initial_count BETWEEN 2 AND 3 THEN '2-3'
            ELSE '4+'
        END AS history_depth_bucket,
        CASE
            WHEN prior_cycle_initial_count = 0 THEN TRUE
            ELSE FALSE
        END AS has_no_cycle_initial_history
    FROM base_features
)
SELECT
    f.*,

    r.borough,
    r.cuisine_description,
    r.zipcode,
    r.nta,
    r.community_board
FROM final_features f
LEFT JOIN processed.restaurants r
  ON r.camis = f.camis;