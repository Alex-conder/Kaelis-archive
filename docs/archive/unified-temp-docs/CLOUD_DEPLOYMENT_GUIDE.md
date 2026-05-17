# Kaelis 云部署指南

## 📋 前置要求

### 必需工具
- kubectl (v1.25+)
- Helm (v3.12+)
- Docker (v24+)
- 云服务商 CLI (可选)

### 云服务商支持
- ✅ AWS EKS
- ✅ Azure AKS
- ✅ Google Cloud GKE
- ✅ 阿里云 ACK
- ✅ 腾讯云 TKE
- ✅ 华为云 CCE

---

## 🚀 快速部署

### 1. 环境准备

```bash
# 克隆代码
git clone https://github.com/your-org/kaelis.git
cd kaelis

# 配置 kubectl
kubectl config use-context your-cluster-context

# 验证连接
kubectl cluster-info
```

### 2. 配置 Secrets

```bash
# 编辑密钥文件
vim k8s/secret.yaml

# 应用密钥
kubectl apply -f k8s/secret.yaml -n kaelis
```

### 3. 执行部署

```bash
# 一键部署
./scripts/deploy-to-k8s.sh production v1.0.0

# 或使用 kubectl 直接部署
kubectl apply -f k8s/ -n kaelis
```

---

## ☁️ 云服务商特定配置

### AWS EKS

```bash
# 安装 AWS CLI
pip install awscli

# 配置凭证
aws configure

# 更新 kubeconfig
aws eks update-kubeconfig --region us-west-2 --name kaelis-cluster

# 安装 AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=kaelis-cluster
```

### 阿里云 ACK

```bash
# 配置阿里云 CLI
aliyun configure

# 获取集群凭证
aliyun cs GET /k8s/[cluster-id]/user_config > ~/.kube/config

# 安装 ingress-nginx
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace
```

### 腾讯云 TKE

```bash
# 配置腾讯云 CLI
tccli configure

# 获取集群凭证
tccli tke DescribeClusterKubeconfig --ClusterId cls-xxxxx

# 配置存储类
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cbs
csi:
  driver: com.tencent.cloud.csi.cbs
EOF
```

---

## 📦 托管服务配置

### 使用托管数据库 (推荐生产环境)

```yaml
# 修改 configmap，使用托管数据库地址
apiVersion: v1
kind: ConfigMap
metadata:
  name: kaelis-config
data:
  DATABASE_URL: "postgresql://user:pass@your-rds-endpoint:5432/kaelis"
  REDIS_URL: "redis://your-redis-endpoint:6379/0"
```

### 对象存储配置

```yaml
# 修改文件存储配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: kaelis-config
data:
  # AWS S3
  S3_ENDPOINT: "s3.amazonaws.com"
  S3_BUCKET: "kaelis-data"
  
  # 阿里云 OSS
  # OSS_ENDPOINT: "oss-cn-beijing.aliyuncs.com"
  # OSS_BUCKET: "kaelis-data"
  
  # 腾讯云 COS
  # COS_ENDPOINT: "cos.ap-beijing.myqcloud.com"
  # COS_BUCKET: "kaelis-data-xxx"
```

---

## 🔒 SSL/TLS 配置

### 使用 cert-manager (Let's Encrypt)

```bash
# 安装 cert-manager
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true

# 创建 ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@kaelis.io
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

---

## 📊 监控部署

```bash
# 部署 Prometheus + Grafana
kubectl apply -f docker-compose.monitoring.yml

# 或 Helm 安装
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.enabled=true
```

---

## 🔄 升级和回滚

### 滚动升级

```bash
# 更新镜像
kubectl set image deployment/kaelis-backend \
  backend=ghcr.io/your-org/kaelis-backend:v1.1.0 \
  -n kaelis --record

# 查看滚动状态
kubectl rollout status deployment/kaelis-backend -n kaelis
```

### 回滚

```bash
# 查看历史版本
kubectl rollout history deployment/kaelis-backend -n kaelis

# 回滚到上一版本
kubectl rollout undo deployment/kaelis-backend -n kaelis

# 回滚到指定版本
kubectl rollout undo deployment/kaelis-backend -n kaelis --to-revision=2
```

---

## 🐛 故障排查

### 查看 Pod 状态
```bash
kubectl get pods -n kaelis -o wide
kubectl describe pod <pod-name> -n kaelis
```

### 查看日志
```bash
# 实时日志
kubectl logs -f deployment/kaelis-backend -n kaelis

# 查看历史日志
kubectl logs deployment/kaelis-backend -n kaelis --previous

# 查看特定容器日志
kubectl logs <pod-name> -c backend -n kaelis
```

### 进入容器调试
```bash
kubectl exec -it deployment/kaelis-backend -n kaelis -- /bin/bash
```

### 网络诊断
```bash
# 测试服务连通性
kubectl run -it --rm debug --image=busybox:1.28 --restart=Never -- sh

# 在容器内测试
wget -O- http://backend:5000/api/status
```

---

## 💰 成本优化

### 资源限制建议

| 环境 | CPU 请求 | CPU 限制 | 内存请求 | 内存限制 |
|------|----------|----------|----------|----------|
| 开发 | 100m | 500m | 128Mi | 512Mi |
| 测试 | 250m | 1000m | 256Mi | 1Gi |
| 生产 | 500m | 2000m | 512Mi | 2Gi |

### 自动扩缩容
```bash
# 查看 HPA 状态
kubectl get hpa -n kaelis

# 手动调整副本数
kubectl scale deployment kaelis-backend --replicas=5 -n kaelis
```

---

## 📞 支持

遇到问题？
- 查看日志：`kubectl logs -n kaelis`
- 查看事件：`kubectl get events -n kaelis --sort-by='.lastTimestamp'`
- 提交 Issue：https://github.com/your-org/kaelis/issues
