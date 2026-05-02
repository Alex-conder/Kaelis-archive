"""
Knowledge_Graph Routes - Auto-generated from OpenAPI
Generated at: 2026-04-13T00:50:27.892533
*** DO NOT MODIFY MANUALLY ***
Run `make sync-backend` to regenerate

This module implements the knowledge_graph API endpoints as defined in contracts/openapi.yaml.
Each route corresponds to an OpenAPI operation with full type safety via Pydantic.

Usage:
    from api.routes.knowledge_graph import bp
    app.register_blueprint(bp)
"""

from flask import Blueprint, request, jsonify, g
from pydantic import BaseModel, ValidationError, Field
from typing import Any, Optional, List, Dict
from datetime import datetime, timezone
from functools import wraps
import logging

# Configure logger
logger = logging.getLogger(__name__)

# ============================================================================
# Blueprint Definition
# ============================================================================

bp = Blueprint(
    "knowledge_graph", 
    __name__, 
    url_prefix="/api/knowledge_graph"
)

# ============================================================================
# Request/Response Models (Auto-generated from OpenAPI schemas)
# ============================================================================


class KGExtractRequest(BaseModel):
    """
    KGExtractRequest
    
    Auto-generated from OpenAPI schema: KGExtractRequest
    """
    
    
    text: str  
    
    
    
    domain: Optional[str] = None  
    
    
    
    min_confidence: Optional[float] = None  
    
    
    
        


class KGExtractResponse(BaseModel):
    """
    KGExtractResponse
    
    Auto-generated from OpenAPI schema: KGExtractResponse
    """
    
    
    success: Optional[bool] = None  
    
    
    
    error: Optional[str] = None  
    
    
    
    message: Optional[str] = None  
    
    
    
    timestamp: Optional[datetime] = None  
    
    
    
    data: Optional[Dict[str, Any]] = None  
    
    
    
        


class KGQueryRequest(BaseModel):
    """
    KGQueryRequest
    
    Auto-generated from OpenAPI schema: KGQueryRequest
    """
    
    
    query: str  
    
    
    
    query_type: Optional[str] = None  
    
    
    
        


class KGQueryResponse(BaseModel):
    """
    KGQueryResponse
    
    Auto-generated from OpenAPI schema: KGQueryResponse
    """
    
    
    success: Optional[bool] = None  
    
    
    
    error: Optional[str] = None  
    
    
    
    message: Optional[str] = None  
    
    
    
    timestamp: Optional[datetime] = None  
    
    
    
    data: Optional[Dict[str, Any]] = None  
    
    
    
        


class BaseResponse(BaseModel):
    """
    BaseResponse
    
    Auto-generated from OpenAPI schema: BaseResponse
    """
    
    
    success: bool  
    
    
    
    error: Optional[str] = None  
    
    
    
    message: Optional[str] = None  
    
    
    
    timestamp: Optional[datetime] = None  
    
    
    
        


# ============================================================================
# Error Handling
# ============================================================================

def handle_validation_error(e: ValidationError) -> tuple:
    """
    Convert Pydantic validation errors to API response.
    
    Args:
        e: ValidationError from Pydantic
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    errors = []
    for error in e.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return jsonify({
        "success": False,
        "error": "Validation failed",
        "details": errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 400


def handle_exception(e: Exception) -> tuple:
    """
    Convert unexpected exceptions to API response.
    
    Args:
        e: Exception that occurred
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    logger.exception("Unhandled exception in route")
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": str(e) if request.app.debug else "An unexpected error occurred",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 500

# ============================================================================
# Decorators
# ============================================================================

def validate_request(model_class: type):
    """
    Decorator to validate request body against Pydantic model.
    
    Args:
        model_class: Pydantic model class to validate against
        
    Usage:
        @validate_request(KGExtractRequest)
        def kgExtract():
            data = g.validated_data
            # ... use validated data
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                # Get JSON data from request
                json_data = request.get_json(silent=True) or {}
                
                # Validate against model
                validated = model_class(**json_data)
                
                # Store in Flask g object for access in route
                g.validated_data = validated
                g.raw_data = json_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                return handle_validation_error(e)
            except Exception as e:
                return handle_exception(e)
        
        return wrapper
    return decorator


def log_request(f):
    """Decorator to log incoming requests."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        logger.info(
            f"[{request.method}] {request.path} - "
            f"IP: {request.remote_addr} - "
            f"Content-Type: {request.content_type}"
        )
        return f(*args, **kwargs)
    return wrapper

