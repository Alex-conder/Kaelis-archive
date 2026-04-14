#!/usr/bin/env python3
"""
Kaelis 代谢物知识主动推送模块
检测代码中的代谢物名称并自动补充信息
"""
import re
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple

# 文件路径
METABOLITE_CACHE_FILE = Path("data/metabolite_cache.json")
TELEMETRY_FILE = Path(".kaelis-telemetry.jsonl")
PENDING_ANNOTATIONS_FILE = Path(".kaelis-pending-annotations.jsonl")

# 常见代谢物名称（基础字典，可扩展）
BASE_METABOLITES = {
    "glucose": {"name": "Glucose", "hmdb": "HMDB0000122", "formula": "C6H12O6", "mw": 180.16},
    "fructose": {"name": "Fructose", "hmdb": "HMDB0000660", "formula": "C6H12O6", "mw": 180.16},
    "sucrose": {"name": "Sucrose", "hmdb": "HMDB0000258", "formula": "C12H22O11", "mw": 342.30},
    "lactose": {"name": "Lactose", "hmdb": "HMDB0000186", "formula": "C12H22O11", "mw": 342.30},
    "citric_acid": {"name": "Citric acid", "hmdb": "HMDB0000094", "formula": "C6H8O7", "mw": 192.12},
    "lactic_acid": {"name": "Lactic acid", "hmdb": "HMDB0000190", "formula": "C3H6O3", "mw": 90.08},
    "acetic_acid": {"name": "Acetic acid", "hmdb": "HMDB0000042", "formula": "C2H4O2", "mw": 60.05},
    "glycine": {"name": "Glycine", "hmdb": "HMDB0000123", "formula": "C2H5NO2", "mw": 75.07},
    "alanine": {"name": "Alanine", "hmdb": "HMDB0000161", "formula": "C3H7NO2", "mw": 89.09},
    "glutamate": {"name": "Glutamate", "hmdb": "HMDB0000148", "formula": "C5H9NO4", "mw": 147.13},
    "cholesterol": {"name": "Cholesterol", "hmdb": "HMDB0000067", "formula": "C27H46O", "mw": 386.65},
    "caffeine": {"name": "Caffeine", "hmdb": "HMDB0001845", "formula": "C8H10N4O2", "mw": 194.19},
    "uric_acid": {"name": "Uric acid", "hmdb": "HMDB0000289", "formula": "C5H4N4O3", "mw": 168.11},
    "creatinine": {"name": "Creatinine", "hmdb": "HMDB0000562", "formula": "C4H7N3O", "mw": 113.12},
    "pyruvate": {"name": "Pyruvate", "hmdb": "HMDB0000243", "formula": "C3H4O3", "mw": 88.06},
    "malic_acid": {"name": "Malic acid", "hmdb": "HMDB0000074", "formula": "C4H6O5", "mw": 134.09},
    "oxalic_acid": {"name": "Oxalic acid", "hmdb": "HMDB0000239", "formula": "C2H2O4", "mw": 90.03},
    "succinic_acid": {"name": "Succinic acid", "hmdb": "HMDB0000254", "formula": "C4H6O4", "mw": 118.09},
    "fumaric_acid": {"name": "Fumaric acid", "hmdb": "HMDB0000134", "formula": "C4H4O4", "mw": 116.07},
}


