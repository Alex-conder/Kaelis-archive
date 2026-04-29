import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  base: './',
  build: {
    rollupOptions: {
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
        },
      },
    },
    // FIX-3: 代码分割优化
    chunkSizeWarningLimit: 300,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  }
})
