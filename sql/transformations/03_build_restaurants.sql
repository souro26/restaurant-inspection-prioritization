-- 03_build_restaurants.sql
-- Purpose:
--     Build the restaurant-level table `processed.restaurants`.
--     One row represents one unique restaurant identified by CAMIS.

CREATE OR REPLACE TABLE processed.restaurants AS
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
    location
FROM processed.deduplicated_inspection_rows
GROUP BY
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
    location;