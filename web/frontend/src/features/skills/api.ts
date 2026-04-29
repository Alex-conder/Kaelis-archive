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

export interface SkillPerformance {
  skill_id: string
  name: string
  success_rate: number
  recent_success_rate: number
  recent_trend: 'up' | 'down' | 'neutral'
  avg_execution_time_ms: number
  last_used_at: string | null
  history_count: number
}

export interface SkillWithPerformance extends Skill {
  performance: SkillPerformance
  avg_execution_time_ms: number
  last_used_at: string | null
  execution_history_count: number
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

  // D-4: 技能性能看板
  async getSkillPerformance(skillId: string): Promise<{ success: boolean; data?: SkillPerformance; error?: string }> {
    const res = await apiClient.get(`/api/skills/${skillId}/performance`)
    return res.data
  },

  async getAllSkillsPerformance(params?: { sort_by?: string; limit?: number }): Promise<{ success: boolean; data?: { skills: SkillWithPerformance[]; total: number }; error?: string }> {
    const search = new URLSearchParams()
    if (params?.sort_by) search.set('sort_by', params.sort_by)
    if (params?.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    const res = await apiClient.get(`/api/skills/performance/all${query ? '?' + query : ''}`)
    return res.data
  },
}
