#!/usr/bin/env python3
"""
Kaelis Phase 4 - 运维契约化代码生成器
从 OpenAPI 生成 SLO 配置、K8s 资源配额、Prometheus 告警规则

核心能力：将人类可读的声明式契约确定性转换为机器可执行的运维配置
"""

import os
import sys
import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class SLOSpec:
    """服务级别目标规范"""
    endpoint: str
    method: str
    operation_id: str
    success_rate: float  # 百分比，如 99.5
    latency_p95: int     # 毫秒，如 3000
    latency_p99: Optional[int] = None
    error_budget: Optional[float] = None  # 错误预算百分比
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CapacitySpec:
    """容量规划规范"""
    endpoint: str
    method: str
    operation_id: str
    qps: int             # 预估 QPS
    burst_qps: Optional[int] = None
    cpu_millicores: Optional[int] = None
    memory_mb: Optional[int] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class OpenAPIParser:
    """OpenAPI 解析器，提取 x-slo 和 x-capacity 扩展字段"""
    
    def __init__(self, openapi_path: Path):
        self.openapi_path = openapi_path
        self.spec = None
        
    def parse(self) -> dict:
        """解析 OpenAPI 文件"""
        with open(self.openapi_path, 'r', encoding='utf-8') as f:
            self.spec = yaml.safe_load(f)
        return self.spec
    
    def extract_slo_specs(self) -> List[SLOSpec]:
        """提取所有端点的 SLO 规范"""
        specs = []
        if not self.spec:
            self.parse()
            
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method not in ['get', 'post', 'put', 'delete', 'patch']:
                    continue
                    
                # 查找 x-slo 扩展字段
                x_slo = details.get('x-slo')
                if x_slo:
                    spec = SLOSpec(
                        endpoint=path,
                        method=method.upper(),
                        operation_id=details.get('operationId', 'unknown'),
                        success_rate=x_slo.get('success_rate', 99.0),
                        latency_p95=x_slo.get('latency_p95', 5000),
                        latency_p99=x_slo.get('latency_p99'),
                        error_budget=x_slo.get('error_budget', 0.1)
                    )
                    specs.append(spec)
                    
        return specs
    
    def extract_capacity_specs(self) -> List[CapacitySpec]:
        """提取所有端点的容量规范"""
        specs = []
        if not self.spec:
            self.parse()
            
        paths = self.spec.get('paths', {})
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method not in ['get', 'post', 'put', 'delete', 'patch']:
                    continue
                    
                # 查找 x-capacity 扩展字段
                x_capacity = details.get('x-capacity')
                if x_capacity:
                    qps = x_capacity.get('qps', 10)
                    # 自动计算资源需求（基于 QPS）
                    cpu_millicores = x_capacity.get('cpu_millicores') or self._estimate_cpu(qps)
                    memory_mb = x_capacity.get('memory_mb') or self._estimate_memory(qps)
                    
                    spec = CapacitySpec(
                        endpoint=path,
                        method=method.upper(),
                        operation_id=details.get('operationId', 'unknown'),
                        qps=qps,
                        burst_qps=x_capacity.get('burst_qps', int(qps * 1.5)),
                        cpu_millicores=cpu_millicores,
                        memory_mb=memory_mb
                    )
                    specs.append(spec)
                    
        return specs
    
    def _estimate_cpu(self, qps: int) -> int:
        """基于 QPS 估算 CPU 需求（millicores）"""
        # 基础 100m + 每 QPS 10m
        return 100 + qps * 10
    
    def _estimate_memory(self, qps: int) -> int:
        """基于 QPS 估算内存需求（MB）"""
        # 基础 256MB + 每 QPS 5MB
        return 256 + qps * 5


