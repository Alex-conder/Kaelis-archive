# Kaelis 项目 Makefile
# 版本: 8.1.0 (ACK v2.1 - Forward-Deterministic Kernel)

.PHONY: help init check fix physician loop telemetry daily suggest-context suggest-for suggest-stats daemon daemon-bg daemon-stop daemon-status agent agent-dry agent-bg agent-stop agent-log agent-predict feedback-stats feedback-test check-incr check-lines violation-stats metabolite-detect metabolite-annotate metabolite-dry metabolite-stats stats learn-decision show-model crystallize show-rules export-rules analyze-patterns predict-for ack-status ack-evolve ack-resilience ack-meta-report ack-kb-replay ack-rescue ack-lifeboat-stats decide debate consensus-status idea idea-v2 idea-dry idea-sandbox idea-rollback v2-status team-init team-sync learn symbols template-review sync-all sync-backend sync-frontend sync-config codegen audit

# 默认目标
help:
	@echo "Kaelis Unified CLI v1.0 - Forward-Deterministic Kernel"
	@echo "======================================================="
	@echo ""
	@echo "推荐使用 kaelis 命令:"
	@echo "  kaelis intent \"<目标描述>\"     启动完整前馈流水�?
	@echo "  kaelis plan \"<目标描述>\"       仅生成执行计�?
	@echo "  kaelis op file add <路径>       文件操作"
	@echo "  kaelis profile                   查看认知画像"
	@echo "  kaelis status                    系统状�?
	@echo "  kaelis guide                     导航指南"
	@echo ""
	@echo "快捷方式 (Makefile 兼容):"
	@echo "  make intent DESC='...'         等同�? kaelis intent \"...\""
	@echo "  make plan DESC='...'           等同�? kaelis plan \"...\""
	@echo "  make status                    等同�? kaelis status"
	@echo ""
	@echo "🌌 ACK v2.0 (遗留):"
	@echo "  make decide GOAL='...'         多角色共识引�?
	@echo "  make debate GOAL='...'         辩论模式"
	@echo "  make consensus-status          v2.0 状�?
	@echo ""
	@echo "🚀 其他:"
	@echo "  make init              初始化开发环�?
	@echo "  make idea              智能需求落地工�?
	@echo "  make physician         项目全面体检"
	@echo ""
	@echo "🔮 预测模式 (无标记自动执�?:"
	@echo "  make analyze-patterns  分析执行模式"
	@echo "  make predict-for       预测文件操作 (FILE=path)"
	@echo "  make agent-predict     启动预测模式 Agent"
	@echo ""
	@echo "💎 规则固化 (自进�?:"
	@echo "  make crystallize       固化高置信度规则 (>95%%)"
	@echo "  make show-rules        显示已固化规�?
	@echo "  make export-rules      导出规则�?Agent"
	@echo ""
	@echo "🧠 决策学习 (反馈闭环):"
	@echo "  make learn-decision    从执行历史学习决策模�?
	@echo "  make show-model        显示当前决策模型"
	@echo ""
	@echo "🧠 ACK - Autonomous Cognitive Kernel:"
	@echo "  make ack-status        查看 ACK 完整状�?
	@echo "  make ack-evolve        运行完整进化闭环"
	@echo "  make ack-resilience    捕获韧性上下文"
	@echo "  make ack-meta-report   元认知报�?
	@echo "  make ack-kb-replay     知识库重放验�?
	@echo "  make ack-rescue        救生艇救�?
	@echo "  make ack-lifeboat-stats 救生艇统�?
	@echo ""
	@echo "�?自主执行 Agent (v6.0 - All Features):"
	@echo "  make agent             前台启动 Agent (全功�?"
	@echo "  make agent-dry         预览模式"
	@echo "  make agent-predict     仅预测模�?
	@echo "  make agent-bg          后台启动"
	@echo "  make agent-stop        停止 Agent"
	@echo "  make agent-log         查看执行日志"
	@echo "  make stats             查看所有统�?
	@echo ""
	@echo "💬 使用者反馈闭�?"
	@echo "  make feedback-stats    查看反馈统计"
	@echo "  make feedback-test     测试反馈收集"
	@echo ""
	@echo "🔍 实时架构检�?(增量):"
	@echo "  make check-incr        增量检查文�?(FILE=path)"
	@echo "  make check-lines       检查指定行 (LINES=1,2,3)"
	@echo "  make violation-stats   查看违规统计"
	@echo ""
	@echo "🧬 代谢物知识主动推�?(领域知识集成):"
	@echo "  make metabolite-detect   检测代码中的代谢物"
	@echo "  make metabolite-annotate 自动添加代谢物注�?
	@echo "  make metabolite-dry      预览注释效果"
	@echo "  make metabolite-stats    查看注释统计"
	@echo ""
	@echo "🤖 主动建议 Agent (迭代�?:"
	@echo "  make daemon            前台启动守护进程"
	@echo "  make daemon-bg         后台启动守护进程"
	@echo "  make daemon-stop       停止守护进程"
	@echo "  make daemon-status     查看守护进程状�?
	@echo ""
	@echo "🧠 上下文感�?(迭代一):"
	@echo "  make suggest-context   分析当前目录并给出建�?
	@echo "  make suggest-for       分析指定文件 (FILE=path)"
	@echo "  make suggest-stats     查看建议统计"
	@echo ""
	@echo "📊 遥测与闭�?"
	@echo "  make telemetry         查看遥测记录"
	@echo "  make telemetry-stats   查看遥测统计"
	@echo "  make daily             每日摘要"
	@echo "  make loop              运行生态闭�?

