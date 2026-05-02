"""
Kaelis Workflow Sync API
P1 Task: Workflow Cloud Sync (Web/Desktop)

Provides bidirectional sync between local and cloud workflows.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

from api.routes.auth import require_auth, supabase

sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')


# ============================================================================
# Workflow Sync API
# ============================================================================

@sync_bp.route('/workflows', methods=['GET'])
@require_auth
def get_workflows():
    """获取云端工作流列表"""
    try:
        user = request.user
        
        # 从Supabase获取工作流
        result = supabase.table('workflows')\
            .select('*')\
            .eq('user_id', user.id)\
            .order('updated_at', desc=True)\
            .execute()
        
        workflows = result.data if result.data else []
        
        # 添加同步状态
        for wf in workflows:
            wf['sync_status'] = 'synced'
        
        return jsonify({
            'success': True,
            'workflows': workflows,
            'total': len(workflows)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/workflows/<workflow_id>', methods=['GET'])
@require_auth
def get_workflow(workflow_id: str):
    """获取单个工作流"""
    try:
        user = request.user
        
        result = supabase.table('workflows')\
            .select('*')\
            .eq('id', workflow_id)\
            .eq('user_id', user.id)\
            .single()\
            .execute()
        
        if not result.data:
            return jsonify({'error': 'Workflow not found'}), 404
        
        return jsonify({
            'success': True,
            'workflow': result.data
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/workflows', methods=['POST'])
@require_auth
def create_workflow():
    """创建云端工作流"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    try:
        user = request.user
        
        workflow_data = {
            'user_id': user.id,
            'name': data.get('name', 'Untitled Workflow'),
            'description': data.get('description', ''),
            'nodes': json.dumps(data.get('nodes', [])),
            'edges': json.dumps(data.get('edges', [])),
            'is_public': data.get('is_public', False),
            'version': 1,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'synced_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = supabase.table('workflows').insert(workflow_data).execute()
        
        return jsonify({
            'success': True,
            'workflow': result.data[0] if result.data else None
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/workflows/<workflow_id>', methods=['PUT'])
@require_auth
def update_workflow(workflow_id: str):
    """更新云端工作流"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    try:
        user = request.user
        
        # 检查工作流是否存在且属于当前用户
        existing = supabase.table('workflows')\
            .select('version')\
            .eq('id', workflow_id)\
            .eq('user_id', user.id)\
            .single()\
            .execute()
        
        if not existing.data:
            return jsonify({'error': 'Workflow not found'}), 404
        
        # 检查版本冲突（乐观锁）
        client_version = data.get('version', 0)
        server_version = existing.data.get('version', 0)
        
        if client_version < server_version:
            return jsonify({
                'error': 'Version conflict',
                'server_version': server_version,
                'client_version': client_version
            }), 409
        
        # 更新数据
        update_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'nodes': json.dumps(data.get('nodes')) if 'nodes' in data else None,
            'edges': json.dumps(data.get('edges')) if 'edges' in data else None,
            'is_public': data.get('is_public'),
            'version': server_version + 1,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'synced_at': datetime.now(timezone.utc).isoformat()
        }
        
        # 移除None值
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = supabase.table('workflows')\
            .update(update_data)\
            .eq('id', workflow_id)\
            .eq('user_id', user.id)\
            .execute()
        
        return jsonify({
            'success': True,
            'workflow': result.data[0] if result.data else None
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/workflows/<workflow_id>', methods=['DELETE'])
@require_auth
def delete_workflow(workflow_id: str):
    """删除云端工作流"""
    try:
        user = request.user
        
        # 检查工作流是否存在
        existing = supabase.table('workflows')\
            .select('id')\
            .eq('id', workflow_id)\
            .eq('user_id', user.id)\
            .single()\
            .execute()
        
        if not existing.data:
            return jsonify({'error': 'Workflow not found'}), 404
        
        supabase.table('workflows')\
            .delete()\
            .eq('id', workflow_id)\
            .eq('user_id', user.id)\
            .execute()
        
        return jsonify({
            'success': True,
            'message': 'Workflow deleted successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Sync Operations
# ============================================================================

@sync_bp.route('/status', methods=['GET'])
@require_auth
def get_sync_status():
    """获取同步状态"""
    try:
        user = request.user
        last_sync = request.args.get('last_sync_at')
        
        query = supabase.table('workflows')\
            .select('id, updated_at, version')\
            .eq('user_id', user.id)
        
        # 只获取上次同步后有更新的
        if last_sync:
            query = query.gt('updated_at', last_sync)
        
        result = query.execute()
        
        return jsonify({
            'success': True,
            'pending_sync': len(result.data) if result.data else 0,
            'workflows': result.data if result.data else [],
            'server_time': datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/push', methods=['POST'])
@require_auth
def push_workflows():
    """批量推送本地工作流到云端"""
    data = request.get_json()
    if not data or not data.get('workflows'):
        return jsonify({'error': 'No workflows provided'}), 400
    
    try:
        user = request.user
        workflows = data['workflows']
        
        results = []
        conflicts = []
        
        for wf in workflows:
            workflow_id = wf.get('id')
            
            # 检查云端版本
            existing = supabase.table('workflows')\
                .select('version, updated_at')\
                .eq('id', workflow_id)\
                .eq('user_id', user.id)\
                .maybe_single()\
                .execute()
            
            if existing.data:
                # 更新现有工作流
                server_version = existing.data.get('version', 0)
                client_version = wf.get('version', 0)
                
                if client_version < server_version:
                    conflicts.append({
                        'id': workflow_id,
                        'server_version': server_version,
                        'client_version': client_version
                    })
                    continue
                
                update_data = {
                    'name': wf.get('name'),
                    'description': wf.get('description'),
                    'nodes': json.dumps(wf.get('nodes', [])),
                    'edges': json.dumps(wf.get('edges', [])),
                    'version': server_version + 1,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'synced_at': datetime.now(timezone.utc).isoformat()
                }
                
                result = supabase.table('workflows')\
                    .update(update_data)\
                    .eq('id', workflow_id)\
                    .eq('user_id', user.id)\
                    .execute()
                
                results.append({'id': workflow_id, 'action': 'updated'})
            else:
                # 创建新工作流
                insert_data = {
                    'id': workflow_id,
                    'user_id': user.id,
                    'name': wf.get('name', 'Untitled'),
                    'description': wf.get('description', ''),
                    'nodes': json.dumps(wf.get('nodes', [])),
                    'edges': json.dumps(wf.get('edges', [])),
                    'is_public': wf.get('is_public', False),
                    'version': 1,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'synced_at': datetime.now(timezone.utc).isoformat()
                }
                
                result = supabase.table('workflows').insert(insert_data).execute()
                results.append({'id': workflow_id, 'action': 'created'})
        
        return jsonify({
            'success': True,
            'results': results,
            'conflicts': conflicts,
            'conflict_count': len(conflicts)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@sync_bp.route('/pull', methods=['GET'])
@require_auth
def pull_workflows():
    """拉取云端工作流到本地"""
    try:
        user = request.user
        last_sync = request.args.get('last_sync_at')
        
        query = supabase.table('workflows')\
            .select('*')\
            .eq('user_id', user.id)
        
        if last_sync:
            query = query.gt('updated_at', last_sync)
        
        result = query.execute()
        workflows = result.data if result.data else []
        
        # 解析JSON字段
        for wf in workflows:
            try:
                wf['nodes'] = json.loads(wf['nodes']) if wf.get('nodes') else []
                wf['edges'] = json.loads(wf['edges']) if wf.get('edges') else []
            except Exception:
                wf['nodes'] = []
                wf['edges'] = []
        
        return jsonify({
            'success': True,
            'workflows': workflows,
            'total': len(workflows)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Conflict Resolution
# ============================================================================

@sync_bp.route('/resolve-conflict', methods=['POST'])
@require_auth
def resolve_conflict():
    """解决同步冲突"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request body'}), 400
    
    workflow_id = data.get('workflow_id')
    resolution = data.get('resolution')  # 'local_wins', 'cloud_wins', 'merge'
    workflow_data = data.get('workflow_data')
    
    if not workflow_id or not resolution:
        return jsonify({'error': 'workflow_id and resolution required'}), 400
    
    try:
        user = request.user
        
        if resolution == 'cloud_wins':
            # 使用云端版本，无需操作
            return jsonify({
                'success': True,
                'message': 'Using cloud version'
            })
        
        elif resolution == 'local_wins':
            # 使用本地版本，强制更新
            if not workflow_data:
                return jsonify({'error': 'workflow_data required for local_wins'}), 400
            
            # 获取云端版本号
            existing = supabase.table('workflows')\
                .select('version')\
                .eq('id', workflow_id)\
                .eq('user_id', user.id)\
                .single()\
                .execute()
            
            server_version = existing.data.get('version', 0) if existing.data else 0
            
            update_data = {
                'name': workflow_data.get('name'),
                'description': workflow_data.get('description'),
                'nodes': json.dumps(workflow_data.get('nodes', [])),
                'edges': json.dumps(workflow_data.get('edges', [])),
                'version': server_version + 1,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'synced_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = supabase.table('workflows')\
                .update(update_data)\
                .eq('id', workflow_id)\
                .eq('user_id', user.id)\
                .execute()
            
            return jsonify({
                'success': True,
                'workflow': result.data[0] if result.data else None
            })
        
        elif resolution == 'merge':
            # 合并版本：将本地数据与云端版本合并（简化策略：本地优先，保留云端版本号+1）
            if not workflow_data:
                return jsonify({'error': 'workflow_data required for merge'}), 400
            
            existing = supabase.table('workflows')\
                .select('version')\
                .eq('id', workflow_id)\
                .eq('user_id', user.id)\
                .single()\
                .execute()
            
            server_version = existing.data.get('version', 0) if existing.data else 0
            
            # Merge strategy: combine nodes/edges from both sides
            # For simplicity, local data wins on conflict, but we bump version
            update_data = {
                'name': workflow_data.get('name'),
                'description': workflow_data.get('description'),
                'nodes': json.dumps(workflow_data.get('nodes', [])),
                'edges': json.dumps(workflow_data.get('edges', [])),
                'version': server_version + 1,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'synced_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = supabase.table('workflows')\
                .update(update_data)\
                .eq('id', workflow_id)\
                .eq('user_id', user.id)\
                .execute()
            
            return jsonify({
                'success': True,
                'message': 'Merged workflow (local data with cloud version bump)',
                'workflow': result.data[0] if result.data else None
            })
        
        else:
            return jsonify({'error': 'Invalid resolution strategy'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Health Check
# ============================================================================

@sync_bp.route('/health', methods=['GET'])
def health_check():
    """同步服务健康检查"""
    return jsonify({
        'status': 'healthy',
        'supabase': 'connected' if supabase else 'disconnected',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
