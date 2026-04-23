"""
Kaelis AI Native API Module
Phase 1: Infrastructure Layer - Unified HTTP API for AI Integration

Provides AI-friendly endpoints for:
- Contract queries (M0 rules, OpenAPI summary)
- Symbol search
- Impact analysis
- Risk scoring
- Block event recording
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
from pathlib import Path
import json
import re

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Create Blueprint
ai_native_bp = Blueprint('ai_native', __name__, url_prefix='/ai')

# ============================================================================
# Helper Functions
# ============================================================================

def load_m0_rules():
    """Load M0 guard rules"""
    rules_file = Path("config/guardrails/rules.json")
    
    if rules_file.exists():
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('rules', [])
        except Exception as e:
            print(f"Error loading M0 rules: {e}")
    
    # Default rules
    return [
        {
            "id": "M0-001",
            "name": "禁止直接数据库操作",
            "severity": "error",
            "category": "security",
            "description": "禁止直接使用数据库驱动执行SQL，必须使用ORM或服务层",
            "pattern": r"(cursor|db|connection)\.(execute|query)\s*\(",
            "suggestion": "使用 DatabaseService 或 ORM 模型方法",
            "example_violation": "cursor.execute('SELECT * FROM users')",
            "example_fix": "User.query.all() 或 db_service.get_users()"
        },
        {
            "id": "M0-002",
            "name": "禁止硬编码密钥",
            "severity": "error",
            "category": "security",
            "description": "禁止在代码中硬编码API密钥、密码等敏感信息",
            "pattern": r"(api_key|password|secret|token)\s*=\s*['\"][^'\"]+['\"]",
            "suggestion": "使用环境变量或密钥管理服务",
            "example_violation": "API_KEY = 'sk-1234567890abcdef'",
            "example_fix": "API_KEY = os.environ.get('API_KEY')"
        },
        {
            "id": "M0-003",
            "name": "必须处理异常",
            "severity": "warning",
            "category": "reliability",
            "description": "API端点必须包含异常处理",
            "pattern": None,
            "suggestion": "使用 try-except 包裹业务逻辑",
            "example_violation": "def get_user(id): return User.query.get(id)",
            "example_fix": "def get_user(id):\n    try:\n        return User.query.get(id)\n    except Exception as e:\n        return error_response(str(e))"
        },
        {
            "id": "M0-004",
            "name": "禁止使用 print 调试",
            "severity": "warning",
            "category": "code_quality",
            "description": "使用 logging 替代 print 进行日志输出",
            "pattern": r"\bprint\s*\(",
            "suggestion": "使用 logger.info/debug/error 替代",
            "example_violation": "print('Debug: user_id =', user_id)",
            "example_fix": "logger.debug('user_id: %s', user_id)"
        },
        {
            "id": "M0-005",
            "name": "必须包含类型注解",
            "severity": "info",
            "category": "code_quality",
            "description": "公共函数应包含类型注解",
            "pattern": None,
            "suggestion": "添加返回类型注解和参数类型",
            "example_violation": "def calculate(a, b): return a + b",
            "example_fix": "def calculate(a: int, b: int) -> int: return a + b"
        },
    ]

def search_code_symbols(query, limit=10):
    """Search for code symbols matching query"""
    symbols = []
    project_root = Path(".")
    
    python_files = list(project_root.rglob("*.py"))
    
    for file_path in python_files:
        if any(part.startswith('.') or part in ['venv', '__pycache__', 'node_modules'] 
               for part in file_path.parts):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    class_match = re.match(r'^class\s+(\w+)', line)
                    if class_match and query.lower() in class_match.group(1).lower():
                        symbol_name = class_match.group(1)
                        docstring = ""
                        for j in range(i, min(i+10, len(lines))):
                            if '"""' in lines[j-1] or "'''" in lines[j-1]:
                                docstring = lines[j-1].strip().strip('"').strip("'")
                                break
                        
                        symbols.append({
                            "name": symbol_name,
                            "type": "class",
                            "file_path": str(file_path),
                            "line_number": i,
                            "docstring": docstring[:200] if docstring else None
                        })
                    
                    func_match = re.match(r'^def\s+(\w+)\s*\((.*)\)', line)
                    if func_match and query.lower() in func_match.group(1).lower():
                        symbol_name = func_match.group(1)
                        signature = func_match.group(2)
                        
                        symbols.append({
                            "name": symbol_name,
                            "type": "function",
                            "file_path": str(file_path),
                            "line_number": i,
                            "signature": signature[:100] if signature else None
                        })
                    
                    if len(symbols) >= limit:
                        return symbols
                        
        except Exception as e:
            continue
    
    return symbols