# 初始�?
init:
	@echo "🚀 初始�?Kaelis 开发环�?.."
	@pip install -r requirements.txt -q 2>nul || echo "依赖安装跳过"
	@python scripts/init_telemetry.py 2>nul || echo "遥测初始化跳�?
	@pre-commit install 2>nul || echo "pre-commit 未安装，跳过 Git Hook"
	@echo "�?初始化完�?

# 项目体检
physician:
	@echo "🏥 运行 Kaelis 项目体检..."
	@python scripts/kaelis_physician.py 2>nul || echo "体检脚本未找�?

# 生态闭�?
loop:
	@echo "🔄 运行生态闭�?.."
	@make report 2>nul || echo "周报生成未配�?
	@make suggest 2>nul || echo "建议生成未配�?
	@echo "�?闭环完成"

report:
	@echo "📊 生成周报..."
	@python scripts/weekly_report.py 2>nul || echo "周报脚本未找�?

suggest:
	@echo "💡 生成优化建议..."
	@python scripts/optimization_suggester.py 2>nul || echo "建议器未找到"

# ============================================
# 🌌 ACK v2.0 - 多角色共识引�?
# ============================================

decide:
	@if "$(GOAL)"=="" (echo "用法: make decide GOAL="你的目标描述"" && exit /b 1)
	@echo 🌌 启动 ACK v2.0 多角色决策流�?..
	@echo 目标: $(GOAL)
	@echo.
	@python scripts/consensus_engine.py --goal "$(GOAL)"

debate:
	@if "$(GOAL)"=="" (echo "用法: make debate GOAL="你的目标描述"" && exit /b 1)
	@echo 🗣�? 启动 ACK v2.0 辩论模式...
	@echo 目标: $(GOAL)
	@echo.
	@python scripts/consensus_engine.py --debate --goal "$(GOAL)"

# ============================================================================
# 🔧 Kaelis Unified CLI 快捷方式
# ============================================================================

