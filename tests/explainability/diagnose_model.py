"""
Diagnose model features and predictions.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parents[2]
predictor_path = project_root / "data_analysis" / "predictor"
sys.path.insert(0, str(predictor_path))

from predictor import build_global_curve


def main():
    model_path = project_root / "data_analysis" / "predictor" / "residual_model.joblib"
    processed_root = project_root / "data_analysis" / "data" / "processed"

    print("Loading model...")
    model = joblib.load(model_path)

    print(f"\nModel type: {type(model)}")
    print(f"Model params: {model.get_params()}")

    # Check feature names
    if hasattr(model, 'feature_names_in_'):
        print(f"\nExpected features ({len(model.feature_names_in_)}):")
        for i, name in enumerate(model.feature_names_in_):
            print(f"  {i+1}. {name}")
    else:
        print("\nModel has no feature_names_in_ attribute")

    # Check feature importances
    if hasattr(model, 'feature_importances_'):
        print(f"\nFeature importances:")
        if hasattr(model, 'feature_names_in_'):
            for name, imp in zip(model.feature_names_in_, model.feature_importances_):
                print(f"  {name}: {imp:.4f}")
        else:
            for i, imp in enumerate(model.feature_importances_):
                print(f"  Feature {i}: {imp:.4f}")

    # Test prediction with sample features
    print("\n" + "="*60)
    print("Testing predictions with varying distance...")
    print("="*60)

    global_curve = build_global_curve(processed_root)

    # Test at 10% grade with varying distance
    grade = 10.0
    baseline_ratio = np.interp(grade, global_curve["grade"], global_curve["median"])

    test_distances = [0, 5, 10, 20, 30, 40]

    for dist_km in test_distances:
        # Try to match the feature names from training
        features = pd.DataFrame([{
            "grade_mean": grade,
            "grade_std": 0.0,
            "abs_grade": abs(grade),
            "cumulative_distance_km": dist_km,
            "prev_pace_ratio": 1.0,
            "grade_change": 0.0,
            "cum_elevation_gain_m": dist_km * 1000 * grade / 100.0,
            "elevation_gain_rate": (dist_km * 1000 * grade / 100.0) / max(dist_km, 0.1),
            "rolling_avg_grade_500m": grade,
            "distance_remaining_km": 40 - dist_km,
        }])

        print(f"\nDistance: {dist_km} km")
        print(f"  Features: {features.iloc[0].to_dict()}")

        try:
            pred = model.predict(features)[0]
            print(f"  Predicted residual multiplier: {pred:.4f}")
            print(f"  Baseline ratio: {baseline_ratio:.4f}")
            print(f"  Final ratio: {baseline_ratio * pred:.4f}")
        except Exception as e:
            print(f"  Error: {e}")

    # Check if model has any training
    print("\n" + "="*60)
    print("Model summary:")
    print("="*60)
    if hasattr(model, 'estimators_'):
        print(f"Number of estimators: {len(model.estimators_)}")
    if hasattr(model, 'n_features_in_'):
        print(f"Number of features: {model.n_features_in_}")
    if hasattr(model, 'train_score_'):
        print(f"Training scores: {model.train_score_}")


if __name__ == "__main__":
    main()
