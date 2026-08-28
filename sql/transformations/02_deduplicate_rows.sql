-- 02_deduplicate_rows.sql
-- Purpose:
--     Remove exact duplicate normalized source rows.

CREATE OR REPLACE TABLE processed.deduplicated_inspection_rows AS
SELECT DISTINCT * FROM processed.normalized_inspection_rows;

CREATE OR REPLACE TABLE processed.deduplication_audit AS
SELECT
    (
        SELECT COUNT(*)
        FROM processed.normalized_inspection_rows
    ) AS input_row_count,
    (
        SELECT COUNT(*)
        FROM processed.deduplicated_inspection_rows
    ) AS output_row_count,
    (
        SELECT COUNT(*)
        FROM processed.normalized_inspection_rows
    ) - (
        SELECT COUNT(*)
        FROM processed.deduplicated_inspection_rows
    ) AS exact_duplicates_removed;