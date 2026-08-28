-- 06_build_prediction_population.sql
-- Purpose: Build retrospective restaurant decision snapshots.

CREATE OR REPLACE TABLE processed.prediction_population AS
WITH cutoffs AS (
    SELECT
        inspection_id AS cutoff_inspection_id,
        camis,
        inspection_date AS cutoff_date,
        inspection_type AS cutoff_inspection_type,

        is_cycle_initial AS cutoff_is_cycle_initial,
        is_cycle_reinspection AS cutoff_is_cycle_reinspection
    FROM processed.inspections
    WHERE is_eligible_historical_event = TRUE
),
future_target_candidates AS (
    SELECT
        c.cutoff_inspection_id,
        c.camis,
        c.cutoff_date,
        c.cutoff_inspection_type,
        c.cutoff_is_cycle_initial,
        c.cutoff_is_cycle_reinspection,

        t.inspection_id AS target_inspection_id,
        t.inspection_date AS target_inspection_date,
        t.inspection_type AS target_inspection_type,

        ROW_NUMBER() OVER (
            PARTITION BY c.cutoff_inspection_id
            ORDER BY
                t.inspection_date,
                t.inspection_id
        ) AS target_rank
    FROM cutoffs c
    JOIN processed.inspections t
      ON t.camis = c.camis
     AND t.inspection_date > c.cutoff_date
     AND t.is_eligible_target_event = TRUE
)
SELECT
    cutoff_inspection_id,
    camis,
    cutoff_date,
    cutoff_inspection_type,
    cutoff_is_cycle_initial,
    cutoff_is_cycle_reinspection,

    target_inspection_id,
    target_inspection_date,
    target_inspection_type,

    DATE_DIFF(
        'day',
        cutoff_date,
        target_inspection_date
    ) AS days_to_target
FROM future_target_candidates
WHERE target_rank = 1;