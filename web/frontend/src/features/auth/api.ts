import { apiClient } from '@/shared/api/client'
import type { LoginRequest, LoginResponse, RegisterRequest } from '@/shared/api/types'

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<LoginResponse>('/api/auth/login', data),

  register: (data: RegisterRequest) =>
    apiClient.post('/api/auth/register', data),

  logout: () =>
    apiClient.post('/api/auth/logout'),

  me: () =>
    apiClient.get('/api/auth/me'),

  health: () =>
    apiClient.get('/api/auth/health'),

  activateOffline: () =>
    apiClient.post('/api/auth/offline/activate'),
}
