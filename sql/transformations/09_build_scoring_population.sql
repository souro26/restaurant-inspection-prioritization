-- 09_build_scoring_population.sql
-- Purpose:
--     Build the current restaurant population to be scored.

CREATE OR REPLACE TABLE processed.scoring_population AS
WITH latest_cycle_inspection AS (
    SELECT
        camis,
        MAX(inspection_date) AS cutoff_date
    FROM processed.inspections
    WHERE inspection_type LIKE 'Cycle Inspection /%'
    GROUP BY camis
)
SELECT
    r.camis,
    r.restaurant_name,
    r.borough,
    r.building,
    r.street,
    r.zipcode,
    r.phone,
    r.cuisine_description,
    r.latitude,
    r.longitude,
    r.community_board,
    r.council_district,
    r.census_tract,
    r.bin,
    r.bbl,
    r.nta,

    l.cutoff_date AS latest_cycle_inspection
FROM processed.restaurants r
JOIN latest_cycle_inspection l
    ON l.camis = r.camis;