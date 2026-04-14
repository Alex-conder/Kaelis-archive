# Kaelis 上云部署指南

**目标**: 将 Kaelis 知识图谱飞轮部署到阿里云/腾讯云/自建 K8s 集群

---

## 一、前置要求

### 1. 本地环境
- Docker Desktop 已安装并运行
- kubectl 已配置
- 拥有一个云服务商账号（阿里云/腾讯云/AWS/Azure）

### 2. 云资源准备
- **ECS/VM**: 至少 2核4G（推荐 4核8G）
- **磁盘**: 系统盘 50GB + 数据盘 100GB
- **公网 IP**: 用于外部访问
- **域名**: 已备案（国内）或海外域名

---

## 二、镜像构建与推送

### 1. 登录 GitHub Container Registry

```bash
# 使用 GitHub Token 登录
echo $GITHUB_TOKEN | docker login ghcr.io -u yourusername --password-stdin
```

### 2. 构建并推送镜像

```bash
# 构建镜像
docker build -t ghcr.io/yourusername/kaelis:latest .

# 推送镜像
docker push ghcr.io/yourusername/kaelis:latest

# 推送版本标签
docker tag ghcr.io/yourusername/kaelis:latest ghcr.io/yourusername/kaelis:v1.0.0
docker push ghcr.io/yourusername/kaelis:v1.0.0
```

---

## 三、阿里云部署（推荐）

### 1. 创建 ACK 集群（或单机版）

**方案 A: ACK 托管集群**
- 登录阿里云控制台
- 进入容器服务 Kubernetes -> 创建集群
- 选择标准托管集群，Worker 节点 2 台（2核4G）

**方案 B: 单机 Docker Compose（测试）**
```bash
# 直接在 ECS 上运行
docker-compose up -d
```

### 2. 配置阿里云容器镜像服务（ACR）

```bash
# 登录阿里云镜像仓库
docker login --username=your_username registry.cn-hangzhou.aliyuncs.com

# 重新标记并推送
docker tag kaelis:latest registry.cn-hangzhou.aliyuncs.com/your-namespace/kaelis:latest
docker push registry.cn-hangzhou.aliyuncs.com/your-namespace/kaelis:latest
```

### 3. 部署到 ACK

```bash
# 配置 kubectl 连接集群
aliyun cs GET /k8s/[cluster-id]/user_config | jq -r '.config' > ~/.kube/config

# 创建命名空间
kubectl create namespace kaelis

# 应用部署配置
kubectl apply -f k8s/deployment.yaml

# 查看部署状态
kubectl get pods -n kaelis
kubectl logs -f deployment/kaelis-app -n kaelis
```

### 4. 配置 Ingress 和域名

```bash
# 安装 Ingress Controller（如未安装）
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# 配置 DNS 解析
curl -X POST https://alidns.aliyuncs.com/ \
  -H "Authorization: Bearer $ALICLOUD_TOKEN" \
  -d "Action=AddDomainRecord&DomainName=yourdomain.com&RR=kaelis&Type=A&Value=$SERVER_IP"

# 应用 Ingress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: kaelis-ingress
  namespace: kaelis
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: alidns-webhook
spec:
  tls:
    - hosts:
        - kaelis.yourdomain.com
      secretName: kaelis-tls
  rules:
    - host: kaelis.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: kaelis-app
                port:
                  number: 5000
EOF
```

---

## 四、腾讯云部署

### 1. 创建 TKE 集群
- 登录腾讯云控制台
- 进入容器服务 -> 集群 -> 新建
- 选择标准集群，节点配置 2核4G × 2

### 2. 使用云镜像仓库 TCR

```bash
# 登录腾讯云镜像仓库
docker login ccr.ccs.tencentyun.com --username=your_tencent_id

# 推送镜像
docker tag kaelis:latest ccr.ccs.tencentyun.com/your-namespace/kaelis:latest
docker push ccr.ccs.tencentyun.com/your-namespace/kaelis:latest
```

### 3. 部署配置差异

```yaml
# 修改 k8s/deployment.yaml 中的镜像地址
spec:
  template:
    spec:
      containers:
        - name: app
          image: ccr.ccs.tencentyun.com/your-namespace/kaelis:latest
          # 腾讯云拉取私有镜像需要配置 imagePullSecret
      imagePullSecrets:
        - name: tcr-secret
```

---

## 五、数据库迁移

### 1. 云数据库 RDS 配置