def analyze_impact(symbol, file_path, change_type):
    """Analyze impact of a code change"""
    affected_files = []
    direct_deps = []
    indirect_deps = []
    
    project_root = Path(".")
    
    for py_file in project_root.rglob("*.py"):
        if any(part.startswith('.') or part in ['venv', '__pycache__'] 
               for part in py_file.parts):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                ref_count = content.count(symbol)
                if ref_count > 0:
                    affected_files.append(str(py_file))
                    
                    if symbol in content[:1000]:
                        direct_deps.append({
                            "name": py_file.stem,
                            "type": "module",
                            "file_path": str(py_file),
                            "line_number": 1
                        })
                    else:
                        indirect_deps.append({
                            "name": py_file.stem,
                            "type": "module",
                            "file_path": str(py_file),
                            "line_number": 1
                        })
        except:
            continue
    
    risk_level = "low"
    if len(affected_files) > 20:
        risk_level = "critical"
    elif len(affected_files) > 10:
        risk_level = "high"
    elif len(affected_files) > 5:
        risk_level = "medium"
    
    effort_map = {
        "low": "1-2 小时",
        "medium": "半天",
        "high": "1-2 天",
        "critical": "3-5 天"
    }
    
    suggestions = [
        f"检查 {len(affected_files)} 个受影响文件的单元测试",
        "更新相关文档",
        "在 staging 环境充分测试"
    ]
    
    if risk_level in ["high", "critical"]:
        suggestions.insert(0, "建议创建 feature branch 进行增量开发")
        suggestions.insert(1, "考虑分阶段发布")
    
    return {
        "symbol": symbol,
        "direct_dependencies": direct_deps[:10],
        "indirect_dependencies": indirect_deps[:10],
        "affected_files": affected_files,
        "risk_level": risk_level,
        "estimated_effort": effort_map.get(risk_level, "未知"),
        "suggestions": suggestions
    }

def calculate_risk_score(file_path, content=None):
    """Calculate comprehensive risk score for code change"""
    dimensions = []
    
    if content is None:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            content = ""
    
    lines_changed = len(content.split('\n')) if content else 0
    scope_score = min(30, lines_changed / 5)
    dimensions.append({
        "name": "变更范围",
        "score": int(scope_score),
        "weight": 0.30,
        "details": f"{lines_changed} 行代码变更"
    })
    
    import_count = len(re.findall(r'^(import|from)\s+', content, re.MULTILINE)) if content else 0
    dep_score = min(25, import_count * 3)
    dimensions.append({
        "name": "依赖复杂度",
        "score": int(dep_score),
        "weight": 0.25,
        "details": f"{import_count} 个导入语句"
    })
    
    has_tests = Path(file_path.replace('.py', '_test.py')).exists() or \
                Path(f"tests/test_{Path(file_path).name}").exists()
    test_score = 20 if has_tests else 0
    dimensions.append({
        "name": "测试覆盖",
        "score": test_score,
        "weight": 0.20,
        "details": "有测试文件" if has_tests else "无测试文件"
    })
    
    fault_score = 0
    fault_file = Path(".kaelis/faults/index.json")
    if fault_file.exists():
        try:
            with open(fault_file, 'r', encoding='utf-8') as f:
                faults = json.load(f)
                file_faults = [f for f in faults if file_path in f.get('files', [])]
                fault_score = min(15, len(file_faults) * 5)
        except:
            pass
    dimensions.append({
        "name": "历史故障",
        "score": fault_score,
        "weight": 0.15,
        "details": f"该文件有 {fault_score // 5} 次历史故障记录"
    })
    
    contract_score = 0
    if content:
        if 'TODO' in content or 'FIXME' in content:
            contract_score += 5
        if re.search(r'\.execute\s*\(', content):
            contract_score += 5
    dimensions.append({
        "name": "契约偏离",
        "score": contract_score,
        "weight": 0.10,
        "details": "发现 TODO/FIXME 或潜在违规模式" if contract_score > 0 else "无明显偏离"
    })
    
    total = sum(d["score"] * d["weight"] for d in dimensions)
    total_int = int(total)
    
    if total_int >= 70:
        level = "critical"
    elif total_int >= 50:
        level = "high"
    elif total_int >= 30:
        level = "medium"
    else:
        level = "low"
    
    suggestions = []
    if scope_score > 20:
        suggestions.append("考虑将大变更拆分为多个小 PR")
    if not has_tests:
        suggestions.append("为新功能添加单元测试")
    if contract_score > 0:
        suggestions.append("处理 TODO/FIXME 标记")
    if fault_score > 0:
        suggestions.append("特别关注该文件，历史上曾出现故障")
    
    return {
        "file_path": file_path,
        "total_score": total_int,
        "level": level,
        "dimensions": dimensions,
        "block_threshold": 70,
        "should_block": total_int >= 70,
        "suggestions": suggestions if suggestions else ["风险可控，正常提交"]
    }

