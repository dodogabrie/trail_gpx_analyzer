#!/usr/bin/env python3
"""Test script for Tier 2 parameter learning.

Tests the parameter learning service by training on user's residuals
and comparing predictions with different tiers.

Usage:
    python scripts/test_tier2_learning.py [--user-id USER_ID]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from database import db
from models import User, UserActivityResidual, UserLearnedParams
from services.parameter_learning_service import ParameterLearningService
from services.hybrid_prediction_service import HybridPredictionService
import argparse


def test_parameter_learning(user_id=None):
    """Test parameter learning on user's residuals.

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

        print(f"Testing Tier 2 Parameter Learning")
        print(f"User: {user.email} (ID: {user.id})")
        print("=" * 60)

        # Check tier status
        hybrid_service = HybridPredictionService()
        tier_status = hybrid_service.get_user_tier_status(user.id)

        print(f"\nTier Status:")
        print(f"  Current tier: {tier_status['current_tier']}")
        print(f"  Activity count: {tier_status['activity_count']}")
        print(f"  Confidence: {tier_status['confidence_level']}")

        if tier_status['next_tier']:
            print(f"  Progress to {tier_status['next_tier']}: {tier_status['progress_to_next_tier_pct']:.1f}%")
            print(f"  Activities needed: {tier_status['activities_needed_for_next_tier']}")

        # Check if eligible for Tier 2
        parameter_service = ParameterLearningService()

        if not parameter_service.should_train(user.id):
            print(f"\n❌ User has insufficient data for Tier 2")
            print(f"   Need at least 5 activities with residuals")
            print(f"\nRun: python scripts/test_residual_collection.py --limit 10")
            print(f"     to collect residuals from activities first")
            return

        print(f"\n✓ User eligible for Tier 2 parameter learning\n")

        # Check if already trained
        existing = UserLearnedParams.query.filter_by(user_id=user.id).first()
        if existing:
            print(f"Existing learned parameters:")
            print(f"  v_flat: {existing.v_flat:.3f} m/s ({(1000/existing.v_flat)/60:.2f} min/km)")
            print(f"  k_up: {existing.k_up:.3f}")
            print(f"  k_tech: {existing.k_tech:.3f}")
            print(f"  fatigue_alpha: {existing.fatigue_alpha:.3f}")
            print(f"  Optimization score (MAE): {existing.optimization_score:.4f}")
            print(f"  Activities used: {existing.n_activities_used}")
            print(f"  Last trained: {existing.last_trained}")
            print(f"  Confidence: {existing.confidence_level}\n")

            response = input("Retrain parameters? (y/n): ")
            if response.lower() != 'y':
                print("Skipping retraining")
                return
            print()

        # Train parameters
        print("Training parameters...")
        print("-" * 60)

        learned_params = parameter_service.train_user_params(user.id)

        if not learned_params:
            print("❌ Parameter training failed")
            return

        print(f"\n✓ Training complete!\n")
        print(f"Learned Parameters:")
        print(f"  v_flat: {learned_params.v_flat:.3f} m/s ({(1000/learned_params.v_flat)/60:.2f} min/km)")
        print(f"  k_up: {learned_params.k_up:.3f}")
        print(f"  k_tech: {learned_params.k_tech:.3f}")
        print(f"  fatigue_alpha: {learned_params.fatigue_alpha:.3f}")
        print(f"\nOptimization Results:")
        print(f"  Score (MAE): {learned_params.optimization_score:.4f}")
        print(f"  Activities used: {learned_params.n_activities_used}")
        print(f"  Confidence: {learned_params.confidence_level}")

        # Compare with defaults
        from services.parameter_learning_service import DEFAULT_PARAMS
        print(f"\nComparison with defaults:")
        print(f"  v_flat: {DEFAULT_PARAMS['v_flat']:.3f} → {learned_params.v_flat:.3f} ({(learned_params.v_flat - DEFAULT_PARAMS['v_flat'])/DEFAULT_PARAMS['v_flat']*100:+.1f}%)")
        print(f"  k_up: {DEFAULT_PARAMS['k_up']:.3f} → {learned_params.k_up:.3f} ({(learned_params.k_up - DEFAULT_PARAMS['k_up'])/DEFAULT_PARAMS['k_up']*100:+.1f}%)")
        print(f"  k_tech: {DEFAULT_PARAMS['k_tech']:.3f} → {learned_params.k_tech:.3f} ({(learned_params.k_tech - DEFAULT_PARAMS['k_tech'])/DEFAULT_PARAMS['k_tech']*100:+.1f}%)")
        print(f"  fatigue_alpha: {DEFAULT_PARAMS['fatigue_alpha']:.3f} → {learned_params.fatigue_alpha:.3f} ({(learned_params.fatigue_alpha - DEFAULT_PARAMS['fatigue_alpha'])/DEFAULT_PARAMS['fatigue_alpha']*100:+.1f}%)")

        # Update tier status
        tier_status = hybrid_service.get_user_tier_status(user.id)
        print(f"\nUpdated Tier Status:")
        print(f"  Current tier: {tier_status['current_tier']}")
        print(f"  Confidence: {tier_status['confidence_level']}")
        print(f"  Has learned params: {tier_status['has_learned_params']}")

        print(f"\n✓ Tier 2 parameter learning successful!")
        print(f"\nNext steps:")
        print(f"  1. Use /api/hybrid/predict to get Tier 2 predictions")
        print(f"  2. Add more activities to progress to Tier 3 (need {tier_status['activities_needed_for_next_tier']} more)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test Tier 2 parameter learning')
    parser.add_argument('--user-id', type=int, help='User ID to test')

    args = parser.parse_args()

    test_parameter_learning(user_id=args.user_id)
