-- 01_foundation_checks.sql
-- Purpose:
--     Validate foundational warehouse tables before downstream
--     population, label, feature, or modeling work begins.

SELECT
    'normalization_row_count' AS check_name,
    CASE
        WHEN raw_row_count = normalized_row_count THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    raw_row_count,
    normalized_row_count,
    normalized_row_count - raw_row_count AS difference
FROM (
    SELECT
        (SELECT COUNT(*) FROM raw_inspection) AS raw_row_count,
        (
            SELECT COUNT(*)
            FROM processed.normalized_inspection_rows
        ) AS normalized_row_count
);

SELECT
    'unexpected_critical_flag' AS check_name,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS unexpected_row_count
FROM processed.normalized_inspection_rows
WHERE critical_flag = 'Unexpected';

SELECT
    'deduplication_audit' AS check_name,
    'INFO' AS status,
    input_row_count,
    output_row_count,
    exact_duplicates_removed
FROM processed.deduplication_audit;

SELECT
    'restaurant_camis_uniqueness' AS check_name,
    CASE
        WHEN COUNT(*) - COUNT(DISTINCT camis) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS restaurant_rows,
    COUNT(DISTINCT camis) AS unique_camis,
    COUNT(*) - COUNT(DISTINCT camis) AS duplicate_camis
FROM processed.restaurants;

SELECT
    'no_sentinel_dates_in_events' AS check_name,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS sentinel_event_count
FROM processed.inspections
WHERE inspection_date = DATE '1900-01-01';

SELECT
    'duplicate_inspection_id' AS check_name,
    inspection_id,
    COUNT(*) AS duplicate_count
FROM processed.inspections
GROUP BY inspection_id
HAVING COUNT(*) > 1;

SELECT
    'violations_map_to_inspections' AS check_name,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS violations_without_matching_inspection
FROM processed.violations v
LEFT JOIN processed.inspections i
    ON i.inspection_id = v.inspection_id
WHERE i.inspection_id IS NULL;

SELECT
    'inspection_type_policy_audit' AS check_name,
    inspection_type,
    COUNT(*) AS event_count,
    SUM(
        CASE
            WHEN is_eligible_target_event THEN 1
            ELSE 0
        END
    ) AS target_eligible_events,
    SUM(
        CASE
            WHEN is_eligible_historical_event THEN 1
            ELSE 0
        END
    ) AS historical_eligible_events,
    SUM(
        CASE
            WHEN has_critical_violation THEN 1
            ELSE 0
        END
    ) AS critical_events,
    ROUND(
        100.0 * AVG(
            CASE
                WHEN has_critical_violation THEN 1.0
                ELSE 0.0
            END
        ),
        2
    ) AS critical_rate_pct
FROM processed.inspections
GROUP BY inspection_type
ORDER BY event_count DESC;

SELECT
    'event_attribute_conflicts' AS check_name,
    COUNT(*) AS conflicting_event_count
FROM processed.inspections
WHERE distinct_score_count > 1
   OR distinct_grade_count > 1
   OR distinct_action_count > 1;