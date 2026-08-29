-- run_pipeline.sql
-- Purpose:
--     Execute the complete SQL transformation pipeline in dependency order.

.read sql/transformations/01_normalize_rows.sql
.read sql/transformations/02_deduplicate_rows.sql
.read sql/transformations/03_build_restaurants.sql
.read sql/transformations/04_build_inspection_events.sql
.read sql/transformations/05_build_violations.sql
.read sql/transformations/06_build_prediction_population.sql
.read sql/transformations/07_build_labels.sql
.read sql/transformations/08_build_features.sql
.read sql/transformations/09_build_scoring_population.sql