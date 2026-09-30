# Restaurant Inspection Prioritization

A batch pipeline for prioritizing NYC restaurant inspections using a logistic regression model trained on historical DOHMH inspection records. The system produces a capacity-constrained inspection priority queue, ranks restaurants by their calibrated probability of a high-severity outcome at the next Cycle Inspection / Initial Inspection, and publishes artifacts to Amazon S3.

**[Live Demo](https://huggingface.co/spaces/souro26/restaurant-inspection-prioritization)**

---

## Problem

The NYC Department of Health and Mental Hygiene (DOHMH) conducts routine cycle inspections of restaurants. Inspection capacity is limited relative to the number of establishments, so inspectors cannot visit every restaurant at the same frequency. This project addresses the question: given a fixed inspection capacity, which restaurants should be prioritized for inspection next?

## Prediction Target

The model predicts the probability that the **next eligible Cycle Inspection / Initial Inspection** for a given restaurant will contain **three or more critical violations** (the project-defined high-severity threshold). This threshold is defined in `configs/target_policy.yaml` and is not an official DOHMH closure threshold or a statement about a restaurant's current condition.

The positive class (`target_high_severity = 1`) is assigned when the observed critical violation count at the target inspection is at or above three. The model does not predict whether a restaurant is safe or unsafe.

## Architecture

The production-oriented architecture is:

```
NYC Open Data (DOHMH CSV) --> Dockerized batch pipeline (ECS/Fargate)
    --> DuckDB (ephemeral, in-task SQL transformations)
    --> SQL validation checks
    --> Model scoring (logistic regression + Platt calibration)
    --> S3 artifacts (scores CSV, priority queue CSV, metadata JSON, monitoring JSON)
    --> CloudWatch custom metrics
```

For local development, the pipeline reads from a persistent DuckDB file on disk and writes artifacts to the local filesystem.

---

## Data

**Source:** [NYC DOHMH Restaurant Inspection Results](https://data.cityofnewyork.us/Health/DOHMH-New-York-City-Restaurant-Inspection-Results/43nn-pn8j) (dataset ID `43nn-pn8j`), downloaded as a bulk CSV from the NYC Open Data API.

**Inspection types used for model history and targets:**

| Role | Inspection type |
|---|---|
| Target event | Cycle Inspection / Initial Inspection |
| Historical features | Cycle Inspection / Initial Inspection, Cycle Inspection / Re-inspection |

All other inspection types are excluded from the primary model history and cannot appear as target events.

---

## Data Pipeline

The pipeline executes nine ordered SQL transformation scripts against a DuckDB database, followed by three validation scripts. Scripts are discovered and executed in lexicographic order.

### Transformations (`sql/transformations/`)

| Script | Purpose |
|---|---|
| `01_normalize_rows.sql` | Standardize raw column names and data types; map `critical_flag` values |
| `02_deduplicate_rows.sql` | Remove exact duplicate source rows; write deduplication audit counts |
| `03_build_restaurants.sql` | One row per restaurant (CAMIS), with latest known name, borough, cuisine |
| `04_build_inspection_events.sql` | Aggregate violation rows into one row per inspection event; compute critical violation counts and boolean flags |
| `05_build_violations.sql` | Retain individual violation records keyed by inspection |
| `06_build_prediction_population.sql` | Build retrospective decision snapshots: for each eligible historical inspection event, identify the next eligible target inspection strictly after the cutoff date |
| `07_build_labels.sql` | Attach observed target inspection outcomes to each snapshot; compute binary label (`target_high_severity`) |
| `08_build_features.sql` | Build point-in-time historical features for each retrospective snapshot; all historical lookups are bounded at `inspection_date <= cutoff_date` |
| `09_build_scoring_population.sql` | Build the current scoring population using all historical data up to the maximum inspection date in the database |

### Validation (`sql/validation/`)

Three validation scripts are executed after transformations. Each script contains multiple named checks that return `PASS`, `FAIL`, or `INFO` status. Hard failures (e.g., duplicate restaurant IDs, sentinel dates in the event table, orphaned violation records, future-dated features) are flagged as `FAIL`. Data quality thresholds are defined in `configs/data_quality.yaml`.

---

## Leakage Prevention

Point-in-time isolation is enforced at the SQL level. Features for a given snapshot are computed using only inspection events and violations with `inspection_date <= cutoff_date`. The target inspection is required to occur strictly after the cutoff date (`target_inspection_date > cutoff_date`). The validation layer includes explicit checks for future-dated feature sources and invalid target dates.

Temporal train/validation/test splits are enforced in code (`src/restaurant_risk/dataset/splits.py`) and are validated at construction time to ensure no boundary overlap.

---

## Temporal Splits

Training, validation, and test sets are defined by `cutoff_date` boundaries. Only snapshots from 2022 onward are included.

| Split | Cutoff date range |
|---|---|
| Train | 2022-01-01 to 2023-12-31 |
| Validation | 2024-01-01 to 2024-12-31 |
| Test | 2025-01-01 to 2025-12-31 |

---

## Features

Features are computed in SQL and consumed by the Python model pipeline. The full list is defined in `src/restaurant_risk/modeling/features.py`.

**Numeric features (18):**

| Feature | Description |
|---|---|
| `prior_cycle_inspection_count` | Total prior cycle inspections |
| `prior_cycle_initial_count` | Prior Cycle Initial inspections |
| `prior_cycle_reinspection_count` | Prior Cycle Re-inspections |
| `prior_high_severity_inspection_count` | Prior inspections with critical_violation_count >= 3 |
| `prior_high_severity_inspection_rate` | Rate of high-severity inspections over all cycle inspections |
| `prior_cycle_initial_high_severity_count` | High-severity Cycle Initial inspections |
| `prior_cycle_reinspection_high_severity_count` | High-severity Cycle Re-inspections |
| `high_severity_cycle_inspections_last_365d` | High-severity cycle inspections in the trailing 365 days |
| `prior_critical_violation_count` | Total critical violations across all prior cycle inspections |
| `prior_total_violations` | Total violation records across all prior cycle inspections |
| `prior_critical_violation_rows` | Prior violation records flagged as Critical |
| `violations_last_365d` | Violation records in the trailing 365 days |
| `critical_violations_last_365d` | Critical violation records in the trailing 365 days |
| `max_historical_score` | Maximum DOHMH numeric score across all prior inspections |
| `average_historical_score` | Mean DOHMH numeric score across all prior inspections |
| `average_score_last_365d` | Mean DOHMH numeric score in the trailing 365 days |
| `days_since_last_critical_inspection` | Days between the cutoff date and the most recent inspection with a critical violation |
| `days_since_last_high_severity_inspection` | Days between the cutoff date and the most recent high-severity inspection |

**Categorical features (3):** `borough`, `cuisine_description`, `history_depth_bucket`

The `history_depth_bucket` variable is a derived ordinal bucket based on `prior_cycle_initial_count`: `0`, `1`, `2-3`, `4+`.

---

## Model

**Algorithm:** Logistic regression (`sklearn.linear_model.LogisticRegression`, solver `lbfgs`, `C=1.0`, `max_iter=1000`).

**Preprocessing:**
- Numeric: median imputation with missing-value indicator, then `StandardScaler`
- Categorical: constant imputation (`"Missing"`), then one-hot encoding with `handle_unknown="ignore"`

**Calibration:** A Platt/sigmoid calibrator (`SigmoidCalibrator`) is trained on a held-out temporal calibration period. The calibrator learns a logistic mapping from the classifier's raw decision scores to observed outcomes. Both the fitted pipeline and calibrator are persisted to disk using `joblib`.

**Serialized artifacts** (checked into `models/`):
- `logistic_regression_C1.joblib`
- `logistic_regression_C1_sigmoid_calibrator.joblib`

---

## Scoring

The batch scoring pipeline (`src/restaurant_risk/score_restaurants.py`) applies the frozen model artifacts to the current scoring population. For each restaurant, it computes:

- `raw_logistic_probability`: uncalibrated probability from `model.predict_proba(X)[:, 1]`
- `calibrated_high_severity_probability`: Platt-calibrated probability from `SigmoidCalibrator.predict_positive_probability(...)`
- `priority_rank`: rank by descending calibrated probability (1 = highest risk)

The pipeline validates that the scoring feature schema exactly matches the frozen artifact's feature contract before scoring.

**Outputs:**
- `restaurant_risk_scores.csv`: full scored population
- `restaurant_priority_queue.csv`: top-`capacity` restaurants by calibrated probability

---

## Evaluation

Evaluation is implemented in `src/restaurant_risk/evaluation/`. The primary metrics are:

- `precision_at_k`: fraction of the top-`k` ranked restaurants that are positive (high-severity outcome)
- `recall_at_k`: fraction of all positive cases captured in the top `k`
- `lift_vs_random`: ratio of `precision_at_k` to the baseline prevalence under uniform random selection

Baselines include uniform random selection and a Laplace-smoothed historical risk score (`src/restaurant_risk/modeling/baselines.py`). Evaluation notebooks are in `notebooks/`. No specific metric values are reproduced here; see the notebooks for computed results.

---

## Repository Structure

```
.
├── configs/
│   ├── data_quality.yaml          # Hard failure and warning thresholds for validation
│   ├── project.yaml               # Source URL, paths, model filenames, storage config
│   └── target_policy.yaml         # Target event type and positive rule definition
├── infra/
│   └── aws/
│       └── setup_s3.ps1           # PowerShell script to provision S3 bucket (versioning, encryption, IAM policy)
├── models/
│   ├── logistic_regression_C1.joblib
│   └── logistic_regression_C1_sigmoid_calibrator.joblib
├── notebooks/
│   ├── 01_modeling_dataset_eda.ipynb
│   ├── 02_baseline_policy_evaluation.ipynb
│   ├── 03_logistic_regression_validation.ipynb
│   └── 04_error_analysis_and_policy_evaluation.ipynb
├── sql/
│   ├── transformations/           # 01-09: ordered DuckDB SQL transformation scripts
│   └── validation/                # 01-03: data quality and leakage validation checks
├── src/restaurant_risk/
│   ├── api/                       # FastAPI application (health, model-info, scoring-status, priority-queue)
│   ├── config.py                  # ProjectConfig dataclass; environment variable overrides
│   ├── dataset/                   # Data loading and temporal split construction
│   ├── evaluation/                # Precision@k, recall@k, lift metrics and top-k selection
│   ├── exceptions.py              # PipelineError, TransformationError, ValidationError
│   ├── modeling/                  # Logistic regression, Platt calibration, feature definitions, baselines
│   ├── monitoring/                # Batch metrics (build_batch_metrics, publish_cloudwatch_metrics)
│   ├── pipeline/                  # run_batch.py (main entrypoint), run_data_pipeline.py, metadata
│   ├── score_restaurants.py       # Scoring and priority queue construction
│   └── storage/                   # LocalArtifactStore, S3ArtifactStore, create_artifact_store
├── tests/                         # pytest test suite (11 test files)
├── batch-task-def-v6.json         # ECS Fargate task definition (batch pipeline)
├── Dockerfile                     # Single image; CMD runs uvicorn (API); batch invoked via command override
├── pyproject.toml
└── .github/workflows/ci.yml       # CI: ruff lint + pytest + docker build
```

---

## Running Locally

**Requirements:** Python 3.12, a populated DuckDB database at `data/restaurant_risk.duckdb`.

Install the package:

```bash
pip install -e ".[test]"
```

Set the project root (optional; defaults to the repository root):

```bash
# Windows
set RESTAURANT_RISK_PROJECT_ROOT=C:\path\to\repository
# Linux/macOS
export RESTAURANT_RISK_PROJECT_ROOT=/path/to/repository
```

Run the data pipeline (transformations + validation against the local database):

```bash
python -m restaurant_risk.pipeline.run_data_pipeline
```

Score the current population and generate a priority queue of 100 restaurants:

```bash
python -m restaurant_risk.score_restaurants --capacity 100
```

Run the complete batch pipeline (data pipeline + scoring + artifact persistence):

```bash
python -m restaurant_risk.pipeline.run_batch --capacity 100
```

Run the API server:

```bash
uvicorn restaurant_risk.api.app:app --host 0.0.0.0 --port 8000
```

Run tests:

```bash
pytest
```

---

## Docker

The Dockerfile produces a single image based on `python:3.12-slim`. It copies `src/`, `configs/`, `models/`, and `sql/` into `/app` and installs all dependencies.

The default `CMD` starts the FastAPI API server via `uvicorn`. The batch pipeline is invoked by overriding the command in the ECS task definition.

Build:

```bash
docker build -t restaurant-risk-api .
```

Run the API:

```bash
docker run -p 8000:8000 restaurant-risk-api
```

Run the batch pipeline via command override:

```bash
docker run \
  -e RESTAURANT_RISK_STORAGE_PROVIDER=local \
  restaurant-risk-api \
  python -m restaurant_risk.pipeline.run_batch --capacity 100
```

---

## AWS Deployment

The project is deployed to AWS in the `ap-south-1` region. Infrastructure is provisioned manually; there is no IaC (Terraform/CloudFormation) in this repository.

### S3

A single S3 bucket (`restaurant-risk-269626332583`) stores batch artifacts. The bucket is configured with:
- Block all public access
- Server-side encryption (SSE-S3 / AES-256)
- Versioning enabled

Artifact layout under the configured S3 prefix (`restaurant-risk/`):

```
predictions/<run_id>/restaurant_risk_scores.csv
queues/<run_id>/restaurant_priority_queue.csv
runs/<run_id>/run_metadata.json
runs/<run_id>/batch_metadata.json
runs/<run_id>/monitoring_metrics.json
runs/<run_id>/pipeline.log
models/production/<model_filename>
models/production/<calibrator_filename>
raw/<run_id>/dohmh_inspections.csv
```

The S3 bucket and IAM group policy are provisioned by `infra/aws/setup_s3.ps1`.

### ECS / Fargate

The batch pipeline runs as an ECS Fargate task (`restaurant-risk-batch` family). The active task definition is `batch-task-def-v6.json`:

- Image: `269626332583.dkr.ecr.ap-south-1.amazonaws.com/restaurant-risk-api:v5`
- CPU: 1024 units (1 vCPU), Memory: 2048 MB
- Command: `python -m restaurant_risk.pipeline.run_batch --capacity 100`
- Environment variables: `AWS_REGION`, `RESTAURANT_RISK_S3_BUCKET`, `RESTAURANT_RISK_S3_PREFIX`, `RESTAURANT_RISK_STORAGE_PROVIDER`
- Logs: CloudWatch Logs, log group `restaurant-risk-batch`
- IAM task role: `restaurant-risk-batch-task-role`

In S3 mode, the batch pipeline downloads the source CSV fresh each run, builds an ephemeral DuckDB database in a temporary directory, runs transformations and validations, scores the population, writes artifacts locally, and then uploads them all to S3. The temporary directory is deleted automatically after the task completes.

There is no automated scheduling in this repository. Task invocation is performed manually (e.g., via the ECS console or AWS CLI).

### API (Fargate)

The API container has been deployed and started on Fargate. Public external HTTP reachability has not been established as a permanent production endpoint; no load balancer or public DNS record is configured in this repository.

---

## Configuration

Configuration is loaded from `configs/project.yaml`. Storage-related settings can be overridden at runtime via environment variables without modifying the YAML file:

| Environment variable | Purpose | Default (YAML) |
|---|---|---|
| `RESTAURANT_RISK_PROJECT_ROOT` | Absolute path to the project root | Inferred from package path |
| `RESTAURANT_RISK_STORAGE_PROVIDER` | `local` or `s3` | `local` |
| `RESTAURANT_RISK_S3_BUCKET` | S3 bucket name | `""` |
| `RESTAURANT_RISK_S3_PREFIX` | S3 key prefix | `restaurant-risk` |
| `AWS_REGION` | AWS region for S3 and CloudWatch | `ap-south-1` |

---

## Monitoring

After each batch run, the pipeline writes `monitoring_metrics.json` to the run directory (and uploads it to S3 on a successful S3 run).

Metrics captured per run:

| Field | Description |
|---|---|
| `run_id` | UTC timestamp string identifying the run |
| `status` | `SUCCESS` or `FAILED` |
| `capacity` | Requested priority queue capacity |
| `population_size` | Total restaurants in the scoring population |
| `priority_queue_size` | Restaurants in the output queue |
| `duration_seconds` | Total pipeline wall-clock duration |
| `prediction_count` | Rows in the scores CSV |
| `prediction_mean/min/max/median` | Distribution of `calibrated_high_severity_probability` |
| `high_risk_rate_0_50` | Fraction of scored restaurants with calibrated probability >= 0.50 |
| `high_risk_rate_0_75` | Fraction of scored restaurants with calibrated probability >= 0.75 |
| `unique_restaurants` | Distinct CAMIS values in the scores CSV |
| `top_rank_probability` | Calibrated probability of the rank-1 restaurant |
| `history_depth_distribution` | Proportion of each `history_depth_bucket` value in the scored population |

On S3 runs, numeric metrics are also published to CloudWatch in the `RestaurantRisk` namespace with the `Environment: production` dimension. CloudWatch publishing failures are logged but do not cause the pipeline to fail.

---

## API

The FastAPI application (`src/restaurant_risk/api/`) exposes four endpoints. It reads the frozen model artifacts and the scoring population from the local DuckDB database. The API does not run the data pipeline; it serves whatever scoring population is already present in the database.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` |
| `GET` | `/model-info` | Returns model filename, calibrator filename, and feature count |
| `GET` | `/scoring-status` | Returns population size and whether a scoring output file exists |
| `POST` | `/priority-queue` | Accepts `{"capacity": N}` and returns the top-N restaurants by calibrated probability |

The `/priority-queue` response includes, for each restaurant: `camis`, `restaurant_name`, `borough`, `cuisine_description`, `cutoff_date`, `history_depth_bucket`, `raw_logistic_probability`, `calibrated_high_severity_probability`, and `priority_rank`.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

1. **Lint**: `ruff check src tests`
2. **Test**: `pytest` (full test suite, 11 test files)
3. **Docker build**: `docker build -t restaurant-risk-api .`

There is no automated image push to ECR or deployment step in the CI workflow. Image publishing and task registration are performed manually.

---

## Reproducibility

- Random seed: `42` (set in `configs/project.yaml`; passed to `LogisticRegression`)
- Python version: 3.12 (pinned in `pyproject.toml` and CI)
- All dependencies are pinned to exact versions in `pyproject.toml`
- Model artifacts are committed to `models/` and loaded at scoring and inference time

---

## Limitations

- The model is a logistic regression trained on a single temporal cohort. No automated retraining or model promotion is implemented.
- The scoring population includes all restaurants with at least one eligible historical cycle inspection event, regardless of how old that history is. Restaurants with no prior Cycle Initial inspections receive a `history_depth_bucket` of `"0"` and are scored with limited feature signal.
- Feature engineering is computed entirely in DuckDB SQL on each batch run. There is no feature store or cached computation.
- The batch pipeline has no automated trigger. It must be invoked manually (e.g., via the ECS console or AWS CLI).
- Data quality validation checks emit `PASS`/`FAIL`/`INFO` status but do not halt the pipeline on `FAIL`; threshold enforcement is the responsibility of the caller.
- The API reads the local DuckDB database and does not pull fresh data from S3 or re-run the pipeline. In cloud deployments, the API and batch pipeline share no persistent storage.

---

## License

MIT. See `LICENSE`.

