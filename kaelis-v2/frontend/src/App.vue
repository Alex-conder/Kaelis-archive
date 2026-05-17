<template>
  <div class="app">
    <header class="app-header">
      <h1>Kaelis 知识图谱可视化</h1>
      <p class="subtitle">FastAPI + NebulaGraph + AntV G6</p>
    </header>
    <main class="app-main">
      <GraphVisualizer />
    </main>
  </div>
</template>

<script setup>
import GraphVisualizer from './components/GraphVisualizer.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f3f4f6;
  color: #111827;
}
.app-header {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 20px 32px;
}
.app-header h1 {
  font-size: 22px;
  font-weight: 600;
  color: #4F46E5;
}
.app-header .subtitle {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}
.app-main {
  padding: 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
}
</style>
