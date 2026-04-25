import axios, { AxiosError, AxiosInstance } from 'axios'

function resolveApiBaseUrl(): string {
  // Electron file:// protocol: backend runs on localhost:5000
  if (typeof window !== 'undefined' && window.location.protocol === 'file:') {
    return 'http://localhost:5000'
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:5000'
}

const API_BASE_URL = resolveApiBaseUrl()

// ============================================================================
// Axios Instance
// ============================================================================

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: inject auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('kaelis_access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle common errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!error.response) {
      // Network error (offline, CORS, server down)
      console.warn('[API] Network error:', error.message)
    } else if (error.response.status === 401) {
      localStorage.removeItem('kaelis_access_token')
      localStorage.removeItem('kaelis_refresh_token')
      window.location.href = '/#/login'
    } else if (error.response.status >= 500) {
      console.error('[API] Server error:', error.response.status, error.response.data)
    }
    return Promise.reject(error)
  }
)

export { apiClient, API_BASE_URL }
export default apiClient