# ============================================================================
# Route Implementations
# ============================================================================


def _persist_kg_extract(text: str, entities: list, relations: list):
    """Persist extracted entities and relations to SQLite."""
    import sqlite3
    from core.memory_manager_v2 import get_memory_manager
    mm = get_memory_manager()
    db_path = mm._get_db_path("L3")
    try:
        conn = sqlite3.connect(db_path)
        try:
            now = datetime.now(timezone.utc).isoformat()
            for e in entities:
                conn.execute(
                    "INSERT OR IGNORE INTO kg_entities (name, type, source, created_at) VALUES (?, ?, ?, ?)",
                    (e["text"], e.get("type", "entity"), "kg_extract", now)
                )
            for r in relations:
                conn.execute(
                    "INSERT INTO kg_relations (source, target, relation, source_text, created_at) VALUES (?, ?, ?, ?, ?)",
                    (r["source"], r["target"], r["relation"], text[:200], now)
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("KG persist failed: %s", e)


@bp.route('/kg/extract', methods=['POST'])
@validate_request(KGExtractRequest)
@log_request
def kgExtract():
    data = g.validated_data
    text = data.text or ""
    domain = data.domain or "general"
    min_confidence = data.min_confidence if data.min_confidence is not None else 0.5

    # Simple keyword-based entity extraction
    import re
    entities = []
    # Extract capitalized phrases as potential entities
    for match in re.finditer(r'\b[A-Z][a-zA-Z\s]{1,20}[a-zA-Z]\b', text):
        ent = match.group(0).strip()
        if len(ent) > 2:
            entities.append({
                "text": ent,
                "type": "entity",
                "confidence": round(min(0.95, max(min_confidence, 0.5 + len(ent) * 0.01)), 2)
            })
    # Deduplicate
    seen = set()
    unique_entities = []
    for e in entities:
        key = e["text"].lower()
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    # Simple relation extraction based on proximity
    relations = []
    for i in range(len(unique_entities) - 1):
        relations.append({
            "source": unique_entities[i]["text"],
            "target": unique_entities[i + 1]["text"],
            "relation": "related_to",
            "confidence": 0.6
        })

    # Persist to database
    _persist_kg_extract(text, unique_entities, relations)

    return jsonify({
        "success": True,
        "data": {
            "domain": domain,
            "entities": unique_entities[:20],
            "relations": relations[:10],
            "entity_count": len(unique_entities),
            "relation_count": len(relations)
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@bp.route('/kg/history', methods=['GET'])
@log_request
def kg_history():
    """Return historical KG entities and relations within a time range."""
    import sqlite3
    from core.memory_manager_v2 import get_memory_manager

    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    limit = request.args.get("limit", 100, type=int)

    mm = get_memory_manager()
    db_path = mm._get_db_path("L3")

    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            params = []
            where_clauses = []

            if start_time:
                where_clauses.append("created_at >= ?")
                params.append(start_time)
            if end_time:
                where_clauses.append("created_at <= ?")
                params.append(end_time)

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            entities = conn.execute(
                f"SELECT name, type, source, created_at FROM kg_entities {where_sql} ORDER BY created_at DESC LIMIT ?",
                params + [limit]
            ).fetchall()

            relations = conn.execute(
                f"SELECT source, target, relation, created_at FROM kg_relations {where_sql} ORDER BY created_at DESC LIMIT ?",
                params + [limit]
            ).fetchall()

            return jsonify({
                "success": True,
                "data": {
                    "entities": [dict(r) for r in entities],
                    "relations": [dict(r) for r in relations],
                    "entity_count": len(entities),
                    "relation_count": len(relations),
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 200
        finally:
            conn.close()
    except Exception as e:
        logger.exception("KG history query failed")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500


@bp.route('/kg/query', methods=['POST'])
@validate_request(KGQueryRequest)
@log_request
def kgQuery():
    data = g.validated_data
    query = data.query or ""
    query_type = data.query_type or "semantic"

    return jsonify({
        "success": True,
        "data": {
            "query": query,
            "query_type": query_type,
            "results": [],
            "result_count": 0,
            "note": "Knowledge graph query requires a configured graph store."
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200
# ============================================================================
# Health Check Endpoint
# ============================================================================

@bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for this module.
    
    Returns:
        Health status of the knowledge_graph service
    """
    return jsonify({
        "status": "healthy",
        "module": "knowledge_graph",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            
            {"path": "/api/kg/extract", "method": "POST"},
            
            {"path": "/api/kg/query", "method": "POST"},
            
        ]
    }), 200
