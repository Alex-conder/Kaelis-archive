"""
自动化质检调度器 (APScheduler)

基于 KG Flywheel 路线图 选项3 实现：
- 每天凌晨 2 点执行全量质检
- 发现冲突实体时推送告警
- 生成质检报告并存入 L2 记忆

使用方式：
    from core.monitoring.scheduler import QualityScheduler
    scheduler = QualityScheduler()
    scheduler.start()
    
    # 手动触发
    scheduler.run_inspection_now(check_type='full')
"""

import logging
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 支持直接运行
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


class QualityScheduler:
    """
    知识图谱质量检查调度器
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else Path("data/kaelis_graph.db")
        self.scheduler = None
        self._initialized = False
    
    def _init_scheduler(self):
        """延迟初始化调度器"""
        if self._initialized:
            return
        
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            
            self.scheduler = BackgroundScheduler()
            self._initialized = True
            logger.info("QualityScheduler initialized")
        except ImportError:
            logger.warning("APScheduler not installed, scheduling disabled")
            self.scheduler = None
    
    def start(self):
        """启动调度器（幂等：已运行则忽略）"""
        self._init_scheduler()
        
        if not self.scheduler:
            return
        
        if self.scheduler.running:
            logger.info("QualityScheduler already running, skipping start")
            return
        
        # 加载进化配置
        evolution_config = self._load_evolution_config()
        
        try:
            from apscheduler.triggers.cron import CronTrigger
            
            # 每天凌晨 2 点执行全量质检
            self.scheduler.add_job(
                self._run_scheduled_inspection,
                CronTrigger(hour=2, minute=0),
                id='daily_kg_inspection',
                replace_existing=True,
                name='Daily KG Quality Inspection'
            )
            
            # 每小时更新一次指标仪表盘
            self.scheduler.add_job(
                self._update_metrics_gauges,
                'interval',
                minutes=60,
                id='hourly_metrics_update',
                replace_existing=True,
                name='Hourly Metrics Update'
            )
            
            # 每日自进化任务
            if evolution_config.get('evolution', {}).get('enabled', True):
                daily_time = evolution_config.get('evolution', {}).get('daily_time', '02:00')
                hour, minute = map(int, daily_time.split(':'))
                self.scheduler.add_job(
                    self._run_evolution_task,
                    CronTrigger(hour=hour, minute=minute),
                    id='daily_evolution',
                    replace_existing=True,
                    name='Daily Self-Evolution'
                )
                logger.info(f"Daily evolution task scheduled at {daily_time}")
            
            # 每周技能生成任务
            if evolution_config.get('evolution', {}).get('skill_generation', {}).get('enabled', True):
                weekly_time = evolution_config.get('evolution', {}).get('skill_generation', {}).get('weekly_time', '03:00')
                weekly_day = evolution_config.get('evolution', {}).get('skill_generation', {}).get('weekly_day', 'sunday')
                hour, minute = map(int, weekly_time.split(':'))
                day_of_week = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                               'friday': 4, 'saturday': 5, 'sunday': 6}.get(weekly_day.lower(), 6)
                self.scheduler.add_job(
                    self._run_skill_generation,
                    CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
                    id='weekly_skill_generation',
                    replace_existing=True,
                    name='Weekly Skill Generation'
                )
                logger.info(f"Weekly skill generation scheduled on {weekly_day} at {weekly_time}")
            
            # 健康检查心跳任务（每 5 分钟）
            self.scheduler.add_job(
                self._run_health_check,
                'interval',
                minutes=5,
                id='health_check_heartbeat',
                replace_existing=True,
                name='Health Check Heartbeat'
            )
            logger.info("Health check heartbeat scheduled every 5 minutes")
            
            self.scheduler.start()
            logger.info("QualityScheduler started")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
    
    def stop(self):
        """优雅停止调度器"""
        if self.scheduler and self.scheduler.running:
            try:
                self.scheduler.shutdown(wait=False)
                logger.info("QualityScheduler stopped")
            except Exception as e:
                logger.warning(f"Failed to stop scheduler: {e}")
    
    def _load_evolution_config(self) -> Dict[str, Any]:
        """加载进化调度配置"""
        import yaml
        config_path = Path("config/evolution.yaml")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load evolution config: {e}")
        return {}
    
    def _run_evolution_task(self):
        """每日自进化任务：扫描 L2 记忆，触发技能生成检查"""
        logger.info("Scheduled evolution task triggered")
        try:
            from core.memory_manager_v2 import get_memory_manager
            from core.skill_generator import get_skill_generator
            
            mm = get_memory_manager()
            generator = get_skill_generator()
            
            # 读取最近 20 条 L2 执行记录
            recent = mm.search("L2", "execution", top_k=20)
            if not recent:
                logger.info("No recent executions found for evolution")
                return
            
            # 按 task_type 分组
            by_task: Dict[str, list] = {}
            for r in recent:
                task_type = r.get("metadata", {}).get("task_type", "unknown")
                by_task.setdefault(task_type, []).append({
                    "success": r.get("metadata", {}).get("status") == "success",
                    "confidence": r.get("metadata", {}).get("confidence", 0.0),
                    "params": r.get("value", {}).get("best_params", {}),
                    "result": r.get("value", {}).get("best_result", {}),
                })
            
            for task_type, executions in by_task.items():
                result = generator.check_and_generate(task_type, executions)
                if result:
                    logger.info(f"Evolution triggered for {task_type}: {result}")
                else:
                    logger.debug(f"Evolution threshold not met for {task_type}")
                    
        except Exception as e:
            logger.error(f"Evolution task failed: {e}")
    
    def _run_skill_generation(self):
        """每周技能生成任务：为高频 task_type 生成 SKILL.md"""
        logger.info("Scheduled skill generation task triggered")
        try:
            from core.memory_manager_v2 import get_memory_manager
            from core.skill_generator import get_skill_generator
            
            mm = get_memory_manager()
            generator = get_skill_generator()
            
            # 读取最近 50 条成功记录
            recent = mm.search("L2", "execution", top_k=50)
            successful = [r for r in recent if r.get("metadata", {}).get("status") == "success"]
            
            if len(successful) < generator.trigger_threshold:
                logger.info(f"Not enough successful executions for skill generation ({len(successful)}/{generator.trigger_threshold})")
                return
            
            # 为最近的一条成功记录生成技能文档
            latest = successful[0]
            doc_path = generator.generate(latest.get("value", {}), skill_id=latest.get("key"))
            if doc_path:
                logger.info(f"Skill document generated: {doc_path}")
            else:
                logger.debug("Skill generation returned None")
                
        except Exception as e:
            logger.error(f"Skill generation task failed: {e}")
    
    def _run_health_check(self):
        """健康检查心跳任务：检查核心组件可用性并记录状态"""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "scheduler": "running" if self.scheduler and self.scheduler.running else "stopped",
                "components": {}
            }
            
            # 检查数据库可访问性
            try:
                import sqlite3
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("SELECT 1")
                conn.close()
                status["components"]["graph_db"] = "healthy"
            except Exception:
                status["components"]["graph_db"] = "unhealthy"
            
            # 检查内存管理器
            try:
                from core.memory_manager_v2 import get_memory_manager
                mm = get_memory_manager()
                status["components"]["memory_manager"] = "healthy" if mm else "unhealthy"
            except Exception:
                status["components"]["memory_manager"] = "unhealthy"
            
            overall = "healthy" if all(v == "healthy" for v in status["components"].values()) else "degraded"
            status["overall"] = overall
            
            if overall == "degraded":
                logger.warning(f"Health check heartbeat: {overall} — {status['components']}")
            else:
                logger.debug(f"Health check heartbeat: {overall}")
            
            # 将健康状态存入 L2 记忆（保留最近 100 条）
            try:
                from core.memory_manager_v2 import get_memory_manager
                mm = get_memory_manager()
                if mm:
                    mm.store("L2", "health_check", str(status), metadata={
                        "source": "scheduler",
                        "event_type": "health_check",
                        "overall": overall
                    })
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Health check heartbeat failed: {e}")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("QualityScheduler stopped")
    
    def run_inspection_now(self, check_type: str = 'full') -> Dict[str, Any]:
        """
        立即执行质检（同步接口，适合手动触发）
        
        Args:
            check_type: full, quick, entity, relation
            
        Returns:
            Dict: 质检结果
        """
        logger.info(f"Running manual inspection: {check_type}")
        return self._execute_inspection(check_type)
    
    def _run_scheduled_inspection(self):
        """调度器回调（在后台线程中执行）"""
        logger.info("Scheduled inspection triggered")
        try:
            result = self._execute_inspection('full')
            
            # 发现问题时告警
            issues = result.get('issues', [])
            if issues:
                self._send_alert(
                    f"KG 质检发现 {len(issues)} 个问题",
                    result
                )
            
            # 存入 L2 记忆
            self._save_report_to_memory(result)
            
        except Exception as e:
            logger.error(f"Scheduled inspection failed: {e}")
            self._send_alert("KG 质检执行失败", {"error": str(e)})
    
    def _execute_inspection(self, check_type: str) -> Dict[str, Any]:
        """
        执行实际质检逻辑
        
        Args:
            check_type: 检查类型
            
        Returns:
            Dict: 检查结果
        """
        import sqlite3
        from pathlib import Path
        from core.monitoring.metrics import KG_METRICS
        
        start_time = datetime.now().isoformat()
        issues = []
        
        if not self.db_path.exists():
            return {
                "check_type": check_type,
                "status": "skipped",
                "reason": "Database not found",
                "timestamp": start_time
            }
        
        with sqlite3.connect(str(self.db_path)) as conn:
            # 1. 实体名称冲突检查
            if check_type in ('full', 'entity'):
                cursor = conn.execute("""
                    SELECT name, COUNT(*) as cnt, GROUP_CONCAT(type) as types
                    FROM kg_entities
                    GROUP BY name
                    HAVING cnt > 1
                """)
                conflicts = cursor.fetchall()
                for name, count, types in conflicts:
                    issues.append({
                        "type": "entity_conflict",
                        "entity": name,
                        "count": count,
                        "types": types,
                        "severity": "high"
                    })
            
            # 2. 孤立实体检查（没有关系的实体）
            if check_type in ('full', 'relation'):
                cursor = conn.execute("""
                    SELECT e.name, e.type
                    FROM kg_entities e
                    LEFT JOIN kg_triples t ON e.name = t.subject OR e.name = t.object
                    WHERE t.id IS NULL
                    LIMIT 100
                """)
                orphans = cursor.fetchall()
                for name, etype in orphans:
                    issues.append({
                        "type": "orphan_entity",
                        "entity": name,
                        "entity_type": etype,
                        "severity": "low"
                    })
            
            # 3. 低置信度关系检查
            if check_type in ('full', 'relation'):
                cursor = conn.execute("""
                    SELECT subject, predicate, object, confidence
                    FROM kg_triples
                    WHERE confidence < 0.5
                    LIMIT 50
                """)
                low_conf = cursor.fetchall()
                for subj, pred, obj, conf in low_conf:
                    issues.append({
                        "type": "low_confidence_relation",
                        "triple": f"({subj})-[:{pred}]->({obj})",
                        "confidence": conf,
                        "severity": "medium"
                    })
            
            # 4. 统计信息
            cursor = conn.execute("SELECT COUNT(*) FROM kg_entities")
            entity_count = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM kg_triples")
            triple_count = cursor.fetchone()[0]
            
            # 计算质量分
            quality_score = self._calculate_quality_score(entity_count, triple_count, len(issues))
            
            # 更新仪表盘
            KG_METRICS.update_entity_count(entity_count)
            KG_METRICS.update_triple_count(triple_count)
            KG_METRICS.update_quality_score(quality_score)
            KG_METRICS.inspection_total.labels(check_type=check_type).inc()
            
            result = {
                "check_type": check_type,
                "status": "completed",
                "timestamp": start_time,
                "completed_at": datetime.now().isoformat(),
                "summary": {
                    "entity_count": entity_count,
                    "triple_count": triple_count,
                    "quality_score": quality_score,
                    "issues_found": len(issues)
                },
                "issues": issues[:20]  # 最多返回 20 个
            }
            
            logger.info(f"Inspection completed: {len(issues)} issues, score={quality_score:.1f}")
            return result
    
    def _calculate_quality_score(self, entity_count: int, triple_count: int, issue_count: int) -> float:
        """计算知识图谱质量分数 (0-100)"""
        base_score = 100.0
        
        # 实体-关系比例扣分
        if entity_count > 0:
            ratio = triple_count / entity_count
            if ratio < 0.5:
                base_score -= 10
            elif ratio > 10:
                base_score -= 5
        
        # 问题扣分
        base_score -= min(30, issue_count * 2)
        
        return max(0, min(100, base_score))
    
    def _update_metrics_gauges(self):
        """定期更新指标仪表盘"""
        try:
            self._execute_inspection('quick')
        except Exception as e:
            logger.debug(f"Metrics update failed: {e}")
    
    def _save_report_to_memory(self, result: Dict):
        """将质检报告存入 L2 记忆"""
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            
            report_key = f"kg_inspection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            mm.write(
                layer="L2",
                key=report_key,
                value=result,
                metadata={
                    "source": "quality_scheduler",
                    "check_type": result.get("check_type"),
                    "quality_score": result.get("summary", {}).get("quality_score")
                }
            )
        except Exception as e:
            logger.warning(f"Failed to save report to memory: {e}")
    
    def _send_alert(self, message: str, data: Dict):
        """发送告警（当前仅记录日志，可扩展为钉钉/邮件/企业微信）"""
        logger.warning(f"[ALERT] {message}")
        
        # TODO: 接入外部告警通道
        # - 钉钉机器人
        # - 企业微信
        # - 邮件
        # - Webhook
        
        # 同时写入 L2 作为事件记录
        try:
            from core.memory_manager_v2 import get_memory_manager
            mm = get_memory_manager()
            mm.write(
                layer="L2",
                key=f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                value={"message": message, "data": data},
                metadata={"source": "alert", "level": "warning"}
            )
        except Exception as e:
            logger.debug(f"Alert memory write failed: {e}")


# 全局实例
_scheduler_instance: Optional[QualityScheduler] = None


def get_quality_scheduler() -> QualityScheduler:
    """获取全局调度器"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = QualityScheduler()
    return _scheduler_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试质检调度器 ===")
    scheduler = QualityScheduler()
    
    # 手动执行质检
    result = scheduler.run_inspection_now('full')
    print(f"Inspection result: {result['status']}")
    print(f"Summary: {result.get('summary')}")
    print(f"Issues: {len(result.get('issues', []))}")
    
    print("\n[OK] QualityScheduler test completed")
