"""Strava sync service - downloads activities and trains model on login.

Handles the initial sync when user connects Strava account.
"""
import threading
from typing import List
from datetime import datetime
from flask import current_app
from database import db
from models.user import User
from models.strava_activity import StravaActivity
from models.sync_status import SyncStatus
from services.strava_service import StravaService
from services.parameter_learning_service import ParameterLearningService
from services.residual_ml_service import ResidualMLService
from services.user_residual_service import UserResidualService
import logging

logger = logging.getLogger(__name__)


class StravaSyncService:
    """Handles background sync of Strava activities and model training."""

    def sync_user_async(self, user_id: int):
        """Start background sync for user after Strava connection.

        Args:
            user_id: ID of user who just connected Strava
        """
        thread = threading.Thread(
            target=self._sync_user_background,
            args=(user_id,)
        )
        thread.daemon = True
        thread.start()
        logger.info(f"Started background Strava sync for user {user_id}")

    def _sync_user_background(self, user_id: int):
        """Background worker to download activities and train model.

        Fetches all running activities, scores by distance + elevation,
        downloads streams for top 15, and trains Tier 2/3 model.

        Args:
            user_id: User ID
        """
        try:
            from app import create_app
            app = create_app()

            with app.app_context():
                user = User.query.get(user_id)
                if not user or not user.access_token:
                    logger.error(f"User {user_id} not found or no access token")
                    return

                # Initialize or get sync status
                sync_status = SyncStatus.query.filter_by(user_id=user_id).first()
                if not sync_status:
                    sync_status = SyncStatus(user_id=user_id)
                    db.session.add(sync_status)

                sync_status.status = 'syncing'
                sync_status.started_at = datetime.utcnow()
                sync_status.current_step = 'fetching_activities'
                sync_status.message = 'Fetching and scoring your activities from Strava...'
                db.session.commit()

                logger.info(f"Starting Strava sync for user {user_id}")

                # Step 1: Download all recent activities
                activities = self._download_all_activities(user, sync_status)
                logger.info(f"Downloaded {len(activities)} activities for user {user_id}")

                if len(activities) < 5:
                    sync_status.status = 'completed'
                    sync_status.current_step = None
                    sync_status.message = f'Found {len(activities)} activities. Need 5+ for personalization.'
                    sync_status.completed_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"User {user_id} has only {len(activities)} activities, skipping training")
                    return

                # Step 2: Use downloaded activities for training (already filtered by score)
                selected_activities = activities
                logger.info(f"Using {len(selected_activities)} activities for training")

                # Step 3: Train model based on tier
                if len(activities) >= 20:
                    sync_status.current_step = 'training_tier3'
                    sync_status.message = 'Training advanced ML model (Tier 3)...'
                    db.session.commit()
                    self._train_tier3_model(user_id, selected_activities)
                elif len(activities) >= 5:
                    sync_status.current_step = 'training_tier2'
                    sync_status.message = 'Learning your running parameters (Tier 2)...'
                    db.session.commit()
                    self._train_tier2_params(user_id, selected_activities)

                # Mark as completed
                sync_status.status = 'completed'
                sync_status.current_step = None
                sync_status.message = f'Model trained with {len(selected_activities)} activities!'
                sync_status.completed_at = datetime.utcnow()
                db.session.commit()

                logger.info(f"Strava sync completed for user {user_id}")

        except Exception as e:
            logger.error(f"Error in Strava sync for user {user_id}: {str(e)}", exc_info=True)
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    sync_status = SyncStatus.query.filter_by(user_id=user_id).first()
                    if sync_status:
                        sync_status.status = 'error'
                        sync_status.error_message = str(e)
                        db.session.commit()
            except:
                pass

    def _download_all_activities(self, user: User, sync_status: SyncStatus, limit: int = 50) -> List[StravaActivity]:
        """Download user's most relevant activities from Strava.

        Fetches all running activities, scores them by distance + elevation,
        and downloads streams for the top 50 most relevant ones.

        Args:
            user: User object with Strava credentials
            limit: Max number of top activities to download (default: 50)

        Returns:
            List of top StravaActivity objects (max 50)
        """
        try:
            # Initialize Strava service
            strava_service = StravaService(
                current_app.config['STRAVA_CLIENT_ID'],
                current_app.config['STRAVA_CLIENT_SECRET'],
                current_app.config['STRAVA_REDIRECT_URI']
            )

            # Ensure token is valid
            access_token, refresh_token, expires_at = strava_service.get_valid_token(
                user.access_token,
                user.refresh_token,
                user.expires_at
            )

            # Update tokens if refreshed
            if access_token != user.access_token:
                user.access_token = access_token
                user.refresh_token = refresh_token
                user.expires_at = expires_at
                db.session.commit()

            # Get activities from last year
            after_timestamp = strava_service.get_timestamp_for_last_year()
            activities_data = strava_service.fetch_activities(access_token, after_timestamp)

            # Filter for runs only
            run_activities = [a for a in activities_data if a.get('type') == 'Run']

            logger.info(f"Found {len(run_activities)} running activities")

            # Score activities by distance (+ elevation if available)
            for activity in run_activities:
                distance_km = activity.get('distance', 0) / 1000
                elevation_m = activity.get('total_elevation_gain', 0)
                # Mixed score: distance + elevation (normalized)
                activity['_score'] = distance_km + (elevation_m / 100 if elevation_m else 0)

            # Sort by score descending and select top 50
            run_activities.sort(key=lambda a: a.get('_score', 0), reverse=True)
            selected_activities = run_activities[:min(50, len(run_activities))]

            logger.info(f"Selected top {len(selected_activities)} activities by distance/elevation")

            # Update total count
            sync_status.total_activities = len(selected_activities)
            sync_status.current_step = 'downloading_streams'
            sync_status.message = f'Downloading {len(selected_activities)} most relevant activities...'
            db.session.commit()

            downloaded_activities = []
            new_downloads = 0

            # Initialize residual service for collecting training data
            residual_service = UserResidualService()

            for i, activity_data in enumerate(selected_activities):
                # Update progress
                if i % 5 == 0:  # Update every 5 activities
                    sync_status.downloaded_activities = i
                    sync_status.message = f'Downloaded {i}/{len(selected_activities)} activities...'
                    db.session.commit()
                # Check if already exists
                existing = StravaActivity.query.filter_by(
                    user_id=user.id,
                    strava_id=activity_data['id']
                ).first()

                if existing:
                    logger.debug(f"Activity {activity_data['id']} already exists")

                    # Check if residuals exist, collect if missing
                    from models import UserActivityResidual
                    residual_exists = UserActivityResidual.query.filter_by(
                        user_id=user.id,
                        activity_id=str(activity_data['id'])
                    ).first()

                    if not residual_exists and existing.streams:
                        try:
                            logger.info(f"Collecting missing residuals for existing activity {activity_data['id']}")
                            residual = residual_service.collect_residuals_from_activity(
                                user_id=user.id,
                                activity_id=str(activity_data['id']),
                                activity_streams=existing.streams,
                                activity_metadata={
                                    'start_date': existing.start_date,
                                    'distance': existing.distance,
                                    'elevation': activity_data.get('total_elevation_gain', 0)
                                }
                            )
                            if residual:
                                logger.info(f"Collected residuals for existing activity {activity_data['id']}")
                        except Exception as e:
                            logger.error(f"Error collecting residuals for existing activity: {e}")

                    downloaded_activities.append(existing)
                    continue

                # Download streams
                logger.info(f"Downloading streams for activity {activity_data['id']}: {activity_data.get('name')}")
                streams = strava_service.download_streams(activity_data['id'], access_token)
                new_downloads += 1

                # Create activity record
                activity = StravaActivity(
                    user_id=user.id,
                    strava_id=activity_data['id'],
                    name=activity_data.get('name', 'Unnamed Activity'),
                    distance=activity_data.get('distance', 0),
                    start_date=datetime.fromisoformat(activity_data['start_date'].replace('Z', '+00:00')),
                    streams=streams
                )

                db.session.add(activity)
                db.session.flush()  # Get activity ID before collecting residuals

                # Collect residuals for training
                try:
                    residual = residual_service.collect_residuals_from_activity(
                        user_id=user.id,
                        activity_id=str(activity_data['id']),
                        activity_streams=streams,
                        activity_metadata={
                            'start_date': activity.start_date,
                            'distance': activity.distance,
                            'elevation': activity_data.get('total_elevation_gain', 0)
                        }
                    )
                    if residual:
                        logger.info(f"Collected residuals for activity {activity_data['id']}")
                    else:
                        logger.warning(f"Failed to collect residuals for activity {activity_data['id']}")
                except Exception as e:
                    logger.error(f"Error collecting residuals for activity {activity_data['id']}: {e}")

                downloaded_activities.append(activity)
                logger.info(f"Saved activity {activity_data['id']}")

            # Final update
            sync_status.downloaded_activities = len(downloaded_activities)
            db.session.commit()

            logger.info(f"Sync complete: {len(downloaded_activities)} total activities ({new_downloads} newly downloaded)")
            return downloaded_activities

        except Exception as e:
            logger.error(f"Error downloading activities: {str(e)}", exc_info=True)
            return []

    def _train_tier2_params(self, user_id: int, activities: List[StravaActivity]):
        """Train Tier 2 learned parameters.

        Args:
            user_id: User ID
            activities: List of activities to use for training
        """
        try:
            logger.info(f"Training Tier 2 parameters for user {user_id} with {len(activities)} activities")
            parameter_service = ParameterLearningService()

            # Train using all available activities (service will filter appropriately)
            learned_params = parameter_service.train_user_params(user_id)

            if learned_params:
                logger.info(f"Tier 2 training successful for user {user_id}")
            else:
                logger.warning(f"Tier 2 training failed for user {user_id}")

        except Exception as e:
            logger.error(f"Error training Tier 2 for user {user_id}: {str(e)}", exc_info=True)

    def _train_tier3_model(self, user_id: int, activities: List[StravaActivity]):
        """Train Tier 3 ML residual model.

        Args:
            user_id: User ID
            activities: List of activities to use for training
        """
        try:
            logger.info(f"Training Tier 3 ML model for user {user_id} with {len(activities)} activities")

            # First train Tier 2 params (Tier 3 builds on top)
            self._train_tier2_params(user_id, activities)

            # Then train ML model
            ml_service = ResidualMLService()

            if ml_service.should_train(user_id):
                model = ml_service.train_user_model(user_id)

                if model:
                    logger.info(f"Tier 3 training successful for user {user_id}")
                else:
                    logger.warning(f"Tier 3 training failed for user {user_id}")
            else:
                logger.info(f"User {user_id} doesn't have enough data for Tier 3, staying at Tier 2")

        except Exception as e:
            logger.error(f"Error training Tier 3 for user {user_id}: {str(e)}", exc_info=True)
