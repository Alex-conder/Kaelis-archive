import { apiClient } from '@/shared/api/client'
import type { AgentCapability } from './types'

export async function listCapabilities(): Promise<AgentCapability[]> {
  // 通过 MCP Tool 列表获取后端能力
  try {
    const { data } = await apiClient.get('/api/mcp/tools')
    if (data.success && Array.isArray(data.data)) {
      return data.data.map(normalizeToolToCapability)
    }
  } catch {
    // Fallback: 从本地 API 获取 workflow nodes 作为能力示例
  }

  // 兜底：返回静态能力列表（确保 UI 始终有内容展示）
  return getStaticCapabilities()
}

function normalizeToolToCapability(tool: any): AgentCapability {
  return {
    id: tool.name || tool.id || 'unknown',
    name: tool.name || tool.id || 'Unknown Tool',
    description: tool.description || 'No description',
    parameters: tool.parameters?.properties || {},
    visualization_type: 'form',
    category: tool.category || 'general',
  }
}

function getStaticCapabilities(): AgentCapability[] {
  return [
    {
      id: 'memory_search',
      name: '记忆搜索',
      description: '在 L0-L3 记忆层中搜索相关内容',
      parameters: {
        layer: {
          name: 'layer',
          type: 'string',
          description: '记忆层级: L0, L1, L2, L3',
          required: true,
          enum: ['L0', 'L1', 'L2', 'L3'],
        },
        query: {
          name: 'query',
          type: 'string',
          description: '搜索关键词',
          required: true,
        },
        top_k: {
          name: 'top_k',
          type: 'number',
          description: '返回结果数量',
          default: 5,
        },
      },
      category: 'memory',
    },
    {
      id: 'skill_list',
      name: '技能列表',
      description: '列出所有可用技能',
      parameters: {
        task_type_filter: {
          name: 'task_type_filter',
          type: 'string',
          description: '按任务类型过滤',
          required: false,
        },
      },
      category: 'skills',
    },
    {
      id: 'daily_insight_generate',
      name: '生成每日洞察',
      description: '基于记忆生成每日洞察报告',
      parameters: {},
      category: 'insights',
    },
    {
      id: 'memory_write',
      name: '写入记忆',
      description: '向指定记忆层写入内容',
      parameters: {
        layer: {
          name: 'layer',
          type: 'string',
          description: '目标记忆层',
          required: true,
          enum: ['L0', 'L1', 'L2', 'L3'],
        },
        key: {
          name: 'key',
          type: 'string',
          description: '记忆键名',
          required: true,
        },
        value: {
          name: 'value',
          type: 'string',
          description: '记忆内容',
          required: true,
        },
      },
      category: 'memory',
    },
  ]
}

export async function executeCapability(
  capabilityId: string,
  params: Record<string, unknown>
): Promise<unknown> {
  const { data } = await apiClient.post('/api/mcp/tools/execute', {
    tool: capabilityId,
    params,
  })
  return data
}
