import { defineStore } from 'pinia'
import api from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    isAuthenticated: false,
    user: null,
    token: localStorage.getItem('jwt_token') || null
  }),

  actions: {
    async checkAuthStatus() {
      if (!this.token) {
        this.isAuthenticated = false
        return
      }

      try {
        const response = await api.get('/auth/status')
        this.isAuthenticated = true
        this.user = response.data.user
      } catch (error) {
        this.isAuthenticated = false
        this.user = null
        this.token = null
        localStorage.removeItem('jwt_token')
      }
    },

    async getStravaAuthUrl() {
      const response = await api.get('/auth/strava')
      return response.data.auth_url
    },

    setToken(token) {
      this.token = token
      localStorage.setItem('jwt_token', token)
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    },

    logout() {
      this.isAuthenticated = false
      this.user = null
      this.token = null
      localStorage.removeItem('jwt_token')
      delete api.defaults.headers.common['Authorization']
    },

    async refreshStravaToken() {
      await api.post('/auth/refresh')
    }
  }
})
