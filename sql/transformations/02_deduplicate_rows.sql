-- 02_deduplicate_rows.sql
-- Purpose:
--     Remove exact duplicate normalized source records.

CREATE OR REPLACE TABLE processed.deduplicated_inspection_rows AS
SELECT DISTINCT *
FROM processed.normalized_inspection_rows;