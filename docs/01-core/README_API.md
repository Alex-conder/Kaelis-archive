# Kaelis API 速查表

> Auto-generated from OpenAPI specification
> Version: 5.0.0
> Generated at: 2026-04-13 00:31:49

## 目录

- [System](#system)
- [Knowledge Graph](#knowledge-graph)
- [Intent](#intent)
- [Symbols](#symbols)
- [Team](#team)
- [Reports](#reports)
- [Omics](#omics)

## System

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| GET | `/api/health` | 健康检查 | `healthCheck` |

## Knowledge Graph

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| POST | `/api/kg/extract` | 从文本提取知识三元组 | `kgExtract` |
| POST | `/api/kg/query` | 查询知识图谱 | `kgQuery` |

## Intent

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| POST | `/api/intent/parse` | 解析自然语言意图 | `intentParse` |
| POST | `/api/intent/execute` | 执行意图 | `intentExecute` |

## Symbols

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| POST | `/api/symbols/index` | 构建符号索引 | `buildSymbolIndex` |
| GET | `/api/symbols/query` | 查询符号 | `querySymbols` |

## Team

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| GET | `/api/team/status` | 获取团队同步状态 | `getTeamSyncStatus` |

## Reports

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| POST | `/api/reports/export` | 导出报表 | `exportReport` |
| GET | `/api/reports/status/{job_id}` | 查询导出任务状态 | `getExportStatus` |

## Omics

| Method | Endpoint | Description | Operation ID |
|--------|----------|-------------|--------------|
| POST | `/api/omics/metabolomics/analyze` | 代谢组学分析 | `metabolomicsAnalyze` |

## 使用示例

### Python
```python
import requests

# Health check
response = requests.get('http://localhost:5000/api/health')
print(response.json())
```

### cURL
```bash
# Health check
curl http://localhost:5000/api/health
```

---

*This file is auto-generated. Do not modify manually.*