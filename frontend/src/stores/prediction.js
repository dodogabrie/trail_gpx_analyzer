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
    splitLevel: 3, // 1-5: 1=minimal detail, 5=max detail

    // Hybrid system
    tierStatus: null, // Tier status from hybrid system
    useHybridByDefault: true, // Use hybrid prediction by default

    // Effort level for predictions
    effort: 'training', // 'race', 'training', 'recovery'

    // Annotations
    annotations: [],
    annotationsDirty: false,

    // UI state
    loading: false,
    error: null,
    currentStep: 'predicting' // 'select-activity', 'calibrating', 'edit-calibration', 'predicting', 'results'
  }),

  getters: {
    isCalibrated: (state) => state.flatPace !== null,
    hasPrediction: (state) => state.prediction !== null,
    recommendedActivities: (state) =>
      state.calibrationActivities.filter(a => a.recommended),
    totalPredictedTime: (state) =>
      state.prediction?.total_time_formatted || null,
    totalStopTimeSeconds: (state) =>
      state.annotations.reduce((sum, a) => sum + (a.stop_time_seconds || 0), 0),
    adjustedTotalTimeSeconds: (state) => {
      if (!state.prediction?.total_time_seconds) return null
      const stopTime = state.annotations.reduce((sum, a) => sum + (a.stop_time_seconds || 0), 0)
      return state.prediction.total_time_seconds + stopTime
    },
    adjustedTotalTimeFormatted() {
      const totalSeconds = this.adjustedTotalTimeSeconds
      if (totalSeconds === null) return null
      const h = Math.floor(totalSeconds / 3600)
      const m = Math.floor((totalSeconds % 3600) / 60)
      const s = Math.floor(totalSeconds % 60)
      return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
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
      console.log('🔧 calibrateFromActivity called (PHYSICS MODEL)', { activityId, gpxId })
      this.loading = true
      this.error = null
      this.currentStep = 'calibrating'

      try {
        const response = await api.post('/physics/calibrate', {
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

    async predictRouteTime(gpxId, useHybrid = true) {
      console.log('🚀 predictRouteTime called with gpxId:', gpxId)
      console.log('🔍 Use Hybrid System:', useHybrid)

      this.loading = true
      this.error = null
      this.currentStep = 'predicting'

      try {
        // NEW: Use hybrid prediction system (automatic ML-enhanced predictions)
        if (useHybrid) {
          console.log('📡 Sending HYBRID prediction request...')

          const response = await api.post('/hybrid/predict', {
            gpx_id: gpxId,
            include_diagnostics: true,
            effort: this.effort
          }, {
            timeout: 60000
          })

          console.log('✅ Hybrid prediction received:', response.data)
          console.log('   Tier:', response.data.metadata.tier)
          console.log('   Method:', response.data.metadata.method)
          console.log('   Confidence:', response.data.metadata.confidence)
          console.log('   Activities used:', response.data.metadata.activities_used)

          // Prediction already includes metadata from backend
          this.prediction = response.data.prediction
          this.prediction.prediction_id = response.data.prediction_id
          this.similarActivities = []
          this.currentStep = 'results'

          return response.data
        }

        // FALLBACK: Old physics-based prediction (manual calibration)
        console.log('🔍 Current flatPace:', this.flatPace)
        console.log('🔍 Edited flatPace:', this.editedFlatPace)

        const flatPace = this.editedFlatPace || this.flatPace

        if (!flatPace) {
          console.error('❌ No flat pace - must calibrate first')
          throw new Error('Must calibrate first')
        }

        console.log('📡 Sending PHYSICS prediction request...')
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

        const response = await api.post('/physics/predict', {
          gpx_id: gpxId,
          flat_pace_min_per_km: flatPace,
          anchor_ratios: this.editedAnchorRatios,
          cached_activities: cachedActivities
        }, {
          timeout: 60000 // 60 second timeout
        })

        console.log('✅ Physics prediction received:', response.data)

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
        this.currentStep = 'predicting'
        throw error
      } finally {
        this.loading = false
        console.log('🏁 predictRouteTime finished')
      }
    },

    async fetchTierStatus() {
      try {
        const response = await api.get('/hybrid/tier-status')
        this.tierStatus = response.data
        console.log('📊 Tier status:', response.data)
        return response.data
      } catch (error) {
        console.error('Failed to fetch tier status:', error)
        return null
      }
    },

    async loadAnnotations(predictionId) {
      try {
        const response = await api.get(`/prediction/${predictionId}/annotations`)
        this.annotations = response.data.annotations || []
        this.annotationsDirty = false
      } catch (error) {
        console.error('Failed to load annotations:', error)
        this.annotations = []
      }
    },

    async saveAnnotations(predictionId) {
      try {
        const response = await api.put(`/prediction/${predictionId}/annotations`, {
          annotations: this.annotations
        })
        this.annotationsDirty = false
        return response.data
      } catch (error) {
        console.error('Failed to save annotations:', error)
        throw error
      }
    },

    addAnnotation(annotation) {
      this.annotations.push({
        id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
        ...annotation
      })
      this.annotationsDirty = true
    },

    removeAnnotation(annotationId) {
      const index = this.annotations.findIndex(a => a.id === annotationId)
      if (index !== -1) {
        this.annotations.splice(index, 1)
        this.annotationsDirty = true
      }
    },

    updateAnnotation(annotationId, updates) {
      const annotation = this.annotations.find(a => a.id === annotationId)
      if (annotation) {
        Object.assign(annotation, updates)
        this.annotationsDirty = true
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
      this.tierStatus = null
      this.annotations = []
      this.annotationsDirty = false
      this.currentStep = 'predicting'
      this.error = null
    }
  }
})
