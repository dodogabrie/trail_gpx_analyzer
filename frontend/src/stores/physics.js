import { defineStore } from 'pinia'
import api from '../services/api'

/**
 * Physics-based prediction store.
 * Uses the new Minetti energy model for route predictions.
 */
export const usePhysicsStore = defineStore('physics', {
  state: () => ({
    // User calibration params
    params: {
      v_flat: null,          // m/s
      k_up: 1.0,             // Uphill efficiency factor
      k_tech: 1.0,           // Downhill technical ability
      a_param: 3.0,          // Downhill grade scaling
      k_terrain_up: 1.08,    // Terrain factor uphill
      k_terrain_down: 1.12,  // Terrain factor downhill
      k_terrain_flat: 1.05   // Terrain factor flat
    },

    // Calibration state
    calibrationActivities: [],
    isCalibrated: false,

    // Prediction result
    prediction: null,

    // UI state
    loading: false,
    error: null
  }),

  getters: {
    flatPaceMinPerKm: (state) => {
      if (!state.params.v_flat) return null
      // Convert m/s to min/km: (1000 / v_flat) / 60
      return (1000 / state.params.v_flat) / 60
    },

    hasValidParams: (state) => {
      return state.params.v_flat !== null && state.params.v_flat > 0
    }
  },

  actions: {
    /**
     * Calibrate physics parameters from user's Strava activities.
     *
     * @param {Array<number>} activityIds - Strava activity IDs to use for calibration
     */
    async calibrate(activityIds) {
      this.loading = true
      this.error = null

      try {
        console.log('🔧 Calibrating physics model with activities:', activityIds)

        const response = await api.post('/physics/calibrate', {
          activity_ids: activityIds
        })

        console.log('✅ Calibration response:', response.data)

        // Store calibrated parameters
        this.params = {
          ...this.params,
          ...response.data.params
        }

        this.isCalibrated = true
        this.calibrationActivities = activityIds

        console.log('📊 Calibrated params:', this.params)
        console.log('   v_flat:', this.params.v_flat, 'm/s =', this.flatPaceMinPerKm?.toFixed(2), 'min/km')
        console.log('   k_up:', this.params.k_up)
        console.log('   k_tech:', this.params.k_tech)
        console.log('   a_param:', this.params.a_param)

        return response.data
      } catch (error) {
        console.error('❌ Calibration failed:', error)
        this.error = error.response?.data?.error || 'Calibration failed'
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Predict route time using physics model.
     *
     * @param {number} gpxId - GPX file ID
     */
    async predict(gpxId) {
      if (!this.hasValidParams) {
        throw new Error('Must calibrate first')
      }

      this.loading = true
      this.error = null

      try {
        console.log('🚀 Running physics prediction for GPX:', gpxId)
        console.log('📊 Using params:', this.params)

        const response = await api.post('/physics/predict', {
          gpx_id: gpxId,
          user_params: this.params
        })

        console.log('✅ Prediction response:', response.data)

        this.prediction = response.data

        return response.data
      } catch (error) {
        console.error('❌ Prediction failed:', error)
        this.error = error.response?.data?.error || 'Prediction failed'
        throw error
      } finally {
        this.loading = false
      }
    },

    /**
     * Manually set calibration parameters.
     * Useful for testing or if user wants to override.
     */
    setParams(params) {
      this.params = {
        ...this.params,
        ...params
      }
      this.isCalibrated = this.hasValidParams
    },

    /**
     * Convert flat pace (min/km) to v_flat (m/s) and update params.
     */
    setFlatPace(minPerKm) {
      const metersPerSecond = 1000 / (minPerKm * 60)
      this.params.v_flat = metersPerSecond
      this.isCalibrated = this.hasValidParams
    },

    reset() {
      this.params = {
        v_flat: null,
        k_up: 1.0,
        k_tech: 1.0,
        a_param: 3.0,
        k_terrain_up: 1.08,
        k_terrain_down: 1.12,
        k_terrain_flat: 1.05
      }
      this.calibrationActivities = []
      this.isCalibrated = false
      this.prediction = null
      this.error = null
    }
  }
})
