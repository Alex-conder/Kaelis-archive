/**
 * Axios API 客户端封装。
 * 集中管理后端接口调用，统一错误处理和超时控制。
 */
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器：可在此注入 Token 等
api.interceptors.request.use((config) => config);

// 响应拦截器：统一错误提示
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || 'Network error';
    console.error('[API Error]', msg);
    return Promise.reject(msg);
  }
);

// 业务接口
export const extractKnowledge = (text, schema = null) =>
  api.post('/api/extraction/extract', { text, schema });

export const queryGraph = (query) =>
  api.post('/api/graph/query', { query });

export const upsertTriples = (triples) =>
  api.post('/api/graph/upsert-triples', triples);

export default api;