class SLOGenerator:
    """SLO 配置生成器"""
    
    def __init__(self, specs: List[SLOSpec]):
        self.specs = specs
        
    def generate_slo_yaml(self) -> str:
        """生成 SLO YAML 配置"""
        slo_config = {
            'apiVersion': 'kaelis.io/v1',
            'kind': 'ServiceLevelObjective',
            'metadata': {
                'name': 'kaelis-api-slo',
                'generated_at': datetime.now().isoformat(),
                'source': 'contracts/openapi.yaml'
            },
            'spec': {
                'service': 'kaelis-api',
                'objectives': []
            }
        }
        
        for spec in self.specs:
            objective = {
                'name': spec.operation_id,
                'endpoint': spec.endpoint,
                'method': spec.method,
                'indicators': {
                    'availability': {
                        'target': spec.success_rate / 100,
                        'window': '30d'
                    },
                    'latency': {
                        'p95': {
                            'target': f"{spec.latency_p95}ms",
                            'window': '7d'
                        }
                    }
                }
            }
            
            if spec.latency_p99:
                objective['indicators']['latency']['p99'] = {
                    'target': f"{spec.latency_p99}ms",
                    'window': '7d'
                }
            
            if spec.error_budget:
                objective['error_budget'] = f"{spec.error_budget}%"
                
            slo_config['spec']['objectives'].append(objective)
        
        return yaml.dump(slo_config, allow_unicode=True, sort_keys=False)
    
    def generate_prometheus_rules(self) -> str:
        """生成 Prometheus 告警规则 YAML"""
        rules = []
        
        for spec in self.specs:
            # 可用性告警
            rules.append({
                'alert': f"{spec.operation_id}_HighErrorRate",
                'expr': f'''(
                    sum(rate(http_requests_total{{handler="{spec.endpoint}",status=~"5.."}}[5m]))
                    /
                    sum(rate(http_requests_total{{handler="{spec.endpoint}"}}[5m]))
                ) > {(100 - spec.success_rate) / 100}''',
                'for': '5m',
                'labels': {
                    'severity': 'critical',
                    'service': 'kaelis-api',
                    'endpoint': spec.endpoint
                },
                'annotations': {
                    'summary': f"{spec.operation_id} error rate is too high",
                    'description': f"Error rate for {spec.endpoint} is above {(100 - spec.success_rate):.1f}%"
                }
            })
            
            # 延迟告警
            rules.append({
                'alert': f"{spec.operation_id}_HighLatency",
                'expr': f'''histogram_quantile(0.95,
                    sum(rate(http_request_duration_seconds_bucket{{handler="{spec.endpoint}"}}[5m])) by (le)
                ) > {spec.latency_p95 / 1000}''',
                'for': '5m',
                'labels': {
                    'severity': 'warning',
                    'service': 'kaelis-api',
                    'endpoint': spec.endpoint
                },
                'annotations': {
                    'summary': f"{spec.operation_id} P95 latency is too high",
                    'description': f"P95 latency for {spec.endpoint} is above {spec.latency_p95}ms"
                }
            })
        
        prometheus_config = {
            'apiVersion': 'monitoring.coreos.com/v1',
            'kind': 'PrometheusRule',
            'metadata': {
                'name': 'kaelis-api-alerts',
                'namespace': 'kaelis',
                'generated_at': datetime.now().isoformat()
            },
            'spec': {
                'groups': [{
                    'name': 'kaelis-api-slo',
                    'rules': rules
                }]
            }
        }
        
        return yaml.dump(prometheus_config, allow_unicode=True, sort_keys=False)
    
    def generate_grafana_dashboard(self) -> dict:
        """生成 Grafana 仪表盘 JSON"""
        panels = []
        y_position = 0
        
        for i, spec in enumerate(self.specs):
            # 可用性面板
            panels.append({
                'id': i * 2 + 1,
                'title': f"{spec.operation_id} - Availability",
                'type': 'stat',
                'targets': [{
                    'expr': f'''1 - (
                        sum(rate(http_requests_total{{handler="{spec.endpoint}",status=~"5.."}}[5m]))
                        /
                        sum(rate(http_requests_total{{handler="{spec.endpoint}"}}[5m]))
                    )''',
                    'legendFormat': 'Success Rate'
                }],
                'fieldConfig': {
                    'defaults': {
                        'unit': 'percentunit',
                        'thresholds': {
                            'steps': [
                                {'color': 'red', 'value': 0},
                                {'color': 'yellow', 'value': spec.success_rate / 100 - 0.01},
                                {'color': 'green', 'value': spec.success_rate / 100}
                            ]
                        }
                    }
                },
                'gridPos': {'h': 8, 'w': 12, 'x': 0, 'y': y_position}
            })
            
            # 延迟面板
            panels.append({
                'id': i * 2 + 2,
                'title': f"{spec.operation_id} - Latency P95",
                'type': 'timeseries',
                'targets': [{
                    'expr': f'''histogram_quantile(0.95,
                        sum(rate(http_request_duration_seconds_bucket{{handler="{spec.endpoint}"}}[5m])) by (le)
                    ) * 1000''',
                    'legendFormat': 'P95 Latency'
                }],
                'fieldConfig': {
                    'defaults': {
                        'unit': 'ms',
                        'thresholds': {
                            'steps': [
                                {'color': 'green', 'value': 0},
                                {'color': 'yellow', 'value': spec.latency_p95 * 0.8},
                                {'color': 'red', 'value': spec.latency_p95}
                            ]
                        }
                    }
                },
                'gridPos': {'h': 8, 'w': 12, 'x': 12, 'y': y_position}
            })
            
            y_position += 8
        
        dashboard = {
            'apiVersion': 1,
            'title': 'Kaelis API SLO Dashboard',
            'tags': ['kaelis', 'slo', 'generated'],
            'timezone': 'browser',
            'schemaVersion': 36,
            'version': 1,
            'refresh': '30s',
            'generated_at': datetime.now().isoformat(),
            'source': 'contracts/openapi.yaml',
            'panels': panels
        }
        
        return dashboard


