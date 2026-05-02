#!/usr/bin/env python3
"""
Kaelis 决策学习器
基于历史执行结果学习，生成决策模型
"""
import json
import yaml
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 文件路径
EXEC_LOG_FILE = Path(".kaelis-auto-exec.jsonl")
DECISION_MODEL_FILE = Path("config/decision_model.yaml")

# 文件模式提取规则
FILE_PATTERNS = [
    (r"api/routes/.*\.py", "api_routes"),
    (r"web/frontend/src/pages/.*\.tsx", "frontend_pages"),
    (r"agent/.*\.py", "agent_tools"),
    (r"config/.*\.yaml", "config_files"),
    (r"api/models/.*\.py", "db_models"),
    (r"tests/.*\.py", "tests"),
    (r"scripts/.*\.py", "scripts"),
]

# 内容特征提取规则
CONTENT_FEATURES = [
    (r"# AUTO-FIX", "auto_fix_marker"),
    (r"# AUTO-DOCS", "auto_docs_marker"),
    (r"# AUTO-CHECK", "auto_check_marker"),
    (r"# AUTO-PHYSICIAN", "auto_physician_marker"),
    (r"# KAELIS-RUN", "kaelis_run_marker"),
    (r"# AUTO-LLM", "auto_llm_marker"),
    (r"@bp.route", "blueprint_route"),
    (r"@router", "fastapi_router"),
    (r"export default", "react_export"),
    (r"def main\(\):", "main_function"),
]


def extract_file_pattern(filepath: str) -> str:
    """从文件路径提取模式"""
    for pattern, name in FILE_PATTERNS:
        if re.search(pattern, filepath):
            return name
    return "other"


def extract_content_features(content: str) -> list:
    """从内容提取特征"""
    features = []
    for pattern, name in CONTENT_FEATURES:
        if re.search(pattern, content):
            features.append(name)
    return features


def load_execution_log() -> list:
    """加载执行日志"""
    if not EXEC_LOG_FILE.exists():
        return []
    
    entries = []
    with open(EXEC_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def analyze_patterns(entries: list) -> dict:
    """分析执行模式"""
    # 按 (文件模式, 内容特征, 操作) 聚合
    stats = defaultdict(lambda: {"success": 0, "total": 0, "files": set()})
    
    for entry in entries:
        filepath = entry.get("file", "")
        action = entry.get("action", "")
        result = entry.get("result", {})
        
        # 提取文件模式
        file_pattern = extract_file_pattern(filepath)
        
        # 尝试读取文件内容提取特征
        content_features = []
        try:
            content = Path(filepath).read_text(encoding="utf-8")
            content_features = extract_content_features(content)
        except Exception:
            pass
        
        # 构建统计键
        # 优先级：文件模式 + 内容特征 > 仅文件模式
        if content_features:
            for feature in content_features:
                key = (file_pattern, feature, action)
                stats[key]["total"] += 1
                if result.get("success", False):
                    stats[key]["success"] += 1
                stats[key]["files"].add(filepath)
        else:
            key = (file_pattern, "none", action)
            stats[key]["total"] += 1
            if result.get("success", False):
                stats[key]["success"] += 1
            stats[key]["files"].add(filepath)
    
    return stats


def build_decision_model(stats: dict, min_samples: int = 3, min_confidence: float = 0.7) -> dict:
    """构建决策模型"""
    model = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "rules": []
    }
    
    for (file_pattern, content_feature, action), data in stats.items():
        if data["total"] < min_samples:
            continue
        
        confidence = data["success"] / data["total"]
        if confidence < min_confidence:
            continue
        
        rule = {
            "file_pattern": file_pattern,
            "content_feature": content_feature if content_feature != "none" else None,
            "action": action,
            "confidence": round(confidence, 3),
            "success_count": data["success"],
            "total_count": data["total"],
            "priority": 1 if confidence > 0.9 else 2 if confidence > 0.8 else 3
        }
        model["rules"].append(rule)
    
    # 按置信度排序
    model["rules"].sort(key=lambda x: (-x["confidence"], -x["total_count"]))
    
    return model


def save_model(model: dict):
    """保存决策模型"""
    DECISION_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISION_MODEL_FILE, "w", encoding="utf-8") as f:
        yaml.dump(model, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"[OK] Decision model saved to {DECISION_MODEL_FILE}")


def print_model_stats(model: dict):
    """打印模型统计"""
    rules = model.get("rules", [])
    print(f"\n[STATS] Decision Model Generated")
    print(f"  Total rules: {len(rules)}")
    print(f"  High confidence (>0.9): {sum(1 for r in rules if r['confidence'] > 0.9)}")
    print(f"  Medium confidence (0.8-0.9): {sum(1 for r in rules if 0.8 <= r['confidence'] <= 0.9)}")
    print(f"  Low confidence (0.7-0.8): {sum(1 for r in rules if 0.7 <= r['confidence'] < 0.8)}")
    
    if rules:
        print(f"\n[TOP RULES]")
        for rule in rules[:5]:
            feature = rule['content_feature'] or 'any'
            print(f"  {rule['file_pattern']} + {feature} -> {rule['action']}")
            print(f"    Confidence: {rule['confidence']:.1%} ({rule['success_count']}/{rule['total_count']})")


def learn():
    """主学习流程"""
    print("[KAELIS] Decision Learner v1.0")
    print("=" * 60)
    
    # 加载执行日志
    entries = load_execution_log()
    if not entries:
        print("[WARN] No execution data found in .kaelis-auto-exec.jsonl")
        print("       Run 'make agent' first to generate execution data")
        return
    
    print(f"[INFO] Loaded {len(entries)} execution records")
    
    # 分析模式
    stats = analyze_patterns(entries)
    print(f"[INFO] Found {len(stats)} unique patterns")
    
    # 构建模型
    model = build_decision_model(stats)
    print_model_stats(model)
    
    # 保存模型
    save_model(model)
    print("\n[OK] Learning complete!")
    print("       Agent will now use learned model for decisions")


def get_model() -> dict:
    """获取当前决策模型"""
    if not DECISION_MODEL_FILE.exists():
        return {"version": "0.0", "rules": []}
    
    with open(DECISION_MODEL_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def query_decision(filepath: str, content: str) -> dict:
    """查询决策建议"""
    model = get_model()
    rules = model.get("rules", [])
    
    # 提取特征
    file_pattern = extract_file_pattern(filepath)
    content_features = extract_content_features(content)
    
    # 匹配规则
    for rule in rules:
        # 检查文件模式
        if rule["file_pattern"] != file_pattern:
            continue
        
        # 检查内容特征
        if rule["content_feature"]:
            if rule["content_feature"] not in content_features:
                continue
        
        # 找到匹配
        return {
            "action": rule["action"],
            "confidence": rule["confidence"],
            "source": "learned_model",
            "rule": rule
        }
    
    # 无匹配
    return {"action": None, "confidence": 0, "source": "none"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Decision Learner")
    parser.add_argument("--query", help="Query decision for a file")
    parser.add_argument("--min-samples", type=int, default=3, help="Minimum samples for a rule")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Minimum confidence threshold")
    args = parser.parse_args()
    
    if args.query:
        # 查询模式
        try:
            content = Path(args.query).read_text(encoding="utf-8")
        except Exception:
            content = ""
        
        result = query_decision(args.query, content)
        print(f"[QUERY] {args.query}")
        print(f"  File pattern: {extract_file_pattern(args.query)}")
        print(f"  Content features: {extract_content_features(content)}")
        print(f"  Decision: {result}")
    else:
        # 学习模式
        learn()


if __name__ == "__main__":
    main()