def load_metabolite_cache() -> Dict:
    """加载代谢物缓存"""
    if METABOLITE_CACHE_FILE.exists():
        try:
            with open(METABOLITE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return BASE_METABOLITES.copy()


def save_metabolite_cache(cache: Dict):
    """保存代谢物缓存"""
    METABOLITE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METABOLITE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def record_telemetry(event_type: str, data: dict):
    """记录遥测"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    with open(TELEMETRY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def detect_metabolites(content: str) -> List[Tuple[str, dict]]:
    """检测代码中的代谢物名称"""
    cache = load_metabolite_cache()
    found = []
    
    # 转小写进行匹配
    content_lower = content.lower()
    
    for key, info in cache.items():
        # 匹配完整单词
        pattern = r'\b' + re.escape(key.lower()) + r'\b'
        if re.search(pattern, content_lower):
            found.append((key, info))
    
    return found


def generate_annotation(metabolite_info: dict) -> str:
    """生成代谢物注释"""
    return f"# {metabolite_info['name']}: HMDB={metabolite_info['hmdb']}, MW={metabolite_info['mw']}, Formula={metabolite_info['formula']}"


def check_existing_annotation(content: str, metabolite_name: str) -> bool:
    """检查是否已有该代谢物的注释"""
    # 检查是否已有 HMDB 注释
    pattern = rf'#\s*{re.escape(metabolite_name)}.*HMDB'
    return bool(re.search(pattern, content, re.IGNORECASE))


def annotate_file(filepath: str, dry_run: bool = False) -> dict:
    """
    为文件添加代谢物注释
    
    Returns:
        {"added": int, "pending": int, "found": list}
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except Exception as e:
        return {"added": 0, "pending": 0, "found": [], "error": str(e)}
    
    # 检测代谢物
    metabolites = detect_metabolites(content)
    
    if not metabolites:
        return {"added": 0, "pending": 0, "found": []}
    
    added = 0
    pending = 0
    annotations = []
    
    for name, info in metabolites:
        if check_existing_annotation(content, info['name']):
            # 已有注释，跳过
            continue
        
        annotation = generate_annotation(info)
        annotations.append((name, info, annotation))
        
        if info.get('hmdb'):
            # 缓存命中，准备添加
            added += 1
        else:
            # 缓存未命中，后台查询
            pending += 1
            queue_background_lookup(name)
    
    if added > 0 and not dry_run:
        # 实际添加注释
        lines = content.split('\n')
        new_lines = []
        
        for i, line in enumerate(lines):
            # 在每行可能引用代谢物的代码前添加注释
            for name, info, annotation in annotations:
                if name.lower() in line.lower() and not line.strip().startswith('#'):
                    # 检查上一行是否已有注释
                    if i == 0 or not new_lines[-1].strip().startswith('#'):
                        new_lines.append(annotation)
                        added += 1
            new_lines.append(line)
        
        # 写回文件
        new_content = '\n'.join(new_lines)
        Path(filepath).write_text(new_content, encoding="utf-8")
        
        print(f"[ANNOTATE] Added {added} metabolite annotations to {filepath}")
    
    # 记录遥测
    record_telemetry("metabolite_annotated", {
        "filepath": filepath,
        "found": len(metabolites),
        "added": added,
        "pending": pending,
        "metabolites": [m[0] for m in metabolites]
    })
    
    return {
        "added": added,
        "pending": pending,
        "found": [m[0] for m in metabolites]
    }


def queue_background_lookup(metabolite_name: str):
    """后台异步查询代谢物信息"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "name": metabolite_name,
        "status": "pending"
    }
    with open(PENDING_ANNOTATIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    
    # 启动后台线程查询
    thread = threading.Thread(target=background_lookup, args=(metabolite_name,), daemon=True)
    thread.start()


def background_lookup(metabolite_name: str):
    """后台查询代谢物信息"""
    try:
        # 尝试复用现有的公共数据库查询
        sys.path.insert(0, str(Path(__file__).parent.parent))
        try:
            from core.services.public_db import get_connector
            connector = get_connector()
            
            # 查询 PubChem
            result = connector.search_pubchem(metabolite_name)
            if result:
                # 更新缓存
                cache = load_metabolite_cache()
                cache[metabolite_name.lower()] = {
                    "name": metabolite_name.capitalize(),
                    "hmdb": result.get("hmdb_id", "pending"),
                    "formula": result.get("formula", "N/A"),
                    "mw": result.get("molecular_weight", "N/A")
                }
                save_metabolite_cache(cache)
                
                record_telemetry("metabolite_lookup_complete", {
                    "name": metabolite_name,
                    "source": "pubchem",
                    "success": True
                })
                return
        except ImportError:
            pass
        
        # 查询失败
        record_telemetry("metabolite_lookup_failed", {
            "name": metabolite_name,
            "reason": "service_unavailable"
        })
    
    except Exception as e:
        record_telemetry("metabolite_lookup_error", {
            "name": metabolite_name,
            "error": str(e)
        })


def get_annotation_stats() -> dict:
    """获取注释统计"""
    cache = load_metabolite_cache()
    
    stats = {
        "cached_metabolites": len(cache),
        "with_hmdb_id": sum(1 for v in cache.values() if v.get('hmdb') and v['hmdb'] != 'pending'),
        "pending_lookups": 0
    }
    
    if PENDING_ANNOTATIONS_FILE.exists():
        with open(PENDING_ANNOTATIONS_FILE, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "pending":
                        stats["pending_lookups"] += 1
                except:
                    pass
    
    return stats


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Kaelis Metabolite Annotator")
    parser.add_argument("filepath", nargs="?", help="File to annotate")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--detect", action="store_true", help="Detect metabolites only")
    parser.add_argument("--stats", action="store_true", help="Show annotation statistics")
    args = parser.parse_args()
    
    if args.stats:
        stats = get_annotation_stats()
        print("[METABOLITE ANNOTATION STATS]")
        print(f"  Cached metabolites: {stats['cached_metabolites']}")
        print(f"  With HMDB ID: {stats['with_hmdb_id']}")
        print(f"  Pending lookups: {stats['pending_lookups']}")
        return
    
    if not args.filepath:
        parser.print_help()
        return
    
    if args.detect:
        # 仅检测
        content = Path(args.filepath).read_text(encoding="utf-8")
        metabolites = detect_metabolites(content)
        
        if metabolites:
            print(f"[DETECTED] {len(metabolites)} metabolites in {args.filepath}:")
            for name, info in metabolites:
                print(f"  - {info['name']} (HMDB: {info.get('hmdb', 'N/A')})")
        else:
            print(f"[INFO] No metabolites detected in {args.filepath}")
    else:
        # 添加注释
        result = annotate_file(args.filepath, args.dry_run)
        
        if result.get("error"):
            print(f"[ERROR] {result['error']}")
            sys.exit(1)
        
        if result["added"] > 0:
            print(f"[OK] Added {result['added']} annotations")
            if result["pending"] > 0:
                print(f"[INFO] {result['pending']} metabolites queued for background lookup")
        elif result["found"]:
            print(f"[INFO] {len(result['found'])} metabolites already annotated")
        else:
            print(f"[INFO] No metabolites found")


if __name__ == "__main__":
    main()
