import sys
import os
import joblib
import pandas as pd
import numpy as np

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import UserLearnedParams, UserResidualModel, UserActivityResidual

app = create_app()

def inspect_user(user_id):
    with app.app_context():
        print(f"\n=== INSPECTING USER {user_id} ===")
        
        # 1. Learned Parameters (Tier 2)
        params = UserLearnedParams.query.filter_by(user_id=user_id).first()
        if params:
            print("\n[Tier 2] Learned Parameters:")
            print(f"  v_flat: {params.v_flat:.4f} m/s ({1000/params.v_flat/60:.2f} min/km)")
            print(f"  k_up:   {params.k_up:.4f}")
            print(f"  k_tech: {params.k_tech:.4f}")
            print(f"  a_param: {params.a_param:.4f}")
            print(f"  k_terrain_up: {params.k_terrain_up:.4f}")
            print(f"  k_terrain_down: {params.k_terrain_down:.4f}")
            
            # Check continuity at g=0
            # Uphill limit (g->0+): v = v_flat / (k_up * k_terrain_up)
            v_up_lim = params.v_flat / (params.k_up * params.k_terrain_up)
            pace_up_lim = (1000 / v_up_lim) / 60
            
            # Downhill limit (g->0-): v = v_flat * k_tech / k_terrain_down
            v_down_lim = params.v_flat * params.k_tech / params.k_terrain_down
            pace_down_lim = (1000 / v_down_lim) / 60
            
            print(f"\n[Continuity Check at 0% Grade]")
            print(f"  Uphill side (g=+0%): {pace_up_lim:.2f} min/km")
            print(f"  Downhill side (g=-0%): {pace_down_lim:.2f} min/km")
            print(f"  Gap: {abs(pace_up_lim - pace_down_lim):.2f} min/km")
        else:
            print("\n[Tier 2] No learned parameters found.")

        # 2. ML Model (Tier 3)
        ml_model = UserResidualModel.query.filter_by(user_id=user_id).first()
        if ml_model:
            print("\n[Tier 3] ML Model:")
            print(f"  Activities used: {ml_model.n_activities_used}")
            print(f"  Segments trained: {ml_model.n_segments_trained}")
            print(f"  Residual Variance (std): {ml_model.residual_variance:.4f}")
            print(f"  Metrics: {ml_model.metrics}")
            
            # Load model and test simple predictions
            try:
                model = joblib.load(pd.io.common.BytesIO(ml_model.model_blob))
                print("\n  Test Predictions (Residual Multipliers):")
                
                # Test cases
                test_grades = [-0.30, -0.10, -0.01, 0.00, 0.01, 0.10, 0.30]
                features = []
                for g in test_grades:
                    features.append({
                        'grade_mean': g,
                        'grade_std': 0.0,
                        'abs_grade': abs(g),
                        'cum_distance_km': 5.0,
                        'distance_remaining_km': 10.0,
                        'prev_pace_ratio': 1.0,
                        'grade_change': 0.0,
                        'cum_elevation_gain_m': 100.0,
                        'elevation_gain_rate': max(0, g * 1000 / 0.2) * 0.2, # Scaled correctly? No, rate is per km usually?
                        # In service: elevation_gain_rate = elevation_gain / (length_m / 1000)
                        # gain = g * 200. rate = g * 200 / 0.2 = g * 1000.
                        'rolling_avg_grade_500m': g
                    })
                
                # We need to construct DataFrame with correct columns
                from services.residual_ml_service import FEATURES
                df_test = pd.DataFrame(features)
                # Ensure all features exist
                for f in FEATURES:
                    if f not in df_test.columns:
                        df_test[f] = 0.0
                
                preds = model.predict(df_test[FEATURES])
                
                for g, p in zip(test_grades, preds):
                    print(f"    Grade {g:>5.0%}: {p:.4f}x")
                    
            except Exception as e:
                print(f"  Error loading/testing model: {e}")
                
        else:
            print("\n[Tier 3] No ML model found.")
            
        # 3. Residual Data Stats
        count = UserActivityResidual.query.filter_by(user_id=user_id).count()
        print(f"\n[Data] Total Activity Residuals: {count}")

if __name__ == "__main__":
    inspect_user(2)
