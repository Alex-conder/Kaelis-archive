/**
 * 前端图渲染器插件注册中心
 *
 * 将 React Flow 和 AntV G6 封装为可插拔的渲染器，
 * 支持运行时动态切换和扩展。
 */

import type { ComponentType } from 'react'

export interface GraphNode {
  id: string
  name: string
  type?: string
  [key: string]: any
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  relation?: string
  [key: string]: any
}

export interface RendererProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  className?: string
  onNodeClick?: (node: GraphNode) => void
  onEdgeClick?: (edge: GraphEdge) => void
}

export interface GraphRenderer {
  /** 渲染器唯一标识 */
  name: string
  /** 显示名称 */
  displayName: string
  /** 图标（Lucide 图标名或其他标识） */
  icon: string
  /** React 组件 */
  component: ComponentType<RendererProps>
  /** 是否可用（可加入环境检测） */
  available: boolean
}

class RendererRegistry {
  private renderers = new Map<string, GraphRenderer>()
  private defaultRenderer: string = 'xyflow'

  register(renderer: GraphRenderer) {
    this.renderers.set(renderer.name, renderer)
  }

  get(name: string): GraphRenderer | undefined {
    return this.renderers.get(name)
  }

  list(): GraphRenderer[] {
    return Array.from(this.renderers.values())
  }

  listAvailable(): GraphRenderer[] {
    return this.list().filter((r) => r.available)
  }

  setDefault(name: string) {
    if (this.renderers.has(name)) {
      this.defaultRenderer = name
    }
  }

  getDefault(): GraphRenderer | undefined {
    return this.get(this.defaultRenderer)
  }
}

// 单例
export const rendererRegistry = new RendererRegistry()
