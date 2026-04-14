# Neo4j 真实数据库切换指南

## 1. 安装 Neo4j Python 驱动

```bash
pip install neo4j>=5.14.0
```

或更新所有依赖：

```bash
pip install -r requirements.txt
```

## 2. 启动 Neo4j 容器

```bash
# 使用 docker-compose 启动 Neo4j
docker-compose up -d neo4j

# 等待服务就绪（约 30 秒）
docker ps --filter "name=neo4j"

# 查看日志
docker logs -f kaelis-neo4j
```

## 3. 验证 Neo4j 连接

```bash
# 方法 1: 使用 cypher-shell
docker exec -it kaelis-neo4j cypher-shell -u neo4j -p password

# 在 cypher-shell 中执行
MATCH (n) RETURN count(n) as count;
:exit

# 方法 2: 访问 Neo4j Browser
open http://localhost:7474
# 登录: neo4j / password
```

## 4. 验证 KgFlywheel 连接

```bash
# 运行验证脚本
python -c "
import os
os.environ['NEO4J_URI'] = 'bolt://localhost:7687'
os.environ['NEO4J_USER'] = 'neo4j'
os.environ['NEO4J_PASS'] = 'password'

# 强制重新导入模块
import importlib
import api.routes.kg_flywheel_tools as tools
importlib.reload(tools)

print('Connection status:', tools.neo4j_connection_status)
print('Driver type:', type(tools.neo4j_driver).__name__)

# 测试写入
with tools.neo4j_driver.session() as session:
    session.run('MERGE (n:Entity {name: \"TestNode\", type: \"Test\"})')
    result = session.run('MATCH (n:Entity {name: \"TestNode\"}) RETURN n').single()
    print('Test node created:', result is not None)
"
```

## 5. 运行完整测试

```bash
# 单元测试
pytest tests/test_kg_flywheel.py -v

# API 测试
python -c "
from flask import Flask
from api.routes.kg_flywheel_routes import kg_flywheel_bp

app = Flask(__name__)
app.register_blueprint(kg_flywheel_bp)

with app.test_client() as client:
    # 写入测试数据
    resp = client.post('/api/kg-flywheel/extract', json={
        'text': '阿里巴巴由马云创立，腾讯由马化腾创立',
        'user_id': 'neo4j-test'
    })
    print('Extract:', resp.status_code)
    
    # 查询验证
    resp = client.post('/api/kg-flywheel/query', json={
        'query': 'MATCH (n:Entity) RETURN n.name as name LIMIT 10'
    })
    data = resp.get_json()
    print('Query results:', data.get('results', []))
"
```

## 6. 在 Neo4j Browser 中查看数据

访问 http://localhost:7474 并执行：

```cypher
// 查看所有实体
MATCH (n:Entity) RETURN n LIMIT 50

// 查看实体关系
MATCH (n:Entity)-[r:RELATES]-(m:Entity) 
RETURN n.name, r.type, m.name 
LIMIT 50

// 统计
MATCH (n:Entity) RETURN count(n) as entity_count
MATCH ()-[r:RELATES]->() RETURN count(r) as relation_count
```

## 环境变量配置

```bash
# .env 文件
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASS=password

# Docker 环境使用服务名
NEO4J_URI=bolt://neo4j:7687
```

## 故障排查

### 连接被拒绝
```bash
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 检查端口
curl -v localhost:7474

# 重启 Neo4j
docker-compose restart neo4j
```

### 认证失败
```bash
# 重置密码
docker-compose down
docker volume rm desktop_neo4j_data  # 清除数据
docker-compose up -d neo4j
```

### 驱动未安装
```bash
pip install neo4j
# 验证
python -c "from neo4j import GraphDatabase; print('OK')"
```

## 验证清单

- [ ] Neo4j 容器运行中
- [ ] Python neo4j 驱动已安装
- [ ] KgFlywheel 连接到真实 Neo4j
- [ ] 数据写入后可在 Browser 中查看
- [ ] 重启服务后数据仍然持久化