```bash
# 创建 PostgreSQL 实例（阿里云 RDS）
aliyun rds CreateDBInstance \
  --Engine PostgreSQL \
  --EngineVersion 14.0 \
  --DBInstanceClass rds.pg.s1.small \
  --DBInstanceStorage 100

# 获取连接地址
export DB_HOST=your-db.pg.rds.aliyuncs.com
export DB_PORT=5432
export DB_USER=kaelis
export DB_PASS=your-password

# 更新 Secret
kubectl create secret generic db-credentials \
  --from-literal=POSTGRES_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/kaelis" \
  -n kaelis
```

### 2. Neo4j 云部署选项

**选项 A: Neo4j AuraDB（托管）**
```bash
# 在 Neo4j 官网创建 AuraDB 免费实例
# 获取连接 URI 和密码
export NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
export NEO4J_USER=neo4j
export NEO4J_PASS=your-aura-password
```

**选项 B: 自建 Neo4j（ECS 上）**
```bash
# 在单独的高配 ECS 上运行 Neo4j
docker run -d \
  --name neo4j \
  -p 7687:7687 -p 7474:7474 \
  -v /data/neo4j:/data \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.14-enterprise
```

---

## 六、监控与告警

### 1. 阿里云云监控

```bash
# 安装云监控组件
kubectl apply -f https://arms-console.oss-cn-hangzhou.aliyuncs.com/ack-prometheus-operator/ack-prometheus-operator.yaml

# 配置告警规则
aliyun cms PutContactGroup \
  --ContactGroupName kaelis-ops \
  --ContactNames your-phone

# CPU > 80% 告警
aliyun cms PutMetricRule \
  --RuleName kaelis-cpu-high \
  --MetricName cpu_total \
  --Threshold 80
```

### 2. 自建 Prometheus + Grafana

```bash
# Helm 安装
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# 暴露 Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
```

---

## 七、备份策略

### 1. 自动备份脚本

```bash
#!/bin/bash
# backup.sh - 每日备份

BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# 备份 Neo4j
docker exec kaelis-neo4j neo4j-admin dump --to=/tmp/neo4j.dump
docker cp kaelis-neo4j:/tmp/neo4j.dump $BACKUP_DIR/

# 备份 PostgreSQL
pg_dump $DATABASE_URL > $BACKUP_DIR/postgres.sql

# 上传到 OSS
ossutil cp -r $BACKUP_DIR oss://your-bucket/kaelis-backup/

# 清理旧备份（保留7天）
find /backup -type d -mtime +7 -exec rm -rf {} \;
```

### 2. CronJob 配置

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: kaelis-backup
  namespace: kaelis
spec:
  schedule: "0 2 * * *"  # 每天凌晨2点
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: your-backup-image
              command: ["/backup.sh"]
          restartPolicy: OnFailure
```

---

## 八、成本估算（月度）

| 资源 | 阿里云 | 腾讯云 | 说明 |
|------|--------|--------|------|
| ECS (2台 2核4G) | ¥300 | ¥280 | 按量付费 |
| RDS PostgreSQL | ¥200 | ¥180 | 基础版 |
| OSS 存储 100GB | ¥10 | ¥12 | 标准存储 |
| 流量 100GB | ¥80 | ¥70 | 出网流量 |
| **总计** | **~¥590** | **~¥542** | - |

---

## 九、故障排查

### Pod 启动失败
```bash
kubectl describe pod -n kaelis
kubectl logs -f deployment/kaelis-app -n kaelis --previous
```

### Neo4j 连接失败
```bash
# 检查网络连通性
kubectl run debug --rm -it --image=busybox -- /bin/sh
nc -zv neo4j 7687

# 检查配置
kubectl get configmap neo4j-config -n kaelis -o yaml
```

### 性能问题
```bash
# 查看资源使用
kubectl top pod -n kaelis

# 扩容
kubectl scale deployment kaelis-app --replicas=4 -n kaelis
```

---

## 十、快速检查清单

部署前确认：
- [ ] 镜像已推送到镜像仓库
- [ ] 数据库连接字符串已配置
- [ ] 域名 DNS 解析已设置
- [ ] SSL 证书已准备
- [ ] 监控告警已配置

部署后验证：
- [ ] 访问 https://kaelis.yourdomain.com 正常
- [ ] /api/kg-flywheel/health 返回 200
- [ ] Neo4j Browser 可访问（如需要）
- [ ] 知识提取功能正常
- [ ] 图谱可视化正常显示

---

**部署完成！** 现在可以通过域名访问您的 Kaelis 知识图谱飞轮服务了。
