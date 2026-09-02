SELECT
    'duplicate_feature_rows' AS check_name,
    cutoff_inspection_id,
    COUNT(*) AS row_count
FROM processed.features
GROUP BY cutoff_inspection_id
HAVING COUNT(*) > 1;
SELECT
    'feature_label_count_match' AS check_name,
    CASE
        WHEN feature_rows = label_rows THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    feature_rows,
    label_rows,
    feature_rows - label_rows AS difference
FROM (
    SELECT
        (SELECT COUNT(*) FROM processed.features) AS feature_rows,
        (SELECT COUNT(*) FROM processed.labels) AS label_rows
);
SELECT
    'features_map_to_prediction_population' AS check_name,
    CASE
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS features_without_prediction_population
FROM processed.features f
LEFT JOIN processed.prediction_population p
    ON p.cutoff_inspection_id = f.cutoff_inspection_id
WHERE p.cutoff_inspection_id IS NULL;
SELECT
    'future_event_in_feature_history' AS check_name,
    *
FROM processed.features
WHERE last_cycle_inspection_date > cutoff_date;
SELECT
    'negative_feature_counts' AS check_name,
    *
FROM processed.features
WHERE prior_cycle_inspection_count < 0
   OR prior_cycle_initial_count < 0
   OR prior_cycle_reinspection_count < 0
   OR prior_critical_inspection_count < 0
   OR prior_critical_violation_count < 0
   OR cycle_inspections_last_365d < 0
   OR critical_cycle_inspections_last_365d < 0;
SELECT
    'inconsistent_feature_counts' AS check_name, *
FROM processed.features
WHERE prior_cycle_initial_count + prior_cycle_reinspection_count
        <> prior_cycle_inspection_count
   OR prior_critical_inspection_count
        > prior_cycle_inspection_count
   OR prior_cycle_initial_critical_count
        > prior_cycle_initial_count
   OR prior_cycle_reinspection_critical_count
        > prior_cycle_reinspection_count
   OR critical_cycle_inspections_last_365d
        > cycle_inspections_last_365d;
SELECT
    'invalid_critical_inspection_rate' AS check_name,
    *
FROM processed.features
WHERE prior_critical_inspection_rate < 0
   OR prior_critical_inspection_rate > 1
   OR prior_critical_inspection_rate IS NULL;
SELECT
    'invalid_history_depth_bucket' AS check_name,
    *
FROM processed.features
WHERE
    (prior_cycle_initial_count = 0
        AND history_depth_bucket <> '0')
    OR
    (prior_cycle_initial_count = 1
        AND history_depth_bucket <> '1')
    OR
    (prior_cycle_initial_count BETWEEN 2 AND 3
        AND history_depth_bucket <> '2-3')
    OR
    (prior_cycle_initial_count >= 4
        AND history_depth_bucket <> '4+');
SELECT
    'scoring_population_uniqueness' AS check_name,
    CASE
        WHEN COUNT(*) - COUNT(DISTINCT camis) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    COUNT(*) AS scoring_rows,
    COUNT(DISTINCT camis) AS unique_restaurants,
    COUNT(*) - COUNT(DISTINCT camis) AS duplicate_restaurants
FROM processed.scoring_population;
SELECT
    'scoring_date_consistency' AS check_name,
    CASE
        WHEN COUNT(DISTINCT cutoff_date) = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    MIN(cutoff_date) AS min_scoring_date,
    MAX(cutoff_date) AS max_scoring_date,
    COUNT(DISTINCT cutoff_date) AS distinct_scoring_dates
FROM processed.scoring_population;
SELECT
    'history_depth_distribution' AS check_name,
    history_depth_bucket,
    COUNT(*) AS feature_rows,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_feature_rows
FROM processed.features
GROUP BY history_depth_bucket
ORDER BY
    CASE history_depth_bucket
        WHEN '0' THEN 1
        WHEN '1' THEN 2
        WHEN '2-3' THEN 3
        WHEN '4+' THEN 4
    END;