def load_openapi_summary():
    """Load and summarize OpenAPI contract"""
    openapi_file = Path("contracts/openapi.yaml")
    
    if not openapi_file.exists() or not HAS_YAML:
        return {
            "title": "Kaelis API",
            "version": "1.0.0",
            "total_endpoints": 0,
            "endpoints": [],
            "schemas": [],
            "tags": []
        }
    
    try:
        with open(openapi_file, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        
        endpoints = []
        schemas = list(spec.get('components', {}).get('schemas', {}).keys())
        tags = list(set(tag.get('name', '') for tag in spec.get('tags', [])))
        
        for path, methods in spec.get('paths', {}).items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoints.append({
                        'method': method.upper(),
                        'path': path,
                        'summary': details.get('summary', ''),
                        'tags': details.get('tags', [])
                    })
        
        return {
            "title": spec.get('info', {}).get('title', 'Kaelis API'),
            "version": spec.get('info', {}).get('version', '1.0.0'),
            "total_endpoints": len(endpoints),
            "endpoints": endpoints,
            "schemas": schemas,
            "tags": tags
        }
    except Exception as e:
        return {
            "title": "Kaelis API",
            "version": "1.0.0",
            "total_endpoints": 0,
            "endpoints": [],
            "schemas": [],
            "tags": []
        }

# ============================================================================
# API Routes
# ============================================================================

@ai_native_bp.route('/contract/m0', methods=['GET'])
def get_m0_rules():
    """获取所有 M0 护栏规则"""
    rules = load_m0_rules()
    return jsonify(rules)

@ai_native_bp.route('/contract/m0/<rule_id>', methods=['GET'])
def get_m0_rule(rule_id):
    """获取单个 M0 规则详情"""
    rules = load_m0_rules()
    for rule in rules:
        if rule.get('id') == rule_id:
            return jsonify(rule)
    return jsonify({"error": f"规则 {rule_id} 未找到"}), 404

@ai_native_bp.route('/contract/openapi/summary', methods=['GET'])
def get_openapi_summary():
    """获取 OpenAPI 契约摘要"""
    return jsonify(load_openapi_summary())

@ai_native_bp.route('/symbols/search', methods=['GET'])
def search_symbols():
    """搜索代码符号"""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify({"error": "缺少查询参数 'q'"}), 400
    
    symbols = search_code_symbols(query, limit)
    return jsonify(symbols)

@ai_native_bp.route('/impact/analyze', methods=['POST'])
def analyze_change_impact():
    """分析代码变更的影响范围"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    symbol = data.get('symbol')
    file_path = data.get('file_path')
    change_type = data.get('change_type', 'modify')
    
    if not symbol or not file_path:
        return jsonify({"error": "缺少必需参数: symbol, file_path"}), 400
    
    result = analyze_impact(symbol, file_path, change_type)
    return jsonify(result)

@ai_native_bp.route('/risk/pre-check', methods=['GET'])
def pre_check_risk():
    """代码变更风险预检查"""
    file_path = request.args.get('file_path')
    content = request.args.get('content')
    
    if not file_path:
        return jsonify({"error": "缺少查询参数 'file_path'"}), 400
    
    result = calculate_risk_score(file_path, content)
    return jsonify(result)

@ai_native_bp.route('/block-events', methods=['POST'])
def record_block_event():
    """记录 Agent 阻断事件"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    # Ensure .kaelis directory exists
    telemetry_file = Path(".kaelis-telemetry.jsonl")
    telemetry_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate event ID
    event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{hash(data.get('file_path', '')) % 10000:04d}"
    
    try:
        with open(telemetry_file, 'a', encoding='utf-8') as f:
            record = {
                "event_id": event_id,
                "type": "block",
                "rule_id": data.get('rule_id'),
                "file_path": data.get('file_path'),
                "line_number": data.get('line_number'),
                "severity": data.get('severity'),
                "message": data.get('message'),
                "ai_original": data.get('ai_original_output'),
                "corrected": data.get('corrected_output'),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": data.get('session_id')
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        return jsonify({
            "success": True,
            "event_id": event_id,
            "message": "阻断事件已记录"
        })
    except Exception as e:
        return jsonify({"error": f"记录失败: {str(e)}"}), 500

@ai_native_bp.route('/health', methods=['GET'])
def health_check():
    """API 健康检查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "endpoints": [
            "/ai/contract/m0",
            "/ai/contract/openapi/summary",
            "/ai/symbols/search",
            "/ai/impact/analyze",
            "/ai/risk/pre-check",
            "/ai/block-events"
        ]
    })