# 核心命令快捷方式
intent:
	@if "$(DESC)"=="" (echo "用法: make intent DESC="你的需求描�?" && exit /b 1)
	@python scripts/kaelis intent "$(DESC)"

plan:
	@if "$(DESC)"=="" (echo "用法: make plan DESC="你的需求描�?" && exit /b 1)
	@python scripts/kaelis plan "$(DESC)"

status:
	@python scripts/kaelis status

guide:
	@python scripts/kaelis guide

profile:
	@python scripts/kaelis profile

# ============================================================================
# 🔧 ACK v2.1 - 前馈确定性内�?(遗留快捷方式)
# ============================================================================

v2-status:
	@echo 🔧 ACK v2.1 前馈确定性内核状�?
	@echo ===================================
	@echo.
	@echo [核心组件]
	@if exist config\intent_schema.json (echo   [OK] intent_schema.json) else (echo   [MISSING] intent_schema.json)
	@if exist config\action_templates.yaml (echo   [OK] action_templates.yaml) else (echo   [MISSING] action_templates.yaml)
	@echo.
	@echo [执行引擎]
	@if exist scripts\idea_factory_v2.py (echo   [OK] idea_factory_v2.py) else (echo   [MISSING] idea_factory_v2.py)
	@if exist scripts\rule_engine.py (echo   [OK] rule_engine.py) else (echo   [MISSING] rule_engine.py)
	@if exist scripts\hallucination_detector.py (echo   [OK] hallucination_detector.py) else (echo   [MISSING] hallucination_detector.py)
	@if exist scripts\sandbox_runner.py (echo   [OK] sandbox_runner.py) else (echo   [MISSING] sandbox_runner.py)
	@if exist scripts\atomic_executor.py (echo   [OK] atomic_executor.py) else (echo   [MISSING] atomic_executor.py)
	@echo.
	@echo 使用说明:
	@echo   make idea-v2 DESC="添加 API 超时配置"
	@echo   make idea-dry DESC="修改数据库模�?
	@echo   make idea-sandbox DESC="添加测试用例"

idea-v2:
	@if "$(DESC)"=="" (echo "用法: make idea-v2 DESC="你的需求描�?" && exit /b 1)
	@python scripts/idea_factory_v2.py "$(DESC)"

idea-dry:
	@if "$(DESC)"=="" (echo "用法: make idea-dry DESC="你的需求描�?" && exit /b 1)
	@python scripts/idea_factory_v2.py "$(DESC)" --dry-run

idea-sandbox:
	@if "$(DESC)"=="" (echo "用法: make idea-sandbox DESC="你的需求描�?" && exit /b 1)
	@python scripts/idea_factory_v2.py "$(DESC)" --skip-sandbox

idea-rollback:
	@if "$(EXEC_ID)"=="" (echo "用法: make idea-rollback EXEC_ID=exec_20260101_120000_abc123" && exit /b 1)
	@python scripts/atomic_executor.py --rollback $(EXEC_ID)

# ============================================================================
# 🌌 ACK v2.0 - 多角色共识引�?
# ============================================================================

consensus-status:
	@echo 🌌 ACK v2.0 共识引擎状�?
	@echo ==========================
	@echo.
	@echo [角色配置]
	@if exist config\roles.yaml (echo   [OK] roles.yaml) else (echo   [MISSING] roles.yaml)
	@if exist config\cost_profile.yaml (echo   [OK] cost_profile.yaml) else (echo   [MISSING] cost_profile.yaml)
	@echo.
	@echo [共识引擎]
	@if exist scripts\consensus_engine.py (echo   [OK] consensus_engine.py) else (echo   [MISSING] consensus_engine.py)
	@if exist scripts\economist.py (echo   [OK] economist.py) else (echo   [MISSING] economist.py)
	@if exist scripts\external_scanner.py (echo   [OK] external_scanner.py) else (echo   [MISSING] external_scanner.py)
	@echo.
	@echo 使用说明:
	@echo   make decide GOAL="实现用户认证系统"
	@echo   make debate GOAL="选择数据库方�?

# ============================================
# 🧠 上下文感知建议器 (迭代一)
# ============================================

suggest-context:
	@echo "🔍 分析当前目录..."
	@python -c "
import os
from scripts.context_aware_suggester import ContextAwareSuggester
suggester = ContextAwareSuggester()
for root, dirs, files in os.walk('.'):
    for f in files[:5]:
        filepath = os.path.join(root, f)
        suggestion = suggester.analyze(filepath)
        if suggestion:
            print(suggester.format_output(suggestion))
            break
    break
"

suggest-for:
	@if not defined FILE (echo "用法: make suggest-for FILE=path/to/file.py" && exit /b 1)
	@python scripts/context_aware_suggester.py $(FILE)

suggest-stats:
	@echo "📊 建议统计:"
	@python scripts/context_aware_suggester.py --stats

# ============================================
# 📊 遥测系统
# ============================================

telemetry:
	@echo "📊 最近遥测记�?"
	@if exist .kaelis-telemetry.jsonl (
		powershell -Command "Get-Content .kaelis-telemetry.jsonl | Select-Object -Last 10"
	) else (
		echo "遥测文件不存在，请先运行 make init"
	)

telemetry-stats:
	@echo "📈 遥测统计:"
	@python -c "
from scripts.telemetry import get_telemetry_summary
print(get_telemetry_summary(days=7))
"

daily:
	@echo "📅 Kaelis 每日摘要"
	@echo "===================="
	@echo ""
	@echo "🫀 遥测统计:"
	@python -c "from scripts.telemetry import get_telemetry_summary; print(get_telemetry_summary(days=1))"
	@echo ""
	@echo "💡 建议: 运行 'make physician' 进行全面体检"

# ============================================
# 🎯 Idea Factory
# ============================================

idea:
	@if not defined DESC (echo "用法: make idea DESC='你的需求描�?" && exit /b 1)
	@python scripts/idea_factory.py "$(DESC)"

# ============================================
# 🔧 变更管理
# ============================================

change-checkpoint:
	@if not defined FILES (echo "用法: make change-checkpoint FILES='file1.py file2.py'" && exit /b 1)
	@python scripts/solo_change.py --checkpoint $(FILES)

change-rollback:
	@if not defined CHECKPOINT (echo "用法: make change-rollback CHECKPOINT=checkpoint_id" && exit /b 1)
	@python scripts/solo_change.py --rollback $(CHECKPOINT)

change-list:
	@python scripts/solo_change.py --list

# ============================================
# �?自主执行 Agent (迭代�?
# ============================================

agent:
	@python scripts/kaelis_agent.py

agent-dry:
	@python scripts/kaelis_agent.py --dry-run

agent-bg:
	@powershell -ExecutionPolicy Bypass -Command "Start-Process python -ArgumentList 'scripts/kaelis_agent.py' -WindowStyle Hidden"

agent-stop:
	@python scripts/kaelis_agent.py --stop

agent-log:
	@if exist .kaelis-auto-exec.jsonl (
		@powershell -Command "Get-Content .kaelis-auto-exec.jsonl | Select-Object -Last 20"
	) else (
		@echo [INFO] No execution log yet
	)

feedback-stats:
	@python scripts/feedback_collector.py --stats

feedback-test:
	@python scripts/feedback_collector.py --test

# ============================================
# 🔍 实时架构检�?(增量)
# ============================================

check-incr:
	@if not defined FILE (echo "Usage: make check-incr FILE=path/to/file.py" && exit /b 1)
	@python scripts/incremental_check.py $(FILE)

check-lines:
	@if not defined FILE (echo "Usage: make check-lines FILE=path/to/file.py LINES=1,2,3" && exit /b 1)
	@python scripts/incremental_check.py $(FILE) --lines $(LINES)

violation-stats:
	@python scripts/incremental_check.py --stats

# ============================================
# 🧬 代谢物知识主动推�?(领域知识集成)
# ============================================

metabolite-detect:
	@if not defined FILE (echo "Usage: make metabolite-detect FILE=path/to/file.py" && exit /b 1)
	@python scripts/metabolite_annotator.py $(FILE) --detect

metabolite-annotate:
	@if not defined FILE (echo "Usage: make metabolite-annotate FILE=path/to/file.py" && exit /b 1)
	@python scripts/metabolite_annotator.py $(FILE)

metabolite-dry:
	@if not defined FILE (echo "Usage: make metabolite-dry FILE=path/to/file.py" && exit /b 1)
	@python scripts/metabolite_annotator.py $(FILE) --dry-run

metabolite-stats:
	@python scripts/metabolite_annotator.py --stats

# ============================================
# 🧠 ACK - Autonomous Cognitive Kernel
# ============================================

ack-status:
	@echo "🧠 Kaelis ACK Status"
	@echo "===================="
	@echo ""
	@echo "[ACK v2.0 共识引擎]"
	@if exist config/roles.yaml (echo "  �?角色配置") else (echo "  �?角色配置缺失")
	@if exist config/cost_profile.yaml (echo "  �?成本配置") else (echo "  �?成本配置缺失")
	@if exist scripts/consensus_engine.py (echo "  �?共识引擎") else (echo "  �?共识引擎缺失")
	@echo ""
	@echo "[Resilience Context]"
	@python scripts/resilience_context.py --check 2>nul || echo "  Not available"
	@echo ""
	@echo "[Metacognitive Monitor]"
	@python scripts/metacognitive_monitor.py --diagnostic 2>nul || echo "  Not available"
	@echo ""
	@echo "[Knowledge Base]"
	@if exist config/fault_kb.yaml (echo "  KB exists") else (echo "  KB not found")
	@echo ""
	@echo "[Lifeboat]"
	@python scripts/kaelis_rescue.py --check 2>nul || echo "  Not available"
	@echo ""
	@echo "[Telemetry]"
	@if exist .kaelis-telemetry.jsonl (powershell -Command "Get-Content .kaelis-telemetry.jsonl | Measure-Object | Select-Object -ExpandProperty Count" 2>nul && echo " events") else (echo "  No events")

ack-evolve:
	@echo "🔄 Running ACK Evolution Cycle..."
	@echo "1. Capturing resilience context..."
	@python scripts/resilience_context.py --capture > .ack-snapshot.json 2>nul
	@echo "2. Calibrating metacognition..."
	@if exist config/cognitive_profile.yaml (python scripts/metacognitive_monitor.py --calibrate config/cognitive_profile.yaml 2>nul) else (echo "   No profile to calibrate")
	@echo "3. Replaying knowledge base..."
	@python scripts/kb_replay.py --run 2>nul || echo "   KB replay skipped"
	@echo "4. Backing up with lifeboat..."
	@python scripts/kaelis_rescue.py --backup 2>nul
	@echo "�?Evolution cycle complete"

ack-resilience:
	@python scripts/resilience_context.py --capture

ack-meta-report:
	@python scripts/metacognitive_monitor.py --report

ack-kb-replay:
	@python scripts/kb_replay.py --run

ack-rescue:
	@python scripts/kaelis_rescue.py --rescue --learn

ack-lifeboat-stats:
	@python scripts/kaelis_rescue.py --stats

# ============================================
# 📊 统一统计面板
# ============================================

stats:
	@echo "📊 Kaelis Agent Statistics"
	@echo "==========================="
	@echo ""
	@echo "[Telemetry]"
	@if exist .kaelis-telemetry.jsonl (@powershell -Command "Get-Content .kaelis-telemetry.jsonl | Measure-Object | Select-Object -ExpandProperty Count" 2>nul && echo " events recorded") else (@echo "  No telemetry yet")
	@echo ""
	@echo "[Auto Execution]"
	@if exist .kaelis-auto-exec.jsonl (@powershell -Command "Get-Content .kaelis-auto-exec.jsonl | Measure-Object | Select-Object -ExpandProperty Count" 2>nul && echo " executions") else (@echo "  No executions yet")
	@echo ""
	@echo "[Feedback]"
	@if exist .kaelis-feedback.jsonl (@powershell -Command "Get-Content .kaelis-feedback.jsonl | Measure-Object | Select-Object -ExpandProperty Count" 2>nul && echo " feedbacks") else (@echo "  No feedback yet")
	@echo ""
	@echo "Run specific stats:"
	@echo "  make feedback-stats"
	@echo "  make violation-stats"
	@echo "  make metabolite-stats"
	@echo "  make consensus-status"

# ============================================
# 🧠 决策学习 (反馈闭环)
# ============================================

learn-decision:
	@echo "🧠 Learning from execution history..."
	@python scripts/decision_learner.py

show-model:
	@if exist config/decision_model.yaml (
		@echo [CURRENT DECISION MODEL]
		@type config/decision_model.yaml
	) else (
		@echo [INFO] No decision model yet. Run 'make learn-decision' first.
	)

# ============================================
# 💎 规则固化 (高置信度 �?确定性规�?
# ============================================

crystallize:
	@echo "💎 Crystallizing high-confidence rules..."
	@python scripts/rule_crystallizer.py

show-rules:
	@if exist config/auto_rules.yaml (
		@echo [CRYSTALLIZED RULES]
		@type config/auto_rules.yaml
	) else (
		@echo [INFO] No crystallized rules yet. Run 'make crystallize' first.
	)

export-rules:
	@echo "📤 Exporting rules for Agent..."
	@python scripts/rule_crystallizer.py --export

# ============================================
# 🔮 预测模式 (无标记自动执�?
# ============================================

analyze-patterns:
	@echo "🔮 Analyzing execution patterns..."
	@python scripts/predictive_analyzer.py

predict-for:
	@if not defined FILE (echo "Usage: make predict-for FILE=path/to/file.py" && exit /b 1)
	@python scripts/predictive_analyzer.py --predict $(FILE)

agent-predict:
	@echo "🔮 Starting Agent in predictive mode only..."
	@python scripts/kaelis_agent.py --no-check --no-annotate

# ============================================
# 🤖 主动建议 Agent (迭代�?
# ============================================

daemon:
	@python scripts/kaelis_daemon.py

daemon-bg:
	@powershell -ExecutionPolicy Bypass -File scripts/kaelis_bg.ps1

daemon-stop:
	@python scripts/kaelis_daemon.py --stop

daemon-status:
	@if exist .kaelis-daemon.pid (
		@set /p PID=<.kaelis-daemon.pid
		@echo [OK] Daemon running (PID %PID%)
	) else (
		@echo [INFO] No daemon running
	)

# ============================================
# 🧪 测试与验�?
# ============================================

test-suggest:
	@echo "🧪 测试上下文建议器..."
	@python scripts/context_aware_suggester.py api/routes/test.py 2>nul || echo "测试文件不存在，这是正常�?
	@python scripts/context_aware_suggester.py scripts/test.py 2>nul || echo "测试文件不存在，这是正常�?

test-telemetry:
	@echo "🧪 测试遥测系统..."
	@python scripts/telemetry.py
$(Get-Content Makefile)

# ============================================================================
# 🧬 Kaelis v2.0 - 团队协作与自适应学习 (新增)
# ============================================================================

team-init:
	@python scripts/team_sync.py init $(REMOTE)

team-sync:
	@python scripts/team_sync.py sync

team-status:
	@python scripts/team_sync.py status

learn:
	@echo "🧠 从成功会话中学习新规�?.."
	@python scripts/rule_learner.py

learn-custom:
	@if "$(FREQ)"=="" (set FREQ=3)
	@if "$(RATE)"=="" (set RATE=0.9)
	@python scripts/rule_learner.py --min-frequency $(FREQ) --min-success-rate $(RATE)

symbols:
	@echo "🔍 构建符号索引..."
	@python scripts/symbol_indexer.py --full

symbols-incr:
	@echo "🔍 增量更新符号索引..."
	@python scripts/symbol_indexer.py

symbols-query:
	@if "$(QUERY)"=="" (echo "用法: make symbols-query QUERY=function:login" && exit /b 1)
	@python scripts/symbol_indexer.py --query "$(QUERY)"

template-review:
	@echo "📋 待审规则模板:"
	@if exist config/templates/pending (
		@dir /b config/templates/pending/*.yaml 2>nul || echo "  (无待审模�?"
	) else (
		@echo "  (目录不存�?"
	)
	@echo.
	@echo "运行以下命令采纳模板:"
	@echo   kaelis template approve ^<id^>

template-list:
	@echo "📋 已批准的规则模板:"
	@if exist config/templates/approved (
		@dir /b config/templates/approved/*.yaml 2>nul | find /c /v "" 2>nul
	) else (
		@echo "  (无已批准模板)"
	)

# ============================================================================
# 🆕 v2.0 快速命�?
# ============================================================================

v20-status:
	@echo "🧬 Kaelis v2.0 状�?
	@echo "===================="
	@echo.
	@echo [团队协作]
	@if exist .kaelis-team/.git (echo   [OK] 团队知识库已初始�? else (echo   [PENDING] 团队知识库未初始�?
	@echo.
	@echo [符号索引]
	@if exist .kaelis/symbols/symbols.json (echo   [OK] 符号索引已构�? else (echo   [PENDING] 符号索引未构�?
	@echo.
	@echo [规则学习]
	@if exist config/templates/pending/*.yaml (
		@for %%f in (config/templates/pending/*.yaml) do @echo   [PENDING] 待审模板: %%f
	) else (
		@echo   [OK] 无待审模�?
	)
	@echo.
	@echo 快速命�?
	@echo   make team-init REMOTE=https://github.com/org/kaelis-team.git
	@echo   make team-sync
	@echo   make symbols
	@echo   make learn
# ============================================================================
# 🔗 架构收敛与模块联动修�?(Schema-Driven Linkage System)
# ============================================================================

# 核心命令: 一键同步所有模�?
sync-all:
	@echo "🔗 Architecture Convergence - Sync All Modules"
	@echo "=============================================="
	@echo.
	@echo "1️⃣  Checking configuration drift..."
	@python scripts/sync_config.py check || echo "   ⚠️ Config drift detected, will fix"
	@echo.
	@echo "2️⃣  Synchronizing configuration..."
	@python scripts/sync_config.py sync
	@echo.
	@echo "3️⃣  Generating backend routes from OpenAPI..."
	@python scripts/codegen.py backend --output api/routes
	@echo.
	@echo "4️⃣  Generating frontend types from OpenAPI..."
	@python scripts/codegen.py frontend --output web/frontend/src/api
	@echo.
	@echo "5️⃣  Generating tests from OpenAPI..."
	@python scripts/codegen.py tests --output tests
	@echo.
	@echo "6️⃣  Generating Postman collection..."
	@python scripts/codegen.py postman --output postman
	@echo.
	@echo "7️⃣  Generating API documentation..."
	@python scripts/codegen.py readme --output .
	@echo.
	@echo "8️⃣  Running architecture audit..."
	@python scripts/dependency_graph.py audit
	@echo.
	@echo "�?All modules synchronized!"

# 后端路由同步
sync-backend:
	@echo "🐍 Generating backend routes from OpenAPI..."
	@python scripts/codegen.py backend --output api/routes
	@echo.
	@echo "�?Backend routes updated"
	@echo "💡 Review changes: git diff api/routes/"

# 前端类型同步
sync-frontend:
	@echo "⚛️ Generating frontend types from OpenAPI..."
	@python scripts/codegen.py frontend --output web/frontend/src/api
	@echo.
	@echo "�?Frontend types updated"
	@echo "💡 Review changes: git diff web/frontend/src/api/"

# 测试文件同步
sync-tests:
	@echo "🧪 Generating tests from OpenAPI..."
	@python scripts/codegen.py tests --output tests
	@echo.
	@echo "�?Tests updated"

# Postman 集合同步
sync-postman:
	@echo "📮 Generating Postman collection..."
	@python scripts/codegen.py postman --output postman
	@echo.
	@echo "�?Postman collection updated"

# README API 文档同步
sync-readme:
	@echo "📚 Generating API documentation..."
	@python scripts/codegen.py readme --output .
	@echo.
	@echo "�?README_API.md updated"

# 配置同步
sync-config:
	@echo "🔧 Synchronizing configuration..."
	@python scripts/sync_config.py sync

# 预览配置变更
sync-config-dry:
	@echo "🔍 Configuration Sync (Dry Run)..."
	@python scripts/sync_config.py sync --dry-run

# 架构审计 (通、达、速、省)
audit:
	@echo "🔍 Running Architecture Audit: 通、达、速、省"
	@python scripts/dependency_graph.py audit

# 一致性检�?
check-convergence:
	@echo "📊 Checking system convergence..."
	@python scripts/dependency_graph.py check

# 查看变更影响范围
affected:
	@if "$(FILE)"=="" (echo "Usage: make affected FILE=contracts/openapi.yaml" && exit /b 1)
	@echo "🔍 Analyzing impact of: $(FILE)"
	@python scripts/dependency_graph.py affected $(FILE)

# 生成联动修正任务
sync-tasks:
	@if "$(FILE)"=="" (echo "Usage: make sync-tasks FILE=contracts/openapi.yaml" && exit /b 1)
	@echo "📋 Generating sync tasks for: $(FILE)"
	@python scripts/dependency_graph.py tasks $(FILE)

# OpenAPI 规范验证
validate-api:
	@echo "�?Validating OpenAPI specification..."
	@python scripts/dependency_graph.py validate --type openapi

# ============================================================================
# 🏗�?v2.1 架构收敛状�?
# ============================================================================

convergence-status:
	@echo "🏗�? Kaelis Architecture Convergence Status"
	@echo "=========================================="
	@echo.
	@echo [单一事实源]
	@if exist contracts/openapi.yaml (echo   [✅] OpenAPI Specification) else (echo   [❌] OpenAPI Specification Missing)
	@echo.
	@echo [代码生成]
	@if exist scripts/codegen.py (echo   [✅] Code Generator) else (echo   [❌] Code Generator Missing)
	@echo.
	@echo [依赖图谱]
	@if exist scripts/dependency_graph.py (echo   [✅] Dependency Graph Engine) else (echo   [❌] Dependency Graph Missing)
	@echo.
	@echo [配置同步]
	@if exist scripts/sync_config.py (echo   [✅] Config Sync Engine) else (echo   [❌] Config Sync Missing)
	@echo.
	@echo [Backend Routes]
	@if exist api/routes (for %%f in (api/routes/*.py) do @echo   [✅] %%f) else (echo   [❌] No routes directory)
	@echo.
	@echo [Frontend Types]
	@if exist web/frontend/src/api/schema.d.ts (echo   [✅] schema.d.ts) else (echo   [❌] schema.d.ts Missing)
	@echo.
	@echo 快速命�?
	@echo   make sync-all              一键同步所有模�?
	@echo   make audit                 执行架构审计
	@echo   make check-convergence     检查系统一致�?

# ============================================================================
# Electron - Desktop Application (Phase 9 P2)
# ============================================================================

electron-install:
	@cd web/frontend && npm install electron electron-builder --save-dev

electron-dev:
	@cd web/frontend && npm run electron:dev

electron-build:
	@python scripts/build_electron.py

electron-build-win:
	@python scripts/build_electron.py win

electron-build-mac:
	@python scripts/build_electron.py mac

electron-build-linux:
	@python scripts/build_electron.py linux

dist: electron-build

# ============================================================================
# KECL - Kaelis Experience Contract Language
# ============================================================================

experience:
	@python scripts/kaelis_experience.py $(JOURNEY)

experience-list:
	@python scripts/kaelis_experience.py --list

init:
	@python scripts/kaelis_experience.py first_time_user

dev:
	@python scripts/kaelis_experience.py dev_quickstart

# ============================================================================
# Phase 9 P1: Supabase Auth + Workflow Sync
# ============================================================================

# Supabase配置
supabase-setup:
	@echo "🔧 Supabase Setup"
	@echo "=================="
	@echo.
	@echo "1. Create project at https://app.supabase.io"
	@echo "2. Copy SQL from config/supabase/schema.sql to SQL Editor"
	@echo "3. Copy credentials to web/frontend/.env.local:"
	@echo.
	@echo "VITE_SUPABASE_URL=https://your-project.supabase.co"
	@echo "VITE_SUPABASE_ANON_KEY=your-anon-key"

# 前端依赖安装
frontend-deps:
	cd web/frontend && npm install @supabase/supabase-js

# ============================================================================
# 💳 技术债务治理 v2.0
# ============================================================================

debt-list:
	@python scripts/kaelis_debt.py list --sort impact

debt-show:
	@if not defined ID (echo "用法: make debt-show ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py show $(ID)

debt-create:
	@if not defined TITLE (echo "用法: make debt-create TITLE=标题 CATEGORY=类别" && exit /b 1)
	@python scripts/kaelis_debt.py create --title "$(TITLE)" --category $(CATEGORY)

debt-link:
	@if not defined ID (echo "用法: make debt-link ID=债务ID SYM=符号 FILE=文件路径" && exit /b 1)
	@python scripts/kaelis_debt.py link $(ID) --symbol $(SYM) --file $(FILE)

debt-relink:
	@echo "🔄 重构后重新匹配符�?.."
	@python scripts/kaelis_debt.py relink

debt-verify:
	@if not defined ID (echo "用法: make debt-verify ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py verify $(ID)

debt-impact:
	@if not defined ID (echo "用法: make debt-impact ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py impact $(ID)

debt-suggest:
	@if not defined ID (echo "用法: make debt-suggest ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py suggest $(ID)

debt-adopt:
	@if not defined ID (echo "用法: make debt-adopt ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py adopt $(ID)

debt-resolve:
	@if not defined ID (echo "用法: make debt-resolve ID=债务ID" && exit /b 1)
	@python scripts/kaelis_debt.py resolve $(ID)

# ============================================================================
# 🤖 AI Native Development System (Phase 1)
# ============================================================================

ai-status:
	@echo "🤖 Kaelis AI Native 状�?
	@echo "========================="
	@echo.
	@python scripts/kaelis_ai.py status

ai-sync:
	@echo "🔄 同步 AI 上下文文�?.."
	@python scripts/kaelis_ai.py sync

ai-query:
	@if not defined Q (echo "用法: make ai-query Q='查询内容'" && exit /b 1)
	@python scripts/kaelis_ai.py query "$(Q)"

ai-search:
	@if not defined SYM (echo "用法: make ai-search SYM=符号�? && exit /b 1)
	@python scripts/kaelis_ai.py search $(SYM)

ai-impact:
	@if not defined FILE (echo "用法: make ai-impact FILE=文件路径" && exit /b 1)
	@python scripts/kaelis_ai.py impact $(FILE)

ai-risk:
	@if not defined FILE (echo "用法: make ai-risk FILE=文件路径" && exit /b 1)
	@python scripts/kaelis_ai.py risk $(FILE)

ai-analyze:
	@echo "📈 分析阻断模式..."
	@python scripts/kaelis_ai.py analyze

# ============================================================================
# 📅 Phase 9 产品�?- 每周产品回顾 (新增)
# ============================================================================

weekly-review:
	@echo "📊 Kaelis 每周产品回顾"
	@echo "======================="
	@echo.
	@python scripts/weekly_review.py --save

# 快速查看产品健康度
product-health:
	@echo "🏥 Kaelis 产品健康度快�?
	@echo "========================="
	@echo.
	@python scripts/weekly_review.py

# 不做清单检�?
frozen-check:
	@echo "❄️  Phase 9 不做清单检�?
	@echo "========================"
	@echo.
	@echo "以下能力�?Phase 9 期间冻结:"
	@echo "  �?认知预判引擎"
	@echo "  �?AI 共生画布"
	@echo "  �?三模运行开�?
	@echo "  �?零知识密钥存�?
	@echo "  �?三位一体市�?
	@echo.
	@echo "待产品验证后 (NPS>=50) �?Phase 10 启动"

# ============================================================================
# 🏗�?MVP 提测 - 契约管理 (新增)
# ============================================================================

# 契约审计 - 检查契约漂�?
converge:
	@if "$(ACTION)"=="" ( \
		echo "用法: make converge ACTION=audit^|sync" && \
		echo "" && \
		echo "  audit - 审计契约与实现的一致�? && \
		echo "  sync  - 同步契约到实�? && \
		exit /b 1 \
	)
	@python scripts/kaelis.py converge $(ACTION)

# 快速契约审�?
converge-audit:
	@python scripts/kaelis.py converge audit

# 快速契约同�?
converge-sync:
	@python scripts/kaelis.py converge sync

# 体验旅程
experience-run:
	@if "$(JOURNEY)"=="" ( \
		echo "用法: make experience-run JOURNEY=first_time_onboarding" && \
		python scripts/kaelis.py experience --list && \
		exit /b 1 \
	)
	@python scripts/kaelis.py experience $(JOURNEY)

# 提测准入检�?
mvp-check:
	@echo "🏥 Kaelis MVP 提测准入检�?
	@echo "============================"
	@echo.
	@echo "[1/5] 完整体检..."
	@python scripts/kaelis.py physician || echo "   ⚠️  体检发现问题"
	@echo.
	@echo "[2/5] 契约审计..."
	@python scripts/kaelis.py converge audit || echo "   ⚠️  契约审计发现问题"
	@echo.
	@echo "[3/5] 前端构建检�?.."
	@cd web/frontend && npm run build 2>nul && echo "   �?前端构建成功" || echo "   �?前端构建失败"
	@echo.
	@echo "[4/5] 后端启动检�?.."
	@python -c "import api" 2>nul && echo "   �?后端导入成功" || echo "   �?后端导入失败"
	@echo.
	@echo "[5/5] 健康检�?.."
	@curl -s http://localhost:5000/api/auth/health 2>nul && echo "   �?服务健康" || echo "   ⚠️  服务未启�?
	@echo.
	@echo "============================"
	@echo "检查完成。请查看上方结果�?

# ============================================================
# Electron 桌面应用打包 (Phase 9 P2)
# ============================================================

.PHONY: electron-build electron-package electron-package-win electron-package-mac electron-package-linux


# ============================================================
# Electron 桌面应用打包 (Phase 9 P2) - 契约驱动构建
# ============================================================

.PHONY: electron-package electron-package-win electron-package-mac electron-package-linux

electron-package:
	@echo "🔒 [1/4] Running Electron contract gate..."
	@python scripts/kaelis_guardian.py --electron-check || exit /b 1
	@echo "⚙️  [2/4] Generating Electron configs from contract..."
	@python scripts/generate_electron_config.py || exit /b 1
	@echo "🔧 [3/4] Building frontend for Electron..."
	@cd web/frontend && npm run build || exit /b 1
	@echo "📦 [4/4] Packaging Electron app for all platforms..."
	@cd web/frontend && npx electron-builder --config ../../electron-builder.json --publish never
	@echo "✅ Electron packaging complete."

electron-package-win:
	@echo "🔒 [1/4] Running Electron contract gate..."
	@python scripts/kaelis_guardian.py --electron-check || exit /b 1
	@echo "⚙️  [2/4] Generating Electron configs from contract..."
	@python scripts/generate_electron_config.py || exit /b 1
	@echo "🔧 [3/4] Building frontend for Electron..."
	@cd web/frontend && npm run build || exit /b 1
	@echo "📦 [4/4] Packaging Electron app for Windows..."
	@cd web/frontend && npx electron-builder --config ../../electron-builder.json --win --publish never
	@echo "✅ Windows packaging complete."

electron-package-mac:
	@echo "🔒 [1/4] Running Electron contract gate..."
	@python scripts/kaelis_guardian.py --electron-check || exit /b 1
	@echo "⚙️  [2/4] Generating Electron configs from contract..."
	@python scripts/generate_electron_config.py || exit /b 1
	@echo "🔧 [3/4] Building frontend for Electron..."
	@cd web/frontend && npm run build || exit /b 1
	@echo "📦 [4/4] Packaging Electron app for macOS..."
	@cd web/frontend && npx electron-builder --config ../../electron-builder.json --mac --publish never
	@echo "✅ macOS packaging complete."

electron-package-linux:
	@echo "🔒 [1/4] Running Electron contract gate..."
	@python scripts/kaelis_guardian.py --electron-check || exit /b 1
	@echo "⚙️  [2/4] Generating Electron configs from contract..."
	@python scripts/generate_electron_config.py || exit /b 1
	@echo "🔧 [3/4] Building frontend for Electron..."
	@cd web/frontend && npm run build || exit /b 1
	@echo "📦 [4/4] Packaging Electron app for Linux..."
	@cd web/frontend && npx electron-builder --config ../../electron-builder.json --linux --publish never
	@echo "✅ Linux packaging complete."


# ============================================================
# Adapter Validation (P1)
# ============================================================

.PHONY: validate-adapters

validate-adapters:
	@echo "🔍 Validating adapter contracts..."
	@python scripts/validate_adapters.py
