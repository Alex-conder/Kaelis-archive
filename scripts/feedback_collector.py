#!/usr/bin/env python3
"""
Kaelis 反馈收集器
收集使用者对自动执行的满意度反馈
"""
import json
import sys
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

# 反馈记录文件
FEEDBACK_FILE = Path(".kaelis-feedback.jsonl")


def record_feedback(
    action: str,
    filepath: str,
    result: dict,
    feedback: str,
    comment: Optional[str] = None
):
    """记录反馈"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "file": filepath,
        "execution_result": result,
        "feedback": feedback,  # "positive", "negative", "timeout", "ignored"
        "comment": comment
    }
    
    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] Failed to record feedback: {e}")


def collect_feedback(action: str, filepath: str, result: dict, timeout: int = 30) -> str:
    """
    收集反馈（非阻塞方式）
    
    Returns:
        反馈结果: "positive", "negative", "timeout"
    """
    if not result.get("success", False):
        # 执行失败时不收集反馈
        return "failed"
    
    feedback_event = threading.Event()
    feedback_result = ["timeout"]  # 默认超时
    
    def input_thread():
        try:
            # 显示提示
            print(f"\n[FEEDBACK] Auto-executed: {action}")
            print(f"[FEEDBACK] Was this helpful? (y/n/Enter=ignore)")
            
            # 使用 select 实现超时输入（Windows/Linux 兼容）
            user_input = get_input_with_timeout(timeout)
            
            if user_input:
                user_input = user_input.strip().lower()
                if user_input in ('y', 'yes'):
                    feedback_result[0] = "positive"
                    print("[FEEDBACK] Thanks for positive feedback!")
                elif user_input in ('n', 'no'):
                    feedback_result[0] = "negative"
                    comment = input("[FEEDBACK] What went wrong? (optional): ").strip()
                    print("[FEEDBACK] Thanks for feedback, will improve!")
                else:
                    feedback_result[0] = "ignored"
                    print("[FEEDBACK] Feedback ignored")
            else:
                print(f"[FEEDBACK] Timeout ({timeout}s), feedback skipped")
        
        except Exception as e:
            print(f"[WARN] Feedback collection error: {e}")
        
        finally:
            feedback_event.set()
    
    # 启动输入线程
    input_thread_obj = threading.Thread(target=input_thread, daemon=True)
    input_thread_obj.start()
    
    # 等待反馈或超时
    feedback_event.wait(timeout + 1)  # 稍微多等一点确保线程结束
    
    # 记录反馈
    final_feedback = feedback_result[0]
    record_feedback(action, filepath, result, final_feedback)
    
    return final_feedback


def get_input_with_timeout(timeout: int) -> Optional[str]:
    """
    带超时的输入（跨平台兼容）
    """
    import platform
    
    if platform.system() == "Windows":
        # Windows 使用 msvcrt
        try:
            import msvcrt
            import time
            
            start_time = time.time()
            result = []
            
            print("> ", end="", flush=True)
            
            while time.time() - start_time < timeout:
                if msvcrt.kbhit():
                    char = msvcrt.getche().decode('utf-8', errors='ignore')
                    if char == '\r':  # Enter
                        print()
                        return ''.join(result)
                    elif char == '\x08':  # Backspace
                        if result:
                            result.pop()
                            print(' \b', end="", flush=True)
                    else:
                        result.append(char)
                
                time.sleep(0.1)
            
            print()  # 换行
            return None
        except ImportError:
            # 回退到普通输入
            return input("> ")
    else:
        # Unix/Linux/Mac 使用 select
        try:
            import select
            
            print("> ", end="", flush=True)
            
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if ready:
                return sys.stdin.readline().strip()
            return None
        except Exception:
            # 回退到普通输入
            return input("> ")


def get_feedback_stats(days: int = 7) -> dict:
    """获取反馈统计"""
    if not FEEDBACK_FILE.exists():
        return {"total": 0, "positive": 0, "negative": 0, "timeout": 0, "by_action": {}}
    
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    stats = {
        "total": 0,
        "positive": 0,
        "negative": 0,
        "timeout": 0,
        "ignored": 0,
        "by_action": {}
    }
    
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                if entry["timestamp"] < cutoff:
                    continue
                
                feedback = entry.get("feedback", "unknown")
                action = entry.get("action", "unknown")
                
                stats["total"] += 1
                if feedback in stats:
                    stats[feedback] += 1
                
                # 按动作统计
                if action not in stats["by_action"]:
                    stats["by_action"][action] = {"total": 0, "positive": 0, "negative": 0}
                
                stats["by_action"][action]["total"] += 1
                if feedback in ("positive", "negative"):
                    stats["by_action"][action][feedback] += 1
            
            except json.JSONDecodeError:
                continue
    
    # 计算满意度
    if stats["total"] > 0:
        responded = stats["positive"] + stats["negative"]
        if responded > 0:
            stats["satisfaction_rate"] = stats["positive"] / responded
        else:
            stats["satisfaction_rate"] = 0
    else:
        stats["satisfaction_rate"] = 0
    
    return stats


def print_feedback_stats(days: int = 7):
    """打印反馈统计"""
    stats = get_feedback_stats(days)
    
    print(f"[KAELIS] Feedback Stats (Last {days} days)")
    print("=" * 60)
    
    if stats["total"] == 0:
        print("No feedback data available")
        return
    
    print(f"\nTotal feedback collected: {stats['total']}")
    print(f"  Positive: {stats['positive']} ({stats['positive']/stats['total']*100:.1f}%)")
    print(f"  Negative: {stats['negative']} ({stats['negative']/stats['total']*100:.1f}%)")
    print(f"  Timeout:  {stats['timeout']} ({stats['timeout']/stats['total']*100:.1f}%)")
    print(f"  Ignored:  {stats['ignored']} ({stats['ignored']/stats['total']*100:.1f}%)")
    
    responded = stats['positive'] + stats['negative']
    if responded > 0:
        print(f"\nSatisfaction rate: {stats['satisfaction_rate']*100:.1f}%")
    
    # 按动作统计
    if stats["by_action"]:
        print("\nBy action:")
        for action, action_stats in sorted(stats["by_action"].items(), key=lambda x: -x[1]["total"]):
            total = action_stats["total"]
            pos = action_stats["positive"]
            neg = action_stats["negative"]
            responded = pos + neg
            if responded > 0:
                rate = pos / responded * 100
                print(f"  {action}: {pos}/{responded} satisfied ({rate:.0f}%)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kaelis Feedback Collector")
    parser.add_argument("--stats", action="store_true", help="Show feedback statistics")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    parser.add_argument("--test", action="store_true", help="Test feedback collection")
    args = parser.parse_args()
    
    if args.test:
        # 测试模式
        print("Testing feedback collection...")
        result = {"success": True}
        feedback = collect_feedback("test_action", "test.py", result, timeout=10)
        print(f"Test feedback: {feedback}")
    
    elif args.stats:
        print_feedback_stats(args.days)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
