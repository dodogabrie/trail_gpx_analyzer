"""Auto-prediction service for MVP flow.

Handles automatic activity download and prediction after GPX upload.
"""
import threading
from typing import Dict, List
from datetime import datetime, timedelta
from flask import current_app
from database import db
from models.gpx_file import GPXFile
from models.user import User
from models.strava_activity import StravaActivity
from models.prediction import Prediction
from services.strava_service import StravaService
from services.hybrid_prediction_service import HybridPredictionService
import logging

logger = logging.getLogger(__name__)


class AutoPredictionService:
    """Handles automatic activity download and prediction for uploaded GPX files."""

    def __init__(self):
        self.prediction_service = HybridPredictionService()

    def process_gpx_async(self, gpx_id: int, user_id: int):
        """Process GPX file asynchronously: download activities and predict.

        Args:
            gpx_id: ID of uploaded GPX file
            user_id: ID of user who uploaded the GPX
        """
        thread = threading.Thread(
            target=self._process_gpx_background,
            args=(gpx_id, user_id)
        )
        thread.daemon = True
        thread.start()

    def _process_gpx_background(self, gpx_id: int, user_id: int):
        """Background worker to download activities and predict.

        Args:
            gpx_id: ID of uploaded GPX file
            user_id: ID of user
        """
        try:
            # Create new app context for background thread
            from app import create_app
            app = create_app()

            with app.app_context():
                # Update status to processing
                gpx_file = GPXFile.query.get(gpx_id)
                if not gpx_file:
                    logger.error(f"GPX file {gpx_id} not found")
                    return

                # Update status to predicting (no download, model already trained at login)
                gpx_file.processing_status = 'predicting'
                db.session.commit()

                # Run prediction
                gpx_data = gpx_file.data
                if not gpx_data or 'points' not in gpx_data:
                    gpx_file.processing_status = 'error'
                    gpx_file.error_message = 'Invalid GPX data'
                    db.session.commit()
                    return

                prediction_result = self.prediction_service.predict(
                    user_id=user_id,
                    gpx_points=gpx_data['points'],
                    effort='training'  # Default to training effort
                )

                # Save prediction to database (NEW format)
                # Extract tier from metadata
                tier_str = prediction_result.get('metadata', {}).get('tier', 'TIER_1_PHYSICS')
                tier_num = int(tier_str.split('_')[1]) if 'TIER_' in tier_str else 1

                prediction = Prediction(
                    user_id=user_id,
                    gpx_file_id=gpx_id,
                    tier=tier_num,
                    effort_level='training',
                    prediction_data=prediction_result
                )
                db.session.add(prediction)
                db.session.flush()  # Get prediction ID

                # Update GPX status to completed
                gpx_file.processing_status = 'completed'
                gpx_file.prediction_id = prediction.id
                db.session.commit()

                logger.info(f"Auto-prediction completed for GPX {gpx_id}, prediction ID {prediction.id}")

        except Exception as e:
            logger.error(f"Error in auto-prediction for GPX {gpx_id}: {str(e)}", exc_info=True)
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    gpx_file = GPXFile.query.get(gpx_id)
                    if gpx_file:
                        gpx_file.processing_status = 'error'
                        gpx_file.error_message = str(e)
                        db.session.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {str(inner_e)}")
