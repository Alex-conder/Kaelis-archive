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
    from api.routes.intent import bp
    from api.routes.knowledge_graph import bp as knowledge_graph_bp
    from api.routes.reports import bp as reports_bp
    from api.routes.symbols import bp as symbols_bp
    from api.routes.system import bp as system_bp
    from api.routes.team import bp as team_bp
    from api.routes.workflow_nodes import bp as workflow_nodes_bp
    
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
    app.register_blueprint(bp)
    app.register_blueprint(knowledge_graph_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(symbols_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(workflow_nodes_bp)
    
    # 注册 API 中间件（安全扫描 + 速率限制 + 签名验证 + 指标埋点）
    try:
        from core.middleware import register_middleware
        register_middleware(app)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Middleware not registered: {e}")
    
    # 初始化数据库连接池
    try:
        from core.db_pool import init_pool_for_memory_manager
        init_pool_for_memory_manager(db_dir="data")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"DB pool not initialized: {e}")
    
    # 启动自动化质检调度器
    try:
        from core.monitoring.scheduler import get_quality_scheduler
        scheduler = get_quality_scheduler()
        scheduler.start()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Quality scheduler not started: {e}")
    
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
    threads = int(os.getenv('WAITRESS_THREADS', '4'))
    
    logger.info(f"[PROD] Starting Kaelis on {host}:{port} with {threads} threads")
    
    from waitress import serve
    app = create_app()
    serve(app, host=host, port=port, threads=threads)
