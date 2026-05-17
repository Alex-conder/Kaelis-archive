<template>
  <div class="graph-wrapper">
    <div ref="graphRef" class="graph-canvas"></div>
    <div class="toolbar">
      <button @click="loadData">加载图谱</button>
      <button @click="fitView">适应画布</button>
      <button @click="switchLayout">切换布局</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { Graph } from '@antv/g6';
import { queryGraph } from '../services/api.js';

const graphRef = ref(null);
let graph = null;
let currentLayout = 'force';

/**
 * 初始化 G6 图实例。
 * 配置画布交互、默认样式和初始布局。
 */
const initGraph = () => {
  if (!graphRef.value) return;

  graph = new Graph({
    container: graphRef.value,
    width: graphRef.value.clientWidth,
    height: 600,
    modes: {
      default: ['drag-canvas', 'zoom-canvas', 'drag-node']
    },
    layout: {
      type: 'force',
      preventOverlap: true,
      linkDistance: 120,
      nodeStrength: -50,
      edgeStrength: 0.1
    },
    node: {
      style: {
        size: 40,
        fill: '#4F46E5',
        stroke: '#312E81',
        lineWidth: 2,
        labelText: (d) => d.name || d.id,
        labelFill: '#fff',
        labelFontSize: 12,
        labelMaxWidth: 80
      }
    },
    edge: {
      style: {
        stroke: '#9CA3AF',
        lineWidth: 1.5,
        labelText: (d) => d.relation || '',
        labelFontSize: 10,
        labelFill: '#4B5563',
        endArrow: true,
        endArrowSize: 8
      }
    },
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-node', 'click-select']
  });

  window.addEventListener('resize', handleResize);
};

/**
 * 从 NebulaGraph 加载顶点与边数据，渲染到画布。
 */
const loadData = async () => {
  try {
    // 获取顶点
    const vertexRes = await queryGraph(
      'MATCH (v:Entity) RETURN id(v) as id, v.name as name LIMIT 200'
    );
    // 获取边
    const edgeRes = await queryGraph(
      'MATCH ()-[e]->() RETURN src(e) as source, dst(e) as target, type(e) as relation LIMIT 500'
    );

    const nodes = (vertexRes.data || []).map((v, i) => ({
      id: String(v.id || `n-${i}`),
      name: v.name || String(v.id)
    }));

    const edges = (edgeRes.data || []).map((e, i) => ({
      id: `e-${i}`,
      source: String(e.source),
      target: String(e.target),
      relation: e.relation || ''
    }));

    graph.setData({ nodes, edges });
    graph.render();
  } catch (err) {
    alert('图谱数据加载失败，请检查后端服务');
    console.error(err);
  }
};

const fitView = () => {
  if (graph) graph.fitView();
};

const switchLayout = () => {
  if (!graph) return;
  currentLayout = currentLayout === 'force' ? 'circular' : 'force';
  graph.setLayout({ type: currentLayout, preventOverlap: true });
  graph.layout();
};

const handleResize = () => {
  if (graph && graphRef.value) {
    graph.setSize(graphRef.value.clientWidth, 600);
  }
};

onMounted(() => {
  initGraph();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (graph) graph.destroy();
});
</script>

<style scoped>
.graph-wrapper {
  width: 100%;
  height: 100%;
}
.graph-canvas {
  width: 100%;
  height: 600px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}
.toolbar {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}
.toolbar button {
  padding: 8px 18px;
  background: #4F46E5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.toolbar button:hover {
  background: #4338CA;
}
</style>
