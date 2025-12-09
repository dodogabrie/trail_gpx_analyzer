"""
Train the residual correction model on existing processed data.

This script:
1) Builds the global grade→pace ratio curve across all athletes.
2) Builds a segment-level training set (default 200 m segments).
3) Trains a Gradient Boosting model to predict residual multipliers.
4) Saves the model to data_analysis/predictor/residual_model.joblib.

Run inside your venv:
    source data_analysis/venv/bin/activate
    python data_analysis/predictor/train.py
"""

from pathlib import Path

import joblib

from predictor import build_global_curve
from ml_residual import build_training_dataset, train_residual_model


def main():
    project_root = Path(__file__).resolve().parents[2]
    processed_root = project_root / "data_analysis" / "data" / "processed"
    model_path = project_root / "data_analysis" / "predictor" / "residual_model.joblib"

    print(f"Building global curve from {processed_root}...")
    global_curve = build_global_curve(processed_root)

    print("Building training dataset (200 m segments)...")
    train_df = build_training_dataset(processed_root, global_curve, segment_len_m=200)
    print(f"Training rows: {len(train_df)}")

    print("Training Gradient Boosting model...")
    model = train_residual_model(train_df)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Saved model to {model_path}")


if __name__ == "__main__":
    main()
