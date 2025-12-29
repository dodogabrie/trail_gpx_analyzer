#!/usr/bin/env python3
"""Test script for Tier 3 ML residual model.

Tests the GBM training and prediction on user's residuals.

Usage:
    python scripts/test_tier3_ml.py [--user-id USER_ID]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import User, UserActivityResidual, UserResidualModel
from services.residual_ml_service import ResidualMLService
from services.hybrid_prediction_service import HybridPredictionService
import argparse


def test_tier3_ml(user_id=None):
    """Test Tier 3 ML model training.

    Args:
        user_id: Specific user ID to test (default: first user)
    """
    app = create_app()

    with app.app_context():
        # Get user
        if user_id:
            user = User.query.get(user_id)
        else:
            user = User.query.first()

        if not user:
            print("❌ No user found in database")
            return

        print(f"Testing Tier 3 ML Residual Model")
        print(f"User: {user.email} (ID: {user.id})")
        print("=" * 60)

        # Check tier status
        hybrid_service = HybridPredictionService()
        tier_status = hybrid_service.get_user_tier_status(user.id)

        print(f"\nTier Status:")
        print(f"  Current tier: {tier_status['current_tier']}")
        print(f"  Activity count: {tier_status['activity_count']}")
        print(f"  Confidence: {tier_status['confidence_level']}")

        # Check if eligible for Tier 3
        ml_service = ResidualMLService()

        if not ml_service.should_train(user.id):
            print(f"\n❌ User has insufficient data for Tier 3")
            print(f"   Need at least 15 activities with residuals")
            print(f"   Current: {tier_status['activity_count']}")
            print(f"\nRun: python scripts/test_residual_collection.py --limit 20")
            print(f"     to collect more residuals first")
            return

        print(f"\n✓ User eligible for Tier 3 ML training\n")

        # Check if already trained
        existing = UserResidualModel.query.filter_by(user_id=user.id).first()
        if existing:
            print(f"Existing ML model:")
            print(f"  Activities used: {existing.n_activities_used}")
            print(f"  Segments trained: {existing.n_segments_trained}")
            print(f"  Validation MAE: {existing.metrics.get('val_mae', 'N/A'):.4f}")
            print(f"  Validation R²: {existing.metrics.get('val_r2', 'N/A'):.3f}")
            print(f"  Confidence: {existing.confidence_level}")
            print(f"  Last trained: {existing.last_trained}\n")

            print(f"Feature Importance:")
            if existing.feature_importance:
                sorted_features = sorted(
                    existing.feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                for feature, importance in sorted_features:
                    print(f"    {feature:25s}: {importance:.3f}")

            print()
            response = input("Retrain model? (y/n): ")
            if response.lower() != 'y':
                print("Skipping retraining")
                return
            print()

        # Train GBM model
        print("Training GBM model...")
        print("-" * 60)

        trained_model = ml_service.train_user_model(user.id)

        if not trained_model:
            print("❌ Model training failed")
            return

        print(f"\n✓ Training complete!\n")

        print(f"Model Statistics:")
        print(f"  Activities used: {trained_model.n_activities_used}")
        print(f"  Segments trained: {trained_model.n_segments_trained}")

        print(f"\nPerformance Metrics:")
        metrics = trained_model.metrics
        print(f"  Training MAE: {metrics['train_mae']:.4f}")
        print(f"  Validation MAE: {metrics['val_mae']:.4f}")
        print(f"  Training RMSE: {metrics['train_rmse']:.4f}")
        print(f"  Validation RMSE: {metrics['val_rmse']:.4f}")
        print(f"  Training R²: {metrics['train_r2']:.3f}")
        print(f"  Validation R²: {metrics['val_r2']:.3f}")

        print(f"\nFeature Importance:")
        sorted_features = sorted(
            trained_model.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for i, (feature, importance) in enumerate(sorted_features, 1):
            bar = '█' * int(importance * 50)
            print(f"  {i:2d}. {feature:25s}: {importance:.3f} {bar}")

        print(f"\nModel Configuration:")
        for key, value in trained_model.model_config.items():
            print(f"  {key}: {value}")

        # Update tier status
        tier_status = hybrid_service.get_user_tier_status(user.id)
        print(f"\nUpdated Tier Status:")
        print(f"  Current tier: {tier_status['current_tier']}")
        print(f"  Confidence: {tier_status['confidence_level']}")

        print(f"\n✓ Tier 3 ML model training successful!")
        print(f"\nNext steps:")
        print(f"  1. Use /api/hybrid/predict to get Tier 3 predictions with ML corrections")
        print(f"  2. Compare predictions with Tier 2 to see ML improvements")
        print(f"  3. Add more activities to improve model accuracy")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test Tier 3 ML model')
    parser.add_argument('--user-id', type=int, help='User ID to test')

    args = parser.parse_args()

    test_tier3_ml(user_id=args.user_id)