class CapacityGenerator:
    """容量配置生成器"""
    
    def __init__(self, specs: List[CapacitySpec]):
        self.specs = specs
        
    def generate_k8s_resources(self) -> Dict[str, Any]:
        """生成 K8s 资源配额配置"""
        # 汇总所有端点的资源需求
        total_cpu = sum(spec.cpu_millicores or 100 for spec in self.specs)
        total_memory = sum(spec.memory_mb or 256 for spec in self.specs)
        max_qps = max(spec.qps for spec in self.specs) if self.specs else 10
        
        # 添加缓冲（20% 余量）
        buffer_cpu = int(total_cpu * 0.2)
        buffer_memory = int(total_memory * 0.2)
        
        resources = {
            'apiVersion': 'v1',
            'kind': 'ResourceQuota',
            'metadata': {
                'name': 'kaelis-api-quota',
                'namespace': 'kaelis',
                'generated_at': datetime.now().isoformat(),
                'source': 'contracts/openapi.yaml'
            },
            'spec': {
                'hard': {
                    'requests.cpu': f"{total_cpu + buffer_cpu}m",
                    'requests.memory': f"{total_memory + buffer_memory}Mi",
                    'limits.cpu': f"{(total_cpu + buffer_cpu) * 2}m",
                    'limits.memory': f"{(total_memory + buffer_memory) * 2}Mi",
                    'pods': str(max(2, len(self.specs) // 3))
                }
            }
        }
        
        return resources
    
    def generate_hpa_config(self) -> Dict[str, Any]:
        """生成 HPA（水平自动扩缩容）配置"""
        max_qps = max(spec.qps for spec in self.specs) if self.specs else 10
        
        # 基于 QPS 计算副本数
        min_replicas = max(2, len(self.specs) // 5)
        max_replicas = max(min_replicas * 3, min_replicas + 5)
        
        hpa = {
            'apiVersion': 'autoscaling/v2',
            'kind': 'HorizontalPodAutoscaler',
            'metadata': {
                'name': 'kaelis-hpa',
                'namespace': 'kaelis',
                'generated_at': datetime.now().isoformat(),
                'source': 'contracts/openapi.yaml',
                'annotations': {
                    'kaelis.io/max-qps': str(max_qps),
                    'kaelis.io/endpoints': str(len(self.specs))
                }
            },
            'spec': {
                'scaleTargetRef': {
                    'apiVersion': 'apps/v1',
                    'kind': 'Deployment',
                    'name': 'kaelis-app'
                },
                'minReplicas': min_replicas,
                'maxReplicas': max_replicas,
                'metrics': [
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'cpu',
                            'target': {
                                'type': 'Utilization',
                                'averageUtilization': 70
                            }
                        }
                    },
                    {
                        'type': 'Resource',
                        'resource': {
                            'name': 'memory',
                            'target': {
                                'type': 'Utilization',
                                'averageUtilization': 80
                            }
                        }
                    }
                ],
                'behavior': {
                    'scaleUp': {
                        'stabilizationWindowSeconds': 60,
                        'policies': [
                            {
                                'type': 'Percent',
                                'value': 100,
                                'periodSeconds': 15
                            }
                        ]
                    },
                    'scaleDown': {
                        'stabilizationWindowSeconds': 300,
                        'policies': [
                            {
                                'type': 'Percent',
                                'value': 10,
                                'periodSeconds': 60
                            }
                        ]
                    }
                }
            }
        }
        
        return hpa
    
    def generate_deployment_patch(self) -> Dict[str, Any]:
        """生成 Deployment 资源 patch（供 kubectl patch 使用）"""
        # 计算推荐的资源限制
        total_cpu = sum(spec.cpu_millicores or 100 for spec in self.specs)
        total_memory = sum(spec.memory_mb or 256 for spec in self.specs)
        
        # 单个 pod 的资源 = 总量 / 目标副本数（假设 3 个副本）
        target_replicas = 3
        per_pod_cpu = max(100, total_cpu // target_replicas)
        per_pod_memory = max(256, total_memory // target_replicas)
        
        patch = {
            'spec': {
                'template': {
                    'spec': {
                        'containers': [
                            {
                                'name': 'app',
                                'resources': {
                                    'requests': {
                                        'cpu': f"{per_pod_cpu}m",
                                        'memory': f"{per_pod_memory}Mi"
                                    },
                                    'limits': {
                                        'cpu': f"{per_pod_cpu * 2}m",
                                        'memory': f"{per_pod_memory * 2}Mi"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        return patch


class DockerComposeValidator:
    """Docker Compose 环境变量校验器"""
    
    def __init__(self, compose_path: Path, env_schema_path: Path):
        self.compose_path = compose_path
        self.env_schema_path = env_schema_path
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """执行校验，返回是否通过"""
        self.errors = []
        self.warnings = []
        
        # 加载文件
        compose_content = self._load_compose()
        env_schema = self._load_env_schema()
        
        if not compose_content or not env_schema:
            return False
        
        # 提取 Docker Compose 中的环境变量引用
        compose_vars = self._extract_env_vars(compose_content)
        
        # 获取 schema 中定义的变量
        schema_vars = set(env_schema.get('variables', {}).keys())
        
        # 校验每个变量
        for var_name, var_info in compose_vars.items():
            if var_name not in schema_vars:
                self.errors.append({
                    'type': 'UNDEFINED_VARIABLE',
                    'variable': var_name,
                    'location': var_info['location'],
                    'message': f"Environment variable '{var_name}' is used in docker-compose.yml but not defined in env.schema.json"
                })
            else:
                # 检查类型兼容性
                schema_var = env_schema['variables'][var_name]
                self._check_type_compatibility(var_name, var_info, schema_var)
        
        return len(self.errors) == 0
    
    def _load_compose(self) -> Optional[dict]:
        """加载 Docker Compose 文件"""
        try:
            with open(self.compose_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.errors.append({
                'type': 'LOAD_ERROR',
                'message': f"Failed to load docker-compose.yml: {e}"
            })
            return None
    
    def _load_env_schema(self) -> Optional[dict]:
        """加载环境变量 Schema"""
        try:
            with open(self.env_schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.errors.append({
                'type': 'LOAD_ERROR',
                'message': f"Failed to load env.schema.json: {e}"
            })
            return None
    
    def _extract_env_vars(self, compose: dict) -> Dict[str, dict]:
        """提取 Docker Compose 中的环境变量引用（${VAR} 或 ${VAR:-default}）"""
        vars_found = {}
        
        def scan_value(value: Any, location: str):
            """递归扫描值中的环境变量"""
            if isinstance(value, str):
                # 匹配 ${VAR} 或 ${VAR:-default}
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)
                for match in matches:
                    # 处理 ${VAR:-default} 格式
                    var_name = match.split(':-')[0].split(':')[0]
                    if var_name not in vars_found:
                        vars_found[var_name] = {
                            'location': location,
                            'usage': value,
                            'has_default': ':-' in match or ':' in match
                        }
            elif isinstance(value, dict):
                for k, v in value.items():
                    scan_value(v, f"{location}.{k}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    scan_value(item, f"{location}[{i}]")
        
        # 扫描 services 中的 environment 部分
        services = compose.get('services', {})
        for service_name, service_config in services.items():
            env = service_config.get('environment', [])
            if isinstance(env, list):
                for item in env:
                    scan_value(item, f"services.{service_name}.environment")
            elif isinstance(env, dict):
                for k, v in env.items():
                    scan_value(v, f"services.{service_name}.environment.{k}")
        
        return vars_found
    
    def _check_type_compatibility(self, var_name: str, var_info: dict, schema_var: dict):
        """检查类型兼容性"""
        var_type = schema_var.get('type', 'string')
        
        # 检查是否有默认值与类型冲突
        if var_info['has_default']:
            # 提取默认值
            match = re.search(r'\$\{' + var_name + r':-([^}]+)\}', var_info['usage'])
            if match:
                default_value = match.group(1)
                
                if var_type == 'integer':
                    try:
                        int(default_value)
                    except ValueError:
                        self.warnings.append({
                            'type': 'TYPE_MISMATCH',
                            'variable': var_name,
                            'message': f"Default value '{default_value}' may not be compatible with type 'integer'"
                        })
                elif var_type == 'boolean':
                    if default_value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                        self.warnings.append({
                            'type': 'TYPE_MISMATCH',
                            'variable': var_name,
                            'message': f"Default value '{default_value}' may not be compatible with type 'boolean'"
                        })
    
    def get_report(self) -> dict:
        """获取校验报告"""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }
    
    def print_report(self):
        """打印校验报告"""
        report = self.get_report()
        
        print("\n" + "=" * 60)
        print("Docker Compose 环境变量校验报告")
        print("=" * 60)
        
        if report['valid'] and report['warning_count'] == 0:
            print("✅ 所有环境变量定义正确！")
        elif report['valid']:
            print(f"⚠️  发现 {report['warning_count']} 个警告")
        else:
            print(f"❌ 发现 {report['error_count']} 个错误，{report['warning_count']} 个警告")
        
        if self.errors:
            print("\n❌ 错误:")
            for error in self.errors:
                print(f"   [{error['type']}] {error['message']}")
                print(f"   位置: {error['location']}")
        
        if self.warnings:
            print("\n⚠️  警告:")
            for warning in self.warnings:
                print(f"   [{warning['type']}] {warning['message']}")
        
        print("\n" + "=" * 60)


class OpsCodegen:
    """运维代码生成器主类"""
    
    def __init__(self, openapi_path: Path = None, output_dir: Path = None):
        self.openapi_path = openapi_path or PROJECT_ROOT / "contracts" / "openapi.yaml"
        self.output_dir = output_dir or PROJECT_ROOT / "config"
        self.parser = OpenAPIParser(self.openapi_path)
        
    def generate_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """生成所有运维配置"""
        results = {
            'generated': [],
            'errors': [],
            'dry_run': dry_run
        }
        
        # 1. 解析 OpenAPI
        try:
            self.parser.parse()
        except Exception as e:
            results['errors'].append(f"Failed to parse OpenAPI: {e}")
            return results
        
        # 2. 生成 SLO 配置
        slo_specs = self.parser.extract_slo_specs()
        if slo_specs:
            slo_gen = SLOGenerator(slo_specs)
            
            # SLO YAML
            slo_yaml = slo_gen.generate_slo_yaml()
            slo_path = self.output_dir / "slo.yaml"
            if not dry_run:
                slo_path.write_text(slo_yaml, encoding='utf-8')
            results['generated'].append({
                'file': str(slo_path),
                'type': 'slo',
                'endpoints': len(slo_specs)
            })
            
            # Prometheus 规则
            prometheus_yaml = slo_gen.generate_prometheus_rules()
            prometheus_path = self.output_dir / "prometheus-rules.yaml"
            if not dry_run:
                prometheus_path.write_text(prometheus_yaml, encoding='utf-8')
            results['generated'].append({
                'file': str(prometheus_path),
                'type': 'prometheus',
                'rules': len(slo_specs) * 2  # 每个端点 2 条规则
            })
            
            # Grafana 仪表盘
            dashboard = slo_gen.generate_grafana_dashboard()
            dashboard_path = self.output_dir / "grafana-dashboard.json"
            if not dry_run:
                dashboard_path.write_text(json.dumps(dashboard, indent=2), encoding='utf-8')
            results['generated'].append({
                'file': str(dashboard_path),
                'type': 'grafana',
                'panels': len(dashboard['panels'])
            })
        
        # 3. 生成容量配置
        capacity_specs = self.parser.extract_capacity_specs()
        if capacity_specs:
            cap_gen = CapacityGenerator(capacity_specs)
            
            # ResourceQuota
            quota = cap_gen.generate_k8s_resources()
            quota_path = self.output_dir / "k8s-resource-quota.yaml"
            if not dry_run:
                quota_path.write_text(yaml.dump(quota, allow_unicode=True, sort_keys=False), encoding='utf-8')
            results['generated'].append({
                'file': str(quota_path),
                'type': 'resource_quota',
                'endpoints': len(capacity_specs)
            })
            
            # HPA
            hpa = cap_gen.generate_hpa_config()
            hpa_path = self.output_dir / "k8s-hpa.yaml"
            if not dry_run:
                hpa_path.write_text(yaml.dump(hpa, allow_unicode=True, sort_keys=False), encoding='utf-8')
            results['generated'].append({
                'file': str(hpa_path),
                'type': 'hpa',
                'min_replicas': hpa['spec']['minReplicas'],
                'max_replicas': hpa['spec']['maxReplicas']
            })
            
            # Deployment patch
            patch = cap_gen.generate_deployment_patch()
            patch_path = self.output_dir / "k8s-deployment-patch.json"
            if not dry_run:
                patch_path.write_text(json.dumps(patch, indent=2), encoding='utf-8')
            results['generated'].append({
                'file': str(patch_path),
                'type': 'deployment_patch'
            })
        
        return results
    
    def validate_docker_compose(self) -> bool:
        """校验 Docker Compose 环境变量"""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        env_schema_path = PROJECT_ROOT / "config" / "env.schema.json"
        
        if not compose_path.exists():
            print(f"❌ Docker Compose file not found: {compose_path}")
            return False
        
        if not env_schema_path.exists():
            print(f"❌ Environment schema not found: {env_schema_path}")
            return False
        
        validator = DockerComposeValidator(compose_path, env_schema_path)
        is_valid = validator.validate()
        validator.print_report()
        
        return is_valid
    
    def print_summary(self, results: dict):
        """打印生成摘要"""
        print("\n" + "=" * 60)
        print("Kaelis Phase 4 - 运维契约化生成结果")
        print("=" * 60)
        
        if results['errors']:
            print("\n❌ 错误:")
            for error in results['errors']:
                print(f"   - {error}")
        
        if results['generated']:
            print(f"\n✅ 已生成 {len(results['generated'])} 个配置文件:")
            for item in results['generated']:
                print(f"   📄 {item['file']}")
                print(f"      类型: {item['type']}")
                if 'endpoints' in item:
                    print(f"      覆盖端点: {item['endpoints']}")
                if 'rules' in item:
                    print(f"      告警规则: {item['rules']}")
                if 'panels' in item:
                    print(f"      仪表盘面板: {item['panels']}")
                if 'min_replicas' in item:
                    print(f"      副本范围: {item['min_replicas']} - {item['max_replicas']}")
        else:
            print("\n⚠️  未生成任何配置（可能 OpenAPI 中未定义 x-slo 或 x-capacity）")
        
        if results['dry_run']:
            print("\n[DRY RUN] 未实际写入文件")
        
        print("\n" + "=" * 60)


def main():
    """CLI 入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Phase 4 - Operations as Code Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 生成所有运维配置
  python scripts/ops_codegen.py generate

  # 仅校验 Docker Compose
  python scripts/ops_codegen.py validate-compose

  # 干运行（不写入文件）
  python scripts/ops_codegen.py generate --dry-run
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # generate 命令
    gen_parser = subparsers.add_parser('generate', help='Generate all operations configs')
    gen_parser.add_argument('--dry-run', '-n', action='store_true', help='Dry run, do not write files')
    gen_parser.add_argument('--output', '-o', type=Path, help='Output directory')
    
    # validate-compose 命令
    subparsers.add_parser('validate-compose', help='Validate Docker Compose environment variables')
    
    args = parser.parse_args()
    
    codegen = OpsCodegen(output_dir=args.output if hasattr(args, 'output') and args.output else None)
    
    if args.command == 'generate':
        results = codegen.generate_all(dry_run=args.dry_run)
        codegen.print_summary(results)
        return 0 if not results['errors'] else 1
    
    elif args.command == 'validate-compose':
        is_valid = codegen.validate_docker_compose()
        return 0 if is_valid else 1
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
