"""
Kaelis Authentication API
P1 Task: Supabase Authentication + Workflow Cloud Sync
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import os
from pathlib import Path
from datetime import datetime

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Supabase配置
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY', '')

supabase: Client = None
if HAS_SUPABASE and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[WARN] Supabase初始化失败: {e}")

# 离线模式用户数据目录
OFFLINE_DATA_DIR = Path(__file__).parent.parent.parent / '.kaelis'
OFFLINE_DATA_DIR.mkdir(exist_ok=True)
ONBOARDING_MARKER = OFFLINE_DATA_DIR / 'onboarding_completed'


def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not supabase:
            return jsonify({'error': 'Auth service unavailable'}), 503
        
        # 从请求头获取JWT
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing authorization header'}), 401
        
        token = auth_header[7:]
        
        try:
            # 验证token
            user = supabase.auth.get_user(token)
            request.user = user
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
    
    return decorated


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    if not supabase:
        return jsonify({'error': 'Auth service unavailable'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        # 注册用户
        result = supabase.auth.sign_up({
            'email': email,
            'password': password,
            'options': {
                'data': {'username': username or email.split('@')[0]}
            }
        })
        
        # 创建用户资料
        if result.user:
            supabase.table('profiles').insert({
                'id': result.user.id,
                'email': email,
                'username': username or email.split('@')[0],
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        
        return jsonify({
            'success': True,
            'user': {
                'id': result.user.id,
                'email': result.user.email
            },
            'message': 'Registration successful. Please check your email for verification.'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    if not supabase:
        return jsonify({'error': 'Auth service unavailable'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        result = supabase.auth.sign_in_with_password({
            'email': email,
            'password': password
        })
        
        return jsonify({
            'success': True,
            'user': {
                'id': result.user.id,
                'email': result.user.email,
                'username': result.user.user_metadata.get('username', '')
            },
            'session': {
                'access_token': result.session.access_token,
                'refresh_token': result.session.refresh_token,
                'expires_at': result.session.expires_at
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 401


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """用户登出"""
    try:
        supabase.auth.sign_out()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """获取当前用户信息"""
    try:
        user = request.user
        
        # 获取用户资料
        profile = supabase.table('profiles').select('*').eq('id', user.id).single().execute()
        
        return jsonify({
            'user': {
                'id': user.id,
                'email': user.email,
                'username': profile.data.get('username', '') if profile.data else '',
                'avatar_url': profile.data.get('avatar_url', '') if profile.data else ''
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """更新用户资料"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    try:
        user = request.user
        
        update_data = {}
        if 'username' in data:
            update_data['username'] = data['username']
        if 'avatar_url' in data:
            update_data['avatar_url'] = data['avatar_url']
        
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        result = supabase.table('profiles').update(update_data).eq('id', user.id).execute()
        
        return jsonify({
            'success': True,
            'profile': result.data[0] if result.data else None
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """刷新访问令牌"""
    data = request.get_json()
    if not data or not data.get('refresh_token'):
        return jsonify({'error': 'Refresh token required'}), 400
    
    try:
        result = supabase.auth.refresh_session(data['refresh_token'])
        
        return jsonify({
            'success': True,
            'session': {
                'access_token': result.session.access_token,
                'refresh_token': result.session.refresh_token,
                'expires_at': result.session.expires_at
            }
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 401


# ============================================================================
# 离线模式
# ============================================================================

@auth_bp.route('/offline/activate', methods=['POST'])
def activate_offline_mode():
    """激活离线模式，生成本地匿名账户"""
    session['offline_mode'] = True
    session['user_id'] = 'local_anonymous'
    return jsonify({
        'success': True,
        'mode': 'offline',
        'user': {
            'id': 'local_anonymous',
            'email': 'offline@kaelis.local',
            'username': 'Local User',
            'isAnonymous': True
        },
        'message': '离线模式已激活，工作流将保存于本地'
    })


@auth_bp.route('/offline/status', methods=['GET'])
def get_offline_status():
    """获取当前是否为离线模式"""
    return jsonify({
        'offline_mode': session.get('offline_mode', False),
        'user_id': session.get('user_id') if session.get('offline_mode') else None
    })


# ============================================================================
# 首次引导 (Onboarding)
# ============================================================================

@auth_bp.route('/onboarding/status', methods=['GET'])
def get_onboarding_status():
    """获取用户是否已完成首次引导"""
    completed = ONBOARDING_MARKER.exists()
    return jsonify({
        'completed': completed,
        'current_step': 'done' if completed else 'welcome'
    })


@auth_bp.route('/onboarding/complete', methods=['POST'])
def complete_onboarding():
    """标记首次引导完成"""
    try:
        ONBOARDING_MARKER.write_text(datetime.utcnow().isoformat(), encoding='utf-8')
        return jsonify({
            'success': True,
            'message': 'Onboarding completed'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# 健康检查
# ============================================================================

@auth_bp.route('/health', methods=['GET'])
def health_check():
    """认证服务健康检查"""
    return jsonify({
        'status': 'healthy' if supabase else 'unavailable',
        'supabase_configured': bool(SUPABASE_URL and SUPABASE_KEY),
        'offline_mode_supported': True,
        'timestamp': datetime.utcnow().isoformat()
    })
