import axios from 'axios'

const fallbackBaseUrl = () => {
  if (typeof window === 'undefined') return 'http://localhost:5000/api'
  const { protocol, hostname } = window.location
  return `${protocol}//${hostname}:5000/api`
}

const resolveBaseUrl = () => {
  const envBase = import.meta.env.VITE_API_URL
  if (!envBase) return fallbackBaseUrl()
  if (typeof window === 'undefined') return envBase
  try {
    const url = new URL(envBase)
    const isLocalEnv =
      url.hostname === 'localhost' || url.hostname === '127.0.0.1'
    const isRemotePage =
      window.location.hostname !== 'localhost' &&
      window.location.hostname !== '127.0.0.1'
    if (isLocalEnv && isRemotePage) {
      url.hostname = window.location.hostname
      return url.toString().replace(/\/$/, '')
    }
  } catch (error) {
    // Fall back to envBase if it's not a valid URL.
  }
  return envBase
}

const api = axios.create({
  baseURL: resolveBaseUrl(),
  withCredentials: false
})

// Add token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('jwt_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle token expiration
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('jwt_token')
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default api
