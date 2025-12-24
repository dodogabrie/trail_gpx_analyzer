import { defineStore } from 'pinia'
import api from '../services/api'

export const usePredictionStore = defineStore('prediction', {
  state: () => ({
    // Calibration
    calibrationActivities: [],
    selectedActivity: null,
    flatPace: null,
    calibrationDiagnostics: null,

    // Calibration editor data
    globalCurve: [],
    calibrationActivityStreams: {},
    editedFlatPace: null,
    editedAnchorRatios: null,

    // Prediction
    prediction: null,
    similarActivities: [],

    // UI state
    loading: false,
    error: null,
    currentStep: 'select-activity' // 'select-activity', 'calibrating', 'edit-calibration', 'predicting', 'results'
  }),

  getters: {
    isCalibrated: (state) => state.flatPace !== null,
    hasPrediction: (state) => state.prediction !== null,
    recommendedActivities: (state) =>
      state.calibrationActivities.filter(a => a.recommended),
    totalPredictedTime: (state) =>
      state.prediction?.total_time_formatted || null
  },

  actions: {
    async fetchCalibrationActivities(gpxId) {
      this.loading = true
      this.error = null

      try {
        const response = await api.get('/prediction/calibration-activities', {
          params: { gpx_id: gpxId, limit: 50 }
        })

        this.calibrationActivities = response.data.activities
        this.currentStep = 'select-activity'
      } catch (error) {
        console.error('Fetch calibration activities error:', error)
        this.error = error.response?.data?.error || 'Failed to fetch activities'
        throw error
      } finally {
        this.loading = false
      }
    },

    async calibrateFromActivity(activityId, gpxId) {
      console.log('🔧 calibrateFromActivity called', { activityId, gpxId })
      this.loading = true
      this.error = null
      this.currentStep = 'calibrating'

      try {
        const response = await api.post('/prediction/calibrate', {
          activity_id: activityId
        })

        console.log('✅ Calibration successful:', response.data)

        this.flatPace = response.data.flat_pace_min_per_km
        this.calibrationDiagnostics = response.data.diagnostics
        this.selectedActivity = response.data.activity

        // Store calibration editor data
        this.globalCurve = response.data.global_curve || []
        this.calibrationActivityStreams = response.data.calibration_activity_streams || {}

        // Initialize edited values with computed values
        this.editedFlatPace = this.flatPace
        this.editedAnchorRatios = response.data.anchor_ratios || {}

        // Go to edit-calibration step instead of auto-predicting
        this.currentStep = 'edit-calibration'
        this.loading = false

        return response.data
      } catch (error) {
        console.error('❌ Calibration error:', error)
        this.error = error.response?.data?.error || 'Calibration failed'
        this.currentStep = 'select-activity'
        throw error
      } finally {
        this.loading = false
      }
    },

    async saveCalibration(editedData) {
      try {
        await api.post('/prediction/save-calibration', {
          flat_pace_min_per_km: editedData.flat_pace_min_per_km,
          anchor_ratios: editedData.anchor_ratios,
          calibration_activity_id: this.selectedActivity?.id
        })

        console.log('✅ Calibration saved to user profile')

        // Update local state
        this.editedFlatPace = editedData.flat_pace_min_per_km
        this.editedAnchorRatios = editedData.anchor_ratios

      } catch (error) {
        console.error('❌ Failed to save calibration:', error)
        // Don't throw - allow prediction to continue even if save fails
      }
    },

    async predictRouteTime(gpxId) {
      console.log('🚀 predictRouteTime called with gpxId:', gpxId)
      console.log('🔍 Current flatPace:', this.flatPace)
      console.log('🔍 Edited flatPace:', this.editedFlatPace)

      const flatPace = this.editedFlatPace || this.flatPace

      if (!flatPace) {
        console.error('❌ No flat pace - must calibrate first')
        throw new Error('Must calibrate first')
      }

      this.loading = true
      this.error = null
      this.currentStep = 'predicting'

      try {
        console.log('📡 Sending prediction request to backend...')
        console.log('   GPX ID:', gpxId)
        console.log('   Flat Pace:', flatPace, 'min/km')
        console.log('   Anchor Ratios:', this.editedAnchorRatios)

        // Convert frontend calibration activities to backend format
        const cachedActivities = this.calibrationActivities.map(activity => ({
          id: activity.strava_id,
          name: activity.name,
          distance: activity.distance,
          start_date: activity.start_date,
          moving_time: activity.moving_time,
          elapsed_time: activity.elapsed_time,
          type: 'Run'
        }))

        console.log(`   Sending ${cachedActivities.length} cached activities to avoid re-fetch`)

        const response = await api.post('/prediction/predict', {
          gpx_id: gpxId,
          flat_pace_min_per_km: flatPace,
          anchor_ratios: this.editedAnchorRatios,
          cached_activities: cachedActivities
        }, {
          timeout: 60000 // 60 second timeout
        })

        console.log('✅ Prediction response received:', response.data)

        this.prediction = response.data.prediction
        this.similarActivities = response.data.similar_activities
        this.currentStep = 'results'

        return response.data
      } catch (error) {
        console.error('❌ Prediction error:', error)
        console.error('   Error code:', error.code)
        console.error('   Error message:', error.message)
        console.error('   Response:', error.response)

        if (error.code === 'ECONNABORTED') {
          this.error = 'Prediction timed out. Please ensure the backend server is running and the ML model is loaded.'
        } else {
          this.error = error.response?.data?.error || 'Prediction failed. Check browser console for details.'
        }
        this.currentStep = this.flatPace ? 'edit-calibration' : 'select-activity'
        throw error
      } finally {
        this.loading = false
        console.log('🏁 predictRouteTime finished')
      }
    },

    reset() {
      this.selectedActivity = null
      this.flatPace = null
      this.calibrationDiagnostics = null
      this.globalCurve = []
      this.calibrationActivityStreams = {}
      this.editedFlatPace = null
      this.editedAnchorRatios = null
      this.prediction = null
      this.similarActivities = []
      this.currentStep = 'select-activity'
      this.error = null
    }
  }
})
