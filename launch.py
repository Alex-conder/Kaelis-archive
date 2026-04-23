#!/usr/bin/env python3
"""
Kaelis 智流 AI Agent - 一键启动脚本

功能：
1. 检查依赖
2. 初始化数据目录
3. 启动服务
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# 加载 .env 环境变量（必须在其他导入之前）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Fixer D2: 统一日志初始化入口
try:
    from core.logging_config import init_logging
    init_logging()
except Exception:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger('launcher')


def check_dependencies():
    """检查关键依赖"""
    required = ['flask', 'chromadb', 'simpleeval']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False
    
    logger.info("[OK] Dependencies check passed")
    return True


def init_directories():
    """初始化数据目录"""
    dirs = [
        'data/documents',
        'data/chroma_db',
        'data/cache/knowledge',
        'logs'
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    
    logger.info("[OK] Data directories initialized")


def test_core_modules():
    """测试核心模块"""
    modules = [
        ('core.evaluators', 'RuleBasedEvaluator'),
        ('core.strategy_selector', 'StrategySelector'),
        ('core.self_evolving', 'SelfEvolvingEngine'),
        ('core.rl_optimizer', 'RLOptimizer'),
        ('core.transfer_learning', 'TransferLearning'),
        ('core.knowledge_retriever', 'KnowledgeRetriever'),
    ]
    
    passed = 0
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            logger.info(f"  [OK] {module_name}.{class_name}")
            passed += 1
        except Exception as e:
            logger.warning(f"  [WARN] {module_name}.{class_name}: {e}")
    
    logger.info(f"[OK] Core modules: {passed}/{len(modules)} passed")
    return passed == len(modules)


def run_tests():
    """运行自进化测试"""
    logger.info("🧪 运行自进化测试...")
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/test_self_evolving_complete.py', '-v'],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            return False
        return True
    except Exception as e:
        logger.error(f"测试运行失败: {e}")
        return False


def get_dist_path():
    """获取前端 dist 目录路径（兼容 PyInstaller 单文件模式）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, 'web', 'frontend', 'dist')


def start_server():
    """启动服务"""
    logger.info("[START] Launching Kaelis services...")
    logger.info("[INFO] Running in native mode (SQLite + SQLiteGraphDriver)")
    logger.info("访问地址:")
    logger.info("  - 首页: http://localhost:5000")
    logger.info("  - 设置: http://localhost:5000/settings.html")
    logger.info("  - API: http://localhost:5000/api/evolve/config")
    
    try:
        # 创建简单 Flask 应用
        from flask import Flask, send_from_directory
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
        
        app = Flask(__name__, static_folder='api/static')
        app.secret_key = os.environ.get('SECRET_KEY', 'kaelis-dev-secret-key-change-in-production')
        
        # 启用 CORS（开发环境跨域支持）
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
        
        from api.routes.approval import approval_bp
        from api.routes.monitoring import monitoring_bp
        from api.routes.workflow_monitoring import workflow_monitoring_bp
        app.register_blueprint(approval_bp)
        app.register_blueprint(monitoring_bp)
        app.register_blueprint(workflow_monitoring_bp)
        
        # 注册 API 中间件
        try:
            from core.middleware import register_middleware
            register_middleware(app)
        except Exception as e:
            logger.warning(f"Middleware not registered: {e}")
        
        # 初始化数据库连接池
        try:
            from core.db_pool import init_pool_for_memory_manager
            init_pool_for_memory_manager(db_dir="data")
        except Exception as e:
            logger.warning(f"DB pool not initialized: {e}")
        
        # 启动自动化质检调度器
        try:
            from core.monitoring.scheduler import get_quality_scheduler
            scheduler = get_quality_scheduler()
            scheduler.start()
        except Exception as e:
            logger.warning(f"Quality scheduler not started: {e}")
        
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
            # 优先 serve dist 中的真实静态文件（JS/CSS/图片等）
            if has_react_frontend:
                file_path = os.path.join(DIST_DIR, filename)
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    return send_from_directory(DIST_DIR, filename)
                # React Router history fallback
                return send_from_directory(DIST_DIR, 'index.html')
            return "Not found", 404
        
        @app.route('/settings.html')
        def settings():
            return send_from_directory('api/static', 'settings.html')
        
        @app.route('/kg-flywheel')
        def kg_flywheel_redirect():
            """知识图谱飞轮入口"""
            return send_from_directory('api/static', 'kg-flywheel.html')
        
        @app.route('/api/health', methods=['GET'])
        def health_check():
            """统一健康检查端点"""
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
        
        use_reloader = '--no-reload' not in sys.argv
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=use_reloader)
        
    except Exception as e:
        logger.error(f"[FAIL] Launch failed: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("[Kaelis] AI Agent Launcher")
    print("=" * 60)
    
    # Fixer B2: 启动前强制校验环境变量
    if '--skip-env-check' not in sys.argv:
        try:
            from core.env_validator import validate_env
            result = validate_env()
            if not result:
                logger.error("[FAIL] 环境变量校验未通过:")
                for err in result.errors:
                    logger.error(f"  - {err}")
                sys.exit(1)
            logger.info("[OK] 环境变量校验通过")
        except Exception as e:
            logger.error(f"[FAIL] 环境变量校验异常: {e}")
            sys.exit(1)
    else:
        logger.warning("[WARN] 已跳过环境变量校验（--skip-env-check）")
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 初始化目录
    init_directories()
    
    # 测试模块
    test_core_modules()
    
    # 运行测试（可选）
    if '--test' in sys.argv:
        if not run_tests():
            logger.error("❌ 测试未通过")
            sys.exit(1)
        logger.info("[OK] Tests passed")
    
    # 启动服务
    start_server()


if __name__ == '__main__':
    main()
