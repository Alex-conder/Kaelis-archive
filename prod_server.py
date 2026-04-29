"""
Kaelis 生产服务器入口
使用 waitress 替代 Flask 开发服务器
"""
import os
import sys

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, send_from_directory

# 初始化日志
try:
    from core.logging_config import init_logging
    init_logging()
except Exception:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_dist_path():
    """获取前端 dist 目录路径"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'web', 'frontend', 'dist')


def create_app():
    """创建 Flask 应用（生产模式）"""
    
    # 启动时健康检查
    try:
        from core.memory_health import run_startup_health_check
        health_report = run_startup_health_check(db_dir="data")
        if health_report["overall"] == "failed":
            import logging
            logging.getLogger(__name__).warning("Memory subsystem health check FAILED - starting in degraded mode")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Startup health check skipped: {e}")
    
    from api.routes.evolve import evolve_bp
    from api.routes.skills import skills_bp
    from api.routes.recorder import recorder_bp
    from api.routes.memory import memory_bp
    from api.routes.mobile import mobile_bp
    from api.routes.metabolomics import metabolomics_bp
    from api.routes.omics import bp as omics_bp
    from api.routes.ai_native import ai_native_bp
    from api.routes.auth import auth_bp
    from api.routes.sync import sync_bp
    from api.routes.kg_flywheel_routes import kg_flywheel_bp
    from api.routes.approval import approval_bp
    from api.routes.monitoring import monitoring_bp
    from api.routes.workflow_monitoring import workflow_monitoring_bp
    from api.routes.shared_memory import shared_memory_bp
    from api.routes.agent_permissions import agent_permissions_bp
    from api.routes.pubsub import pubsub_bp
    from api.routes.approvals import approvals_bp
    from api.routes.notifications import notifications_bp
    from api.routes.journey import journey_bp
    from api.routes.privacy import privacy_bp
    from api.routes.sharing import bp as sharing_bp
    
    app = Flask(__name__, static_folder='api/static')
    app.secret_key = os.environ.get('SECRET_KEY', 'kaelis-dev-secret-key-change-in-production')
    
    # 启用 CORS
    try:
        from flask_cors import CORS
        CORS(app, resources={r"/api/*": {"origins": "*"}, r"/ai/*": {"origins": "*"}})
    except ImportError:
        pass
    
    app.register_blueprint(evolve_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(recorder_bp)
    app.register_blueprint(memory_bp)
    app.register_blueprint(mobile_bp)
    app.register_blueprint(metabolomics_bp)
    app.register_blueprint(omics_bp)
    app.register_blueprint(ai_native_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(kg_flywheel_bp)
    app.register_blueprint(approval_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(workflow_monitoring_bp)
    app.register_blueprint(shared_memory_bp)
    app.register_blueprint(agent_permissions_bp)
    app.register_blueprint(pubsub_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(journey_bp)
    app.register_blueprint(privacy_bp)
    app.register_blueprint(sharing_bp)
    
    # 注册 Swagger UI（API 交互式文档）
    try:
        from flasgger import Swagger
        Swagger(app, template={
            "swagger": "2.0",
            "info": {
                "title": "Kaelis API",
                "description": "AI Agent OS with four-layer memory and self-evolution",
                "version": "2.0.0",
                "contact": {
                    "url": "https://github.com/Alex-conder/Kaelis-archive"
                }
            },
            "basePath": "/",
            "schemes": ["http", "https"],
        })
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Flasgger not installed, Swagger UI disabled")
    
    # 注册 API 中间件（安全扫描 + 速率限制 + 签名验证 + 指标埋点）
    try:
        from core.middleware import register_middleware
        register_middleware(app)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Middleware not registered: {e}")
    
    # FIX-1: 初始化线程本地连接池（优先）
    try:
        from core.database.connection_pool import init_pools_for_memory_manager
        init_pools_for_memory_manager(db_dir="data")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Thread-local DB pool not initialized: {e}")
    
    # B-3: 兼容旧连接池初始化
    try:
        from core.db_pool import init_pool_for_memory_manager
        init_pool_for_memory_manager(db_dir="data")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Legacy DB pool not initialized: {e}")
    
    # 启动自动化质检调度器
    try:
        from core.monitoring.scheduler import get_quality_scheduler
        scheduler = get_quality_scheduler()
        scheduler.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Quality scheduler not started: {e}")
    
    # 首次启动安全审计
    try:
        from core.security.install_auditor import InstallAuditor
        auditor = InstallAuditor()
        report = auditor.run_full_audit()
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"安装安全审计完成: {report.stats['total']} 项发现, 总体风险 {report.overall_level}")
        if report.stats.get('critical', 0) > 0:
            logger.error(f"发现 {report.stats['critical']} 项 CRITICAL 风险，请立即处理！")
        elif report.stats.get('high', 0) > 0:
            logger.warning(f"发现 {report.stats['high']} 项 HIGH 风险，建议修复后使用")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"安装安全审计跳过: {e}")
    
    # 首次启动环境扫描与技能导入（审计通过后执行）
    try:
        from core.migration.smart_detector import scan_for_competitors
        from core.skill_universal_adapter import UniversalSkillAdapter
        competitors = scan_for_competitors()
        if competitors:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"首次启动检测到 {len(competitors)} 个外部数据源，准备自动纳管...")
            adapter = UniversalSkillAdapter()
            for comp in competitors:
                stats = adapter.batch_import(comp["path"])
                logger.info(f"纳管完成 [{comp['name']}]: {stats['registered']}/{stats['recognized']} 技能已注册")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"首次启动自动纳管跳过: {e}")
    
    DIST_DIR = get_dist_path()
    has_react_frontend = os.path.exists(os.path.join(DIST_DIR, 'index.html'))
    
    @app.route('/')
    def index():
        if has_react_frontend:
            return send_from_directory(DIST_DIR, 'index.html')
        return '''
        <h1>🌊 Kaelis 智流 AI Agent</h1>
        <p>自进化引擎已就绪</p>
        <ul>
            <li><a href="/settings.html">系统设置</a></li>
            <li><a href="/api/evolve/config">API 配置</a></li>
        </ul>
        '''
    
    @app.route('/<path:filename>')
    def serve_static(filename):
        if has_react_frontend:
            file_path = os.path.join(DIST_DIR, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(DIST_DIR, filename)
            return send_from_directory(DIST_DIR, 'index.html')
        return "Not found", 404
    
    @app.route('/settings.html')
    def settings():
        return send_from_directory('api/static', 'settings.html')
    
    @app.route('/kg-flywheel')
    def kg_flywheel_redirect():
        return send_from_directory('api/static', 'kg-flywheel.html')
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        from datetime import datetime
        import platform
        
        checks = {
            "self_evolving": False,
            "skill_manager": False,
            "knowledge_retriever": False
        }
        
        try:
            from core.self_evolving import SelfEvolvingEngine
            checks["self_evolving"] = True
        except Exception:
            pass
        
        try:
            from core.skill_manager import get_skill_manager
            checks["skill_manager"] = True
        except Exception:
            pass
        
        try:
            from core.knowledge_retriever import KnowledgeRetriever
            checks["knowledge_retriever"] = True
        except Exception:
            pass
        
        all_healthy = all(checks.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "version": "8.0.0",
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "mode": "lightweight",
            "host": platform.node()
        }
    
    return app


if __name__ == '__main__':
    import logging
    logger = logging.getLogger('prod_server')
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))
    # B-3: 动态线程数，默认 max(4, CPU核心数)，上限 8（SQLite GIL 限制，过多线程反而降低性能）
    threads = int(os.getenv('WAITRESS_THREADS', max(4, min(8, (os.cpu_count() or 4)))))
    
    logger.info(f"[PROD] Starting Kaelis on {host}:{port} with {threads} threads")
    
    # ===== 启动时智能迁移向导 =====
    try:
        from core.migration.smart_detector import scan_for_competitors
        competitors = scan_for_competitors()
        if competitors:
            print("\n" + "=" * 60)
            print("🧳  Kaelis 智能迁移向导")
            print("=" * 60)
            for comp in competitors:
                print(f"\n  📦 检测到 {comp['name'].upper()} 数据源")
                print(f"     路径: {comp['path']}")
                print(f"     大小: {comp['size_human']} | 置信度: {comp['confidence']:.0%}")
            print(f"\n  共发现 {len(competitors)} 个可迁移数据源")
            print("\n  是否立即导入？[Y/n] ", end="", flush=True)
            
            import sys, select
            # 尝试读取用户输入（30秒超时）
            has_input = False
            try:
                if os.name == 'nt':
                    import msvcrt
                    start = __import__('time').time()
                    while __import__('time').time() - start < 30:
                        if msvcrt.kbhit():
                            ch = msvcrt.getche().decode('utf-8', errors='ignore')
                            if ch.lower() == 'y' or ch == '\r':
                                has_input = True
                            break
                        __import__('time').sleep(0.1)
                else:
                    ready, _, _ = select.select([sys.stdin], [], [], 30)
                    if ready:
                        user_input = sys.stdin.readline().strip().lower()
                        has_input = user_input in ('y', 'yes', '')
            except Exception:
                pass
            
            if has_input:
                from core.skill_universal_adapter import UniversalSkillAdapter
                adapter = UniversalSkillAdapter()
                total_imported = 0
                for comp in competitors:
                    stats = adapter.batch_import(comp["path"])
                    total_imported += stats.get("registered", 0)
                    print(f"  ✅ {comp['name']}: {stats['registered']}/{stats['recognized']} 已导入")
                print(f"\n  🎉 迁移完成！共导入 {total_imported} 个技能")
                
                # 记录到 L2 Episodic 记忆
                try:
                    from core.memory_manager_v2 import get_memory_manager
                    mm = get_memory_manager()
                    mm.write(
                        layer="L2",
                        key=f"migration_{__import__('datetime').datetime.now().isoformat()}",
                        value={"sources": [c["name"] for c in competitors], "imported": total_imported},
                        metadata={"source": "startup_migration", "event_type": "migration"},
                        user_id="kaelis_self",
                    )
                except Exception:
                    pass
            else:
                print("\n  ⏭️  跳过迁移")
                # 写入 pending 提示
                pending_dir = __import__('pathlib').Path("data/migration")
                pending_dir.mkdir(parents=True, exist_ok=True)
                pending_file = pending_dir / "pending.md"
                pending_file.write_text(
                    f"# 待处理迁移\n\n检测到 {len(competitors)} 个数据源未导入。\n"
                    f"运行 `python scripts/cli.py migrate detect` 手动触发迁移。\n",
                    encoding="utf-8",
                )
            print("=" * 60 + "\n")
    except Exception as e:
        logger.warning(f"启动迁移向导跳过: {e}")
    # ===== 迁移向导结束 =====
    
    from waitress import serve
    app = create_app()
    serve(app, host=host, port=port, threads=threads)
