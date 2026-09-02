SELECT
    'duplicate_prediction_cutoff' AS check_name,
    cutoff_inspection_id,
    COUNT(*) AS row_count
FROM processed.prediction_population
GROUP BY cutoff_inspection_id
HAVING COUNT(*) > 1;
SELECT
    'target_not_after_cutoff' AS check_name,
    *
FROM processed.prediction_population
WHERE target_inspection_date <= cutoff_date;
SELECT
    'invalid_target_event_type' AS check_name,
    p.*
FROM processed.prediction_population p
LEFT JOIN processed.inspections i
    ON i.inspection_id = p.target_inspection_id
WHERE i.inspection_id IS NULL
   OR i.is_eligible_target_event <> TRUE;
SELECT
    'invalid_cutoff_event_type' AS check_name,
    p.*
FROM processed.prediction_population p
LEFT JOIN processed.inspections i
    ON i.inspection_id = p.cutoff_inspection_id
WHERE i.inspection_id IS NULL
   OR i.is_eligible_historical_event <> TRUE;
SELECT
    'prediction_label_count_match' AS check_name,
    CASE
        WHEN prediction_rows = label_rows THEN 'PASS'
        ELSE 'FAIL'
    END AS status,
    prediction_rows,
    label_rows,
    prediction_rows - label_rows AS difference
FROM (
    SELECT
        (
            SELECT COUNT(*)
            FROM processed.prediction_population
        ) AS prediction_rows,
        (
            SELECT COUNT(*)
            FROM processed.labels
        ) AS label_rows
);
SELECT
    'duplicate_label' AS check_name,
    cutoff_inspection_id,
    COUNT(*) AS label_count
FROM processed.labels
GROUP BY cutoff_inspection_id
HAVING COUNT(*) > 1;
SELECT
    'label_target_not_after_cutoff' AS check_name,
    *
FROM processed.labels
WHERE target_inspection_date <= cutoff_date;
SELECT
    'target_equals_cutoff' AS check_name,
    *
FROM processed.labels
WHERE target_inspection_id = cutoff_inspection_id;
SELECT
    'invalid_target_label' AS check_name,
    *
FROM processed.labels
WHERE target_high_severity NOT IN (0, 1)
   OR target_high_severity IS NULL;
SELECT
    'non_positive_days_to_target' AS check_name,
    *
FROM processed.labels
WHERE days_to_target <= 0
   OR days_to_target IS NULL;
SELECT
    'target_summary' AS check_name,
    COUNT(*) AS labeled_rows,
    SUM(target_high_severity) AS critical_targets,
    ROUND(100.0 * AVG(target_high_severity), 2)
        AS critical_target_rate_pct,
    MIN(days_to_target) AS min_days_to_target,
    ROUND(AVG(days_to_target), 1) AS avg_days_to_target,
    MEDIAN(days_to_target) AS median_days_to_target,
    MAX(days_to_target) AS max_days_to_target
FROM processed.labels;
SELECT
    'cutoff_event_composition' AS check_name,
    cutoff_inspection_type,
    COUNT(*) AS prediction_rows,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_prediction_rows,
    ROUND(AVG(days_to_target), 1) AS avg_days_to_target
FROM processed.prediction_population
GROUP BY cutoff_inspection_type
ORDER BY prediction_rows DESC;