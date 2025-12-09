import { defineStore } from 'pinia'
import api from '../services/api'

export const useGpxStore = defineStore('gpx', {
  state: () => ({
    currentGpx: null,
    gpxData: null,
    gpxList: [],
    loading: false,
    error: null
  }),

  getters: {
    hasData: (state) => state.gpxData !== null,
    totalDistance: (state) => state.gpxData?.total_distance || 0,
    bounds: (state) => state.gpxData?.bounds || null,
    points: (state) => state.gpxData?.points || []
  },

  actions: {
    async uploadGpx(file) {
      this.loading = true
      this.error = null

      try {
        const formData = new FormData()
        formData.append('file', file)

        const response = await api.post('/gpx/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })

        this.currentGpx = response.data
        await this.fetchGpxData(response.data.id)
        await this.fetchGpxList()

        return response.data
      } catch (error) {
        console.error('Upload error:', error)
        console.error('Response:', error.response)
        this.error = error.response?.data?.error || error.message || 'Failed to upload GPX'
        throw error
      } finally {
        this.loading = false
      }
    },

    async fetchGpxList() {
      try {
        const response = await api.get('/gpx/list')
        this.gpxList = response.data.files
      } catch (error) {
        console.error('Failed to fetch GPX list:', error)
      }
    },

    async fetchGpxData(gpxId) {
      this.loading = true
      this.error = null

      try {
        const response = await api.get(`/gpx/${gpxId}/data`)
        this.gpxData = response.data

        const metaResponse = await api.get(`/gpx/${gpxId}`)
        this.currentGpx = metaResponse.data
      } catch (error) {
        console.error('Fetch GPX data error:', error)
        console.error('Response:', error.response)
        this.error = error.response?.data?.error || error.message || 'Failed to fetch GPX data'
        throw error
      } finally {
        this.loading = false
      }
    },

    async deleteGpx(gpxId) {
      try {
        await api.delete(`/gpx/${gpxId}`)
        await this.fetchGpxList()

        if (this.currentGpx?.id === gpxId) {
          this.currentGpx = null
          this.gpxData = null
        }
      } catch (error) {
        this.error = error.response?.data?.error || 'Failed to delete GPX'
        throw error
      }
    }
  }
})
