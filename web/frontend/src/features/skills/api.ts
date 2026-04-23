import { apiClient } from '@/shared/api/client'

export interface Skill {
  id: string
  name: string
  description: string
  task_type: string
  rating: number
  success_rate: number
  usage_count: number
  source: string
  version?: string
  tags?: string[]
  created_by?: string
  created_at?: string
}

export interface SkillsResponse {
  success: boolean
  data?: {
    skills: Skill[]
    total: number
  }
  error?: string
}

export const skillsApi = {
  async listSkills(params?: { task_type?: string; source?: string; sort_by?: string; limit?: number }): Promise<SkillsResponse> {
    const search = new URLSearchParams()
    if (params?.task_type) search.set('task_type', params.task_type)
    if (params?.source) search.set('source', params.source)
    if (params?.sort_by) search.set('sort_by', params.sort_by)
    if (params?.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    const res = await apiClient.get(`/api/skills/${query ? '?' + query : ''}`)
    return res.data
  },

  async installSkill(skillId: string): Promise<{ success: boolean; message?: string; error?: string }> {
    const res = await apiClient.post(`/api/skills/${skillId}/install`, {})
    return res.data
  },
}
