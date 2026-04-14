#!/usr/bin/env python3
"""
Kaelis 预测分析器
基于历史执行记录生成预测规则
"""
import json
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 文件路径
EXEC_LOG_FILE = Path(".kaelis-auto-exec.jsonl")
PREDICTIVE_RULES_FILE = Path("config/predictive_rules.yaml")
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")

# 预测阈值
PREDICTION_THRESHOLD = 0.8  # 80% 执行率
MIN_SAMPLES = 3  # 最少样本数


def load_execution_history() -> list:
    """加载执行历史"""
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


def extract_file_type(filepath: str) -> str:
    """提取文件类型"""
    path = Path(filepath)
    
    # 基于路径模式
    if "api/routes/" in filepath:
        return "api_route"
    elif "web/frontend/src/pages/" in filepath:
        return "frontend_page"
    elif "agent/" in filepath:
        return "agent_tool"
    elif "config/" in filepath:
        return "config_file"
    elif "api/models/" in filepath:
        return "db_model"
    elif "scripts/" in filepath:
        return "script"
    elif "tests/" in filepath:
        return "test"
    
    # 基于扩展名
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    elif ext in [".tsx", ".ts"]:
        return "typescript"
    elif ext in [".yaml", ".yml"]:
        return "yaml"
    
    return "other"


def analyze_patterns(entries: list) -> dict:
    """分析执行模式"""
    # 按文件类型统计
    file_type_stats = defaultdict(lambda: {"total": 0, "auto_executed": 0, "actions": defaultdict(int)})
    
    for entry in entries:
        filepath = entry.get("file", "")
        action = entry.get("action", "")
        result = entry.get("result", {})
        
        file_type = extract_file_type(filepath)
        
        file_type_stats[file_type]["total"] += 1
        if result.get("success", False):
            file_type_stats[file_type]["auto_executed"] += 1
            file_type_stats[file_type]["actions"][action] += 1
    
    return file_type_stats


def build_predictive_rules(stats: dict, threshold: float = PREDICTION_THRESHOLD) -> dict:
    """构建预测规则"""
    rules = []
    
    for file_type, data in stats.items():
        if data["total"] < MIN_SAMPLES:
            continue
        
        execution_rate = data["auto_executed"] / data["total"]
        if execution_rate < threshold:
            continue
        
        # 找出最高频的动作
        if data["actions"]:
            most_common_action = max(data["actions"].items(), key=lambda x: x[1])
            action_name, action_count = most_common_action
            
            rule = {
                "file_type": file_type,
                "action": action_name,
                "execution_rate": round(execution_rate, 3),
                "sample_count": data["total"],
                "success_count": data["auto_executed"],
                "confidence": "high" if execution_rate > 0.9 else "medium",
                "generated_at": datetime.now().isoformat()
            }
            rules.append(rule)
    
    # 按执行率排序
    rules.sort(key=lambda x: -x["execution_rate"])
    
    return {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "threshold": threshold,
        "rules": rules
    }


def save_predictive_rules(rules: dict):
    """保存预测规则"""
    PREDICTIVE_RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PREDICTIVE_RULES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, default_flow_style=False, allow_unicode=True)
    print(f"[OK] Predictive rules saved to {PREDICTIVE_RULES_FILE}")


def record_telemetry(event_type: str, data: dict):
    """记录遥测"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def generate_predictive_rules(threshold: float = PREDICTION_THRESHOLD):
    """主生成流程"""
    print("[KAELIS] Predictive Analyzer v1.0")
    print("=" * 60)
    print(f"[INFO] Threshold: execution rate > {threshold:.0%}")
    
    # 加载历史
    entries = load_execution_history()
    if not entries:
        print("[WARN] No execution history found")
        print("       Run Agent first to generate execution data")
        return
    
    print(f"[INFO] Analyzing {len(entries)} execution records")
    
    # 分析模式
    stats = analyze_patterns(entries)
    print(f"[INFO] Found {len(stats)} file types")
    
    # 构建规则
    rules = build_predictive_rules(stats, threshold=threshold)
    
    if rules["rules"]:
        print(f"\n[RESULT] Generated {len(rules['rules'])} predictive rules:")
        for rule in rules["rules"]:
            print(f"  {rule['file_type']}: {rule['action']}")
            print(f"    Execution rate: {rule['execution_rate']:.1%} ({rule['success_count']}/{rule['sample_count']})")
            print(f"    Confidence: {rule['confidence']}")
        
        # 保存
        save_predictive_rules(rules)
        
        # 记录遥测
        record_telemetry("predictive_rules_generated", {
            "count": len(rules["rules"]),
            "threshold": threshold
        })
        
        print("\n[OK] Predictive analysis complete!")
        print("       Agent will now predict actions without explicit markers")
    else:
        print("\n[INFO] No predictive patterns found")
        print(f"       Need >{threshold:.0%} execution rate with >={MIN_SAMPLES} samples")


def load_predictive_rules() -> dict:
    """加载预测规则"""
    if not PREDICTIVE_RULES_FILE.exists():
        return {"version": "0.0", "rules": []}
    
    with open(PREDICTIVE_RULES_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"version": "0.0", "rules": []}


def predict_action(filepath: str) -> dict:
    """预测文件的操作"""
    rules = load_predictive_rules()
    file_type = extract_file_type(filepath)
    
    for rule in rules.get("rules", []):
        if rule["file_type"] == file_type:
            return {
                "action": rule["action"],
                "confidence": rule["execution_rate"],
                "reason": f"Historical execution rate: {rule['execution_rate']:.1%}",
                "is_prediction": True
            }
    
    return {"action": None, "confidence": 0, "reason": "No prediction available"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Predictive Analyzer")
    parser.add_argument("--predict", help="Predict action for a file")
    parser.add_argument("--threshold", type=float, default=PREDICTION_THRESHOLD, help="Execution rate threshold")
    args = parser.parse_args()
    
    if args.predict:
        # 预测模式
        result = predict_action(args.predict)
        file_type = extract_file_type(args.predict)
        
        print(f"[PREDICTION] {args.predict}")
        print(f"  File type: {file_type}")
        print(f"  Predicted action: {result['action'] or 'None'}")
        print(f"  Confidence: {result['confidence']:.1%}")
        print(f"  Reason: {result['reason']}")
    else:
        # 生成模式
        generate_predictive_rules(threshold=args.threshold)


if __name__ == "__main__":
    main()
