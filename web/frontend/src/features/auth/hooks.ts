import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from './api'
import { queryKeys } from '@/shared/lib/query-keys'
import type { LoginRequest, RegisterRequest, User } from '@/shared/api/types'

export function useAuthUser() {
  return useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: async () => {
      const { data } = await authApi.me()
      return (data.user ?? null) as User | null
    },
    retry: false,
    enabled: typeof window !== 'undefined' && !!localStorage.getItem('kaelis_access_token'),
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: LoginRequest) => {
      const res = await authApi.login(data)
      if (res.data.success && res.data.session) {
        localStorage.setItem('kaelis_access_token', res.data.session.access_token)
        localStorage.setItem('kaelis_refresh_token', res.data.session.refresh_token)
      }
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.auth.me })
    },
  })
}

export function useRegister() {
  return useMutation({
    mutationFn: (data: RegisterRequest) => authApi.register(data),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSettled: () => {
      localStorage.removeItem('kaelis_access_token')
      localStorage.removeItem('kaelis_refresh_token')
      qc.removeQueries({ queryKey: queryKeys.auth.me })
    },
  })
}

export function useActivateOffline() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await authApi.activateOffline()
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.auth.me })
    },
  })
}
