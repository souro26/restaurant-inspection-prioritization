from pathlib import Path

import joblib
import pandas as pd

from restaurant_risk.dataset.load import load_modeling_dataset
from restaurant_risk.modeling.features import get_feature_matrix

def main():
    project_root = Path(__file__).resolve().parent.parent
    database_path = project_root / "data" / "restaurant_risk.duckdb"
    model_path = project_root / "models" / "logistic_regression_C1.joblib"
    output_path = project_root / "output" / "restaurant_risk_scores.csv"

    output_path.parent.mkdir(exist_ok=True)
    df = load_modeling_dataset(database_path)
    model = joblib.load(model_path)
    X = get_feature_matrix(df)
    scores = model.predict_proba(X)[:, 1]

    scored = df[["camis", "cutoff_date"]].copy()
    scored["logistic_risk_score"] = scores

    scored.to_csv(output_path, index=False)

    print("Scored rows:", len(scored))
    print("Output written to:", output_path)

if __name__ == "__main__":
    main()