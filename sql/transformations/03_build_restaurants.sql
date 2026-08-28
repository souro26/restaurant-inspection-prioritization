-- 03_build_restaurants.sql
-- Purpose:
--     Build the restaurant-level dimension table.

CREATE OR REPLACE TABLE processed.restaurants AS
WITH ranked_restaurant_rows AS (
    SELECT
        camis,
        restaurant_name,
        borough,
        building,
        street,
        zipcode,
        phone,
        cuisine_description,
        latitude,
        longitude,
        community_board,
        council_district,
        census_tract,
        bin,
        bbl,
        nta,
        location,
        inspection_date,
        record_date,
        raw_row_hash,

        ROW_NUMBER() OVER (
            PARTITION BY camis
            ORDER BY
                inspection_date DESC NULLS LAST,
                record_date DESC NULLS LAST,
                raw_row_hash
        ) AS row_rank
    FROM processed.deduplicated_inspection_rows
    WHERE camis IS NOT NULL
)
SELECT
    camis,
    restaurant_name,
    borough,
    building,
    street,
    zipcode,
    phone,
    cuisine_description,
    latitude,
    longitude,
    community_board,
    council_district,
    census_tract,
    bin,
    bbl,
    nta,
    location,
    inspection_date AS latest_observed_inspection_date,
    record_date AS latest_observed_record_date
FROM ranked_restaurant_rows
WHERE row_rank = 1;