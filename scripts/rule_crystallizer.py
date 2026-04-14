#!/usr/bin/env python3
"""
Kaelis 规则固化器
将高置信度决策模型转化为确定性规则
"""
import yaml
import re
import json
from pathlib import Path
from datetime import datetime

# 文件路径
DECISION_MODEL_FILE = Path("config/decision_model.yaml")
AUTO_RULES_FILE = Path("config/auto_rules.yaml")
KAELIS_AGENT_FILE = Path("scripts/kaelis_agent.py")
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")

# 固化阈值
CONFIDENCE_THRESHOLD = 0.95
MIN_SAMPLES = 5


def load_decision_model() -> dict:
    """加载决策模型"""
    if not DECISION_MODEL_FILE.exists():
        print("[WARN] Decision model not found. Run 'make learn-decision' first.")
        return {"rules": []}
    
    with open(DECISION_MODEL_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"rules": []}


def load_auto_rules() -> dict:
    """加载现有自动规则"""
    if not AUTO_RULES_FILE.exists():
        return {"version": "1.0", "rules": [], "crystallized_at": None}
    
    with open(AUTO_RULES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"version": "1.0", "rules": [], "crystallized_at": None}


def save_auto_rules(rules: dict):
    """保存自动规则"""
    AUTO_RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTO_RULES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def record_telemetry(event_type: str, data: dict):
    """记录遥测"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def crystallize_rules():
    """固化高置信度规则"""
    print("[KAELIS] Rule Crystallizer v1.0")
    print("=" * 60)
    print(f"[INFO] Threshold: confidence > {CONFIDENCE_THRESHOLD}, samples >= {MIN_SAMPLES}")
    
    # 加载决策模型
    model = load_decision_model()
    rules = model.get("rules", [])
    
    if not rules:
        print("[WARN] No rules in decision model")
        return
    
    # 加载现有自动规则
    auto_rules = load_auto_rules()
    existing_patterns = {r["pattern"] for r in auto_rules.get("rules", [])}
    
    # 筛选高置信度规则
    crystallized = []
    skipped = []
    
    for rule in rules:
        confidence = rule.get("confidence", 0)
        total_count = rule.get("total_count", 0)
        pattern = rule.get("file_pattern", "")
        content_feature = rule.get("content_feature")
        action = rule.get("action", "")
        
        # 构建匹配模式
        if content_feature:
            # 内容特征映射到具体标记
            feature_to_marker = {
                "auto_fix_marker": "# AUTO-FIX",
                "auto_docs_marker": "# AUTO-DOCS",
                "auto_check_marker": "# AUTO-CHECK",
                "auto_physician_marker": "# AUTO-PHYSICIAN",
                "kaelis_run_marker": "# KAELIS-RUN",
                "auto_llm_marker": "# AUTO-LLM",
                "blueprint_route": "@bp.route",
                "fastapi_router": "@router",
                "react_export": "export default",
                "main_function": "def main():",
            }
            marker = feature_to_marker.get(content_feature, f"# {content_feature.upper()}")
            match_pattern = f"{pattern}:{marker}"
        else:
            match_pattern = f"{pattern}:*"
        
        # 检查是否已存在
        if match_pattern in existing_patterns:
            skipped.append({
                "pattern": match_pattern,
                "reason": "already_exists"
            })
            continue
        
        # 检查阈值
        if confidence < CONFIDENCE_THRESHOLD:
            skipped.append({
                "pattern": match_pattern,
                "confidence": confidence,
                "reason": "confidence_too_low"
            })
            continue
        
        if total_count < MIN_SAMPLES:
            skipped.append({
                "pattern": match_pattern,
                "samples": total_count,
                "reason": "insufficient_samples"
            })
            continue
        
        # 固化规则
        crystallized_rule = {
            "pattern": match_pattern,
            "file_pattern": pattern,
            "content_feature": content_feature,
            "action": action,
            "confidence": confidence,
            "success_count": rule.get("success_count", 0),
            "total_count": total_count,
            "crystallized_at": datetime.now().isoformat(),
            "source": "decision_model"
        }
        
        auto_rules["rules"].append(crystallized_rule)
        crystallized.append(crystallized_rule)
        
        # 发送通知
        print(f"\n[OK] New rule crystallized: {match_pattern} -> {action}")
        print(f"     Confidence: {confidence:.1%} ({rule.get('success_count', 0)}/{total_count})")
    
    # 保存
    if crystallized:
        auto_rules["crystallized_at"] = datetime.now().isoformat()
        auto_rules["version"] = "1.0"
        save_auto_rules(auto_rules)
        
        # 记录遥测
        record_telemetry("rules_crystallized", {
            "count": len(crystallized),
            "rules": [{"pattern": r["pattern"], "action": r["action"]} for r in crystallized]
        })
        
        print(f"\n[OK] {len(crystallized)} rules crystallized")
        print(f"     Total auto-rules: {len(auto_rules['rules'])}")
    else:
        print("\n[INFO] No new rules to crystallize")
    
    if skipped:
        print(f"\n[INFO] {len(skipped)} rules skipped:")
        for s in skipped[:5]:  # 只显示前5个
            print(f"   - {s['pattern']}: {s['reason']}")


def get_crystallized_actions() -> list:
    """获取已固化的动作列表，用于 Agent 加载"""
    auto_rules = load_auto_rules()
    actions = []
    
    for rule in auto_rules.get("rules", []):
        pattern = rule.get("pattern", "")
        action = rule.get("action", "")
        
        # 解析 pattern
        if ":" in pattern:
            file_pat, content_pat = pattern.split(":", 1)
            if content_pat == "*":
                content_pat = None
        else:
            file_pat = pattern
            content_pat = None
        
        actions.append({
            "file_pattern": file_pat,
            "content_pattern": content_pat,
            "action": action,
            "confidence": rule.get("confidence", 0)
        })
    
    return actions


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Rule Crystallizer")
    parser.add_argument("--list", action="store_true", help="List crystallized rules")
    parser.add_argument("--export", action="store_true", help="Export rules for Agent")
    args = parser.parse_args()
    
    if args.list:
        # 列出已固化规则
        auto_rules = load_auto_rules()
        rules = auto_rules.get("rules", [])
        
        print(f"[CRYSTALLIZED RULES] Total: {len(rules)}")
        print("=" * 60)
        
        for rule in rules:
            print(f"\n{rule['pattern']}")
            print(f"  -> {rule['action']}")
            print(f"  Confidence: {rule['confidence']:.1%}")
            print(f"  Crystallized: {rule['crystallized_at'][:10]}")
    
    elif args.export:
        # 导出为 JSON（供 Agent 使用）
        actions = get_crystallized_actions()
        print(json.dumps(actions, indent=2))
    
    else:
        # 执行固化
        crystallize_rules()


if __name__ == "__main__":
    main()
