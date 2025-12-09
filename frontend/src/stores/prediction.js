import { defineStore } from 'pinia'
import api from '../services/api'

export const usePredictionStore = defineStore('prediction', {
  state: () => ({
    // Calibration
    calibrationActivities: [],
    selectedActivity: null,
    flatPace: null,
    calibrationDiagnostics: null,

    // Prediction
    prediction: null,
    similarActivities: [],

    // UI state
    loading: false,
    error: null,
    currentStep: 'select-activity' // 'select-activity', 'calibrating', 'predicting', 'results'
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

        // Automatically trigger prediction after calibration
        if (gpxId) {
          console.log('⏭️ Auto-triggering prediction for GPX', gpxId)
          this.currentStep = 'predicting'
          this.loading = false // Release loading for calibration

          // Trigger prediction immediately
          await this.predictRouteTime(gpxId)
        } else {
          this.currentStep = 'predicting'
        }

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

    async predictRouteTime(gpxId) {
      console.log('🚀 predictRouteTime called with gpxId:', gpxId)
      console.log('🔍 Current flatPace:', this.flatPace)

      if (!this.flatPace) {
        console.error('❌ No flat pace - must calibrate first')
        throw new Error('Must calibrate first')
      }

      this.loading = true
      this.error = null

      try {
        console.log('📡 Sending prediction request to backend...')
        console.log('   GPX ID:', gpxId)
        console.log('   Flat Pace:', this.flatPace, 'min/km')

        const response = await api.post('/prediction/predict', {
          gpx_id: gpxId,
          flat_pace_min_per_km: this.flatPace
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
        this.currentStep = 'select-activity'
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
      this.prediction = null
      this.similarActivities = []
      this.currentStep = 'select-activity'
      this.error = null
    }
  }
})
