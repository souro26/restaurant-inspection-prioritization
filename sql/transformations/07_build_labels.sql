-- 07_build_labels.sql
-- Purpose:
--     Build the supervised learning target for each prediction example.

CREATE OR REPLACE TABLE processed.labels AS

SELECT
    p.camis,
    p.cutoff_date,
    p.target_inspection_date,
    p.target_inspection_type,
    i.has_critical_violation AS target_critical

FROM processed.prediction_population p

JOIN processed.inspections i
    ON i.camis = p.camis
   AND i.inspection_date = p.target_inspection_date
   AND i.inspection_type = p.target_inspection_type;