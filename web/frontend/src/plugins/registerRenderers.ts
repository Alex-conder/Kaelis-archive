/**
 * 注册所有内置图渲染器插件
 *
 * 使用示例：
 *   import { rendererRegistry } from './rendererRegistry'
 *   import './registerRenderers'
 *
 *   const r = rendererRegistry.get('g6')
 */

import { rendererRegistry } from './rendererRegistry'

// 懒加载组件，避免在未使用时打包全部依赖
const loadReactFlowRenderer = async () => {
  const { default: ReactFlowRenderer } = await import('../components/ReactFlowRenderer')
  return ReactFlowRenderer
}

const loadG6Renderer = async () => {
  const { default: NebulaGraphG6 } = await import('../components/NebulaGraphG6')
  return NebulaGraphG6
}

// React Flow（内置，始终可用）
rendererRegistry.register({
  name: 'xyflow',
  displayName: 'React Flow',
  icon: 'Workflow',
  component: (await loadReactFlowRenderer().catch(() => null)) as any,
  available: true,
})

// AntV G6（需安装 @antv/g6）
rendererRegistry.register({
  name: 'g6',
  displayName: 'AntV G6',
  icon: 'Network',
  component: (await loadG6Renderer().catch(() => null)) as any,
  available: true, // 运行时检测：若 import 失败则 component 为 null
})
