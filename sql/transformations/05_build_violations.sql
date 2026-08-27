-- 05_build_violations.sql
-- Purpose:
--     Build the violation-level table.

CREATE OR REPLACE TABLE processed.violations AS
SELECT
    camis,
    inspection_date,
    inspection_type,
    violation_code,
    violation_description,
    critical_flag
FROM processed.deduplicated_inspection_rows
WHERE camis IS NOT NULL
  AND inspection_date IS NOT NULL
  AND inspection_date <> DATE '1900-01-01'
  AND violation_code IS NOT NULL;