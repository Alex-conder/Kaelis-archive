/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false, // 使用 public/manifest.json
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,json}'],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 300 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src').replace(/\\/g, '/')
    }
  },
  base: './',
  build: {
    rollupOptions: {
      external: ['@antv/g6'],
      output: {
        manualChunks: {
          // FIX-3: 框架核心抽离
          framework: ['react', 'react-dom', 'react-router-dom'],
          // 状态与数据获取
          data: ['@tanstack/react-query', 'axios'],
          // Markdown 渲染（重型库）
          markdown: ['react-markdown', 'react-syntax-highlighter'],
          // 国际化
          i18n: ['i18next', 'react-i18next', 'i18next-browser-languagedetector'],
          // 截图工具（大库）
          capture: ['html2canvas'],
          // 图可视化
          graph: ['@xyflow/react'],
          // 状态管理
          state: ['zustand'],
        },
      },
    },
    // FIX-3: 代码分割优化
    chunkSizeWarningLimit: 300,
    sourcemap: false,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/'],
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        ws: true,
      }
    }
  }
})
