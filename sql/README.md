# SQL Pipeline

The SQL layer transforms the raw restaurant inspection data into validated analytical tables used for modeling and scoring.

## Execution order

```text
01 normalize
02 deduplicate
03 restaurants
04 inspections
05 violations
06 prediction population
07 labels
08 features
09 scoring population