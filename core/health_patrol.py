"""
HealthPatrolEngine - 主动健康巡检 + 告警引擎

职责：
1. 定期巡检 KG 健康度、工具调用失败率、安全审查拦截率
2. 超过阈值时发送 webhook 通知
3. 支持巡检历史记录和趋势分析

对标：Anthropic 的部署前安全审计 + 实时监控最佳实践
"""

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PatrolAlert:
    """巡检告警"""
    alert_id: str
    patrol_id: str
    alert_type: str  # "kg_health", "tool_failure_rate", "safety_block_rate", "latency"
    severity: str  # "warning", "critical"
    message: str
    metric_value: float
    threshold: float
    created_at: str


@dataclass
class PatrolReport:
    """巡检报告"""
    patrol_id: str
    started_at: str
    completed_at: str
    duration_ms: int
    kg_health_score: Optional[float]
    tool_failure_rate: Optional[float]
    safety_block_rate: Optional[float]
    avg_latency_ms: Optional[float]
    alerts: List[PatrolAlert] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patrol_id": self.patrol_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "kg_health_score": self.kg_health_score,
            "tool_failure_rate": self.tool_failure_rate,
            "safety_block_rate": self.safety_block_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "alerts_count": len(self.alerts),
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "metric_value": a.metric_value,
                    "threshold": a.threshold,
                }
                for a in self.alerts
            ],
            "summary": self.summary,
        }


class HealthPatrolEngine:
    """
    健康巡检引擎。

    使用示例：
        patrol = HealthPatrolEngine()
        report = patrol.run_patrol()
        if report.alerts:
            patrol.send_webhook_alert(report.alerts[0])
    """

    DEFAULT_THRESHOLDS = {
        "kg_health_min": 0.5,           # KG 健康度低于 50% 告警
        "tool_failure_rate_max": 0.2,   # 工具失败率超过 20% 告警
        "safety_block_rate_max": 0.5,   # 安全拦截率超过 50% 告警（可能规则过严）
        "avg_latency_ms_max": 5000,     # 平均延迟超过 5s 告警
    }

    def __init__(self, db_path: Optional[str] = None, webhook_url: Optional[str] = None):
        self.db_path = db_path or str(Path("data/kaelis_graph.db").resolve())
        self.webhook_url = webhook_url or os.getenv("HEALTH_PATROL_WEBHOOK_URL")
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patrol_reports (
                    patrol_id TEXT PRIMARY KEY,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    duration_ms INTEGER,
                    kg_health_score REAL,
                    tool_failure_rate REAL,
                    safety_block_rate REAL,
                    avg_latency_ms REAL,
                    alerts_json TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patrol_alerts (
                    alert_id TEXT PRIMARY KEY,
                    patrol_id TEXT NOT NULL,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    metric_value REAL,
                    threshold REAL,
                    notified BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def run_patrol(self) -> PatrolReport:
        """执行一次完整巡检"""
        started = datetime.now()
        patrol_id = f"ptl_{uuid.uuid4().hex[:16]}"
        report = PatrolReport(
            patrol_id=patrol_id,
            started_at=started.isoformat(),
            completed_at=started.isoformat(),
            duration_ms=0,
            kg_health_score=None,
            tool_failure_rate=None,
            safety_block_rate=None,
            avg_latency_ms=None,
        )

        # 1. KG 健康度
        try:
            from core.kg_audit import get_kg_audit_engine
            kg_report = get_kg_audit_engine().run_audit()
            report.kg_health_score = kg_report.health_score
            if report.kg_health_score < self.thresholds["kg_health_min"]:
                report.alerts.append(PatrolAlert(
                    alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                    patrol_id=patrol_id,
                    alert_type="kg_health",
                    severity="critical" if report.kg_health_score < 0.3 else "warning",
                    message=f"KG 健康度过低: {report.kg_health_score:.2f} (阈值: {self.thresholds['kg_health_min']})",
                    metric_value=report.kg_health_score,
                    threshold=self.thresholds["kg_health_min"],
                    created_at=datetime.now().isoformat(),
                ))
        except Exception as e:
            logger.warning(f"[Patrol] KG health check failed: {e}")

        # 2. 工具调用失败率
        try:
            from core.tool_tracer import get_tool_tracer
            stats = get_tool_tracer().get_tool_stats(hours=24)
            total = stats.get("total_calls", 0)
            failed = stats.get("failed_calls", 0)
            report.tool_failure_rate = failed / max(total, 1)
            if report.tool_failure_rate > self.thresholds["tool_failure_rate_max"]:
                report.alerts.append(PatrolAlert(
                    alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                    patrol_id=patrol_id,
                    alert_type="tool_failure_rate",
                    severity="critical",
                    message=f"工具失败率过高: {report.tool_failure_rate:.1%} (阈值: {self.thresholds['tool_failure_rate_max']:.1%})",
                    metric_value=report.tool_failure_rate,
                    threshold=self.thresholds["tool_failure_rate_max"],
                    created_at=datetime.now().isoformat(),
                ))
        except Exception as e:
            logger.warning(f"[Patrol] Tool stats check failed: {e}")

        # 3. 安全拦截率
        try:
            from core.safety_audit import get_safety_audit_engine
            sa_stats = get_safety_audit_engine().get_statistics(hours=24)
            report.safety_block_rate = sa_stats.get("blocked_rate", 0.0)
            if report.safety_block_rate > self.thresholds["safety_block_rate_max"]:
                report.alerts.append(PatrolAlert(
                    alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                    patrol_id=patrol_id,
                    alert_type="safety_block_rate",
                    severity="warning",
                    message=f"安全拦截率异常: {report.safety_block_rate:.1%} (阈值: {self.thresholds['safety_block_rate_max']:.1%})",
                    metric_value=report.safety_block_rate,
                    threshold=self.thresholds["safety_block_rate_max"],
                    created_at=datetime.now().isoformat(),
                ))
        except Exception as e:
            logger.warning(f"[Patrol] Safety stats check failed: {e}")

        # 4. 平均延迟（从 decision_traces）
        try:
            from core.decision_trace import get_trace_engine
            traces = get_trace_engine().list_traces(limit=100)
            latencies = [t.total_duration_ms for t in traces if t.total_duration_ms > 0]
            if latencies:
                report.avg_latency_ms = sum(latencies) / len(latencies)
                if report.avg_latency_ms > self.thresholds["avg_latency_ms_max"]:
                    report.alerts.append(PatrolAlert(
                        alert_id=f"alt_{uuid.uuid4().hex[:12]}",
                        patrol_id=patrol_id,
                        alert_type="latency",
                        severity="warning",
                        message=f"平均延迟过高: {report.avg_latency_ms:.0f}ms (阈值: {self.thresholds['avg_latency_ms_max']}ms)",
                        metric_value=report.avg_latency_ms,
                        threshold=self.thresholds["avg_latency_ms_max"],
                        created_at=datetime.now().isoformat(),
                    ))
        except Exception as e:
            logger.warning(f"[Patrol] Latency check failed: {e}")

        completed = datetime.now()
        report.completed_at = completed.isoformat()
        report.duration_ms = int((completed - started).total_seconds() * 1000)

        # 生成摘要
        if report.alerts:
            critical = sum(1 for a in report.alerts if a.severity == "critical")
            warning = sum(1 for a in report.alerts if a.severity == "warning")
            report.summary = f"巡检完成，发现 {critical} 个严重告警，{warning} 个警告。"
        else:
            report.summary = "巡检完成，系统状态健康。"

        # 持久化
        self._persist_report(report)

        # 发送 webhook
        for alert in report.alerts:
            self.send_webhook_alert(alert)

        return report

    def _persist_report(self, report: PatrolReport):
        """持久化巡检报告"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO patrol_reports
                    (patrol_id, started_at, completed_at, duration_ms,
                     kg_health_score, tool_failure_rate, safety_block_rate,
                     avg_latency_ms, alerts_json, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.patrol_id,
                        report.started_at,
                        report.completed_at,
                        report.duration_ms,
                        report.kg_health_score,
                        report.tool_failure_rate,
                        report.safety_block_rate,
                        report.avg_latency_ms,
                        json.dumps([a.__dict__ for a in report.alerts], ensure_ascii=False, default=str),
                        report.summary,
                    ),
                )
                for alert in report.alerts:
                    conn.execute(
                        """
                        INSERT INTO patrol_alerts
                        (alert_id, patrol_id, alert_type, severity, message,
                         metric_value, threshold, notified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            alert.alert_id,
                            alert.patrol_id,
                            alert.alert_type,
                            alert.severity,
                            alert.message,
                            alert.metric_value,
                            alert.threshold,
                            1 if self.webhook_url else 0,
                        ),
                    )
        except Exception as e:
            logger.error(f"[Patrol] persist failed: {e}")

    def send_webhook_alert(self, alert: PatrolAlert) -> bool:
        """发送 webhook 告警通知"""
        if not self.webhook_url:
            logger.debug(f"[Patrol] No webhook configured, skipping alert {alert.alert_id}")
            return False

        payload = {
            "alert_id": alert.alert_id,
            "type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "metric_value": alert.metric_value,
            "threshold": alert.threshold,
            "timestamp": alert.created_at,
            "source": "kaelis-health-patrol",
        }

        try:
            import urllib.request
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"[Patrol] Webhook alert failed: {e}")
            return False

    def get_recent_reports(self, limit: int = 10) -> List[PatrolReport]:
        """获取最近巡检报告"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM patrol_reports ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                reports = []
                for r in rows:
                    alerts = json.loads(r["alerts_json"] or "[]")
                    reports.append(PatrolReport(
                        patrol_id=r["patrol_id"],
                        started_at=r["started_at"],
                        completed_at=r["completed_at"],
                        duration_ms=r["duration_ms"] or 0,
                        kg_health_score=r["kg_health_score"],
                        tool_failure_rate=r["tool_failure_rate"],
                        safety_block_rate=r["safety_block_rate"],
                        avg_latency_ms=r["avg_latency_ms"],
                        alerts=[PatrolAlert(**a) for a in alerts],
                        summary=r["summary"] or "",
                    ))
                return reports
        except Exception as e:
            logger.error(f"[Patrol] get reports failed: {e}")
            return []

    def update_threshold(self, key: str, value: float):
        """动态更新阈值"""
        if key in self.thresholds:
            self.thresholds[key] = value
            logger.info(f"[Patrol] Threshold {key} updated to {value}")


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------
_patrol_engine_instance: Optional[HealthPatrolEngine] = None


def get_health_patrol_engine() -> HealthPatrolEngine:
    global _patrol_engine_instance
    if _patrol_engine_instance is None:
        _patrol_engine_instance = HealthPatrolEngine()
    return _patrol_engine_instance
