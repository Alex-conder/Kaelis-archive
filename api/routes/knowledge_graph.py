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
        with sqlite3.connect(db_path) as conn:
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
    except Exception as e:
        logger.warning("KG persist failed: %s", e)


def _llm_extract(text: str, domain: str = "general") -> tuple[list, list] | None:
    """Use LLM to extract entities and relations. Returns (entities, relations) or None on failure."""
    try:
        from core.llm_client import KaelisLLMClient
        client = KaelisLLMClient()
        system_prompt = (
            "You are a knowledge graph extraction assistant. "
            "Extract entities and relations from the user's text. "
            "Respond ONLY with valid JSON in this exact format:\n"
            '{"entities":[{"text":"entity name","type":"entity type"}],'
            '"relations":[{"source":"entity1","target":"entity2","relation":"relation type"}]}\n'
            "If no entities or relations are found, return empty arrays."
        )
        prompt = f"Domain: {domain}\n\nText:\n{text}"
        response = client.chat(prompt, system_prompt=system_prompt, temperature=0.3)

        import json, re
        # Try to extract JSON from markdown code block or raw text
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        json_str = match.group(1).strip() if match else response.strip()
        data = json.loads(json_str)

        entities = [
            {"text": e["text"], "type": e.get("type", "entity"), "confidence": round(min(0.95, 0.7 + len(e["text"]) * 0.01), 2)}
            for e in data.get("entities", [])
            if e.get("text")
        ]
        relations = [
            {"source": r["source"], "target": r["target"], "relation": r["relation"], "confidence": 0.75}
            for r in data.get("relations", [])
            if r.get("source") and r.get("target") and r.get("relation")
        ]
        logger.info("LLM KG extraction succeeded: %d entities, %d relations", len(entities), len(relations))
        return entities, relations
    except Exception as e:
        logger.warning("LLM KG extraction failed, will fallback to regex: %s", e)
        return None


def _regex_extract(text: str, min_confidence: float = 0.5) -> tuple[list, list]:
    """Fallback regex-based entity and relation extraction."""
    import re
    entities = []
    # English capitalized phrases
    for match in re.finditer(r'\b[A-Z][a-zA-Z\s]{1,20}[a-zA-Z]\b', text):
        ent = match.group(0).strip()
        if len(ent) > 2:
            entities.append({
                "text": ent, "type": "entity",
                "confidence": round(min(0.95, max(min_confidence, 0.5 + len(ent) * 0.01)), 2)
            })
    # Chinese named entities (nouns/phrases 2-10 chars)
    for match in re.finditer(r'[\u4e00-\u9fff]{2,10}', text):
        ent = match.group(0)
        if len(ent) >= 2:
            entities.append({
                "text": ent, "type": "entity",
                "confidence": round(min(0.95, max(min_confidence, 0.5 + len(ent) * 0.02)), 2)
            })
    # Deduplicate
    seen = set()
    unique_entities = []
    for e in entities:
        key = e["text"].lower()
        if key not in seen:
            seen.add(key)
            unique_entities.append(e)

    relations = []
    for i in range(len(unique_entities) - 1):
        relations.append({
            "source": unique_entities[i]["text"], "target": unique_entities[i + 1]["text"],
            "relation": "related_to", "confidence": 0.6
        })
    return unique_entities, relations


@bp.route('/kg/extract', methods=['POST'])
@validate_request(KGExtractRequest)
@log_request
def kgExtract():
    data = g.validated_data
    text = data.text or ""
    domain = data.domain or "general"
    min_confidence = data.min_confidence if data.min_confidence is not None else 0.5

    # Try LLM extraction first, fallback to regex
    llm_result = _llm_extract(text, domain)
    if llm_result:
        unique_entities, relations = llm_result
        method = "llm"
    else:
        unique_entities, relations = _regex_extract(text, min_confidence)
        method = "regex"

    # Persist to database
    _persist_kg_extract(text, unique_entities, relations)

    return jsonify({
        "success": True,
        "data": {
            "domain": domain,
            "method": method,
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


@bp.route('/kg/graph-data', methods=['GET'])
def kg_graph_data():
    """Return all KG entities and relations in G6-compatible format."""
    import sqlite3
    from core.memory_manager_v2 import get_memory_manager
    mm = get_memory_manager()
    db_path = mm._get_db_path("L3")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            entity_rows = conn.execute(
                "SELECT name, type, created_at FROM kg_entities ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
            relation_rows = conn.execute(
                "SELECT source, target, relation, created_at FROM kg_relations ORDER BY created_at DESC LIMIT 200"
            ).fetchall()

        nodes = [
            {"id": f"e-{i}", "name": r["name"], "type": r["type"] or "entity"}
            for i, r in enumerate(entity_rows)
        ]
        # Build entity name -> node id mapping for edge resolution
        name_to_id = {r["name"]: f"e-{i}" for i, r in enumerate(entity_rows)}
        edges = []
        for i, r in enumerate(relation_rows):
            src_id = name_to_id.get(r["source"])
            tgt_id = name_to_id.get(r["target"])
            if src_id and tgt_id:
                edges.append({
                    "id": f"r-{i}",
                    "source": src_id,
                    "target": tgt_id,
                    "relation": r["relation"],
                })

        return jsonify({
            "success": True,
            "data": {"nodes": nodes, "edges": edges},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        logger.exception("KG graph data query failed")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500


@bp.route('/kg/stats', methods=['GET'])
def kg_stats():
    """Return knowledge graph statistics."""
    import sqlite3
    from core.memory_manager_v2 import get_memory_manager
    mm = get_memory_manager()
    db_path = mm._get_db_path("L3")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            entity_count = conn.execute("SELECT COUNT(*) FROM kg_entities").fetchone()[0]
            relation_count = conn.execute("SELECT COUNT(*) FROM kg_relations").fetchone()[0]
            latest_entity = conn.execute(
                "SELECT MAX(created_at) FROM kg_entities"
            ).fetchone()[0]
            latest_relation = conn.execute(
                "SELECT MAX(created_at) FROM kg_relations"
            ).fetchone()[0]

        return jsonify({
            "success": True,
            "data": {
                "entity_count": entity_count,
                "relation_count": relation_count,
                "latest_entity_at": latest_entity,
                "latest_relation_at": latest_relation,
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        logger.exception("KG stats query failed")
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500


@bp.route('/kg/query', methods=['POST'])
@validate_request(KGQueryRequest)
@log_request
def kgQuery():
    """Query KG entities and relations by keyword (semantic fallback to SQLite)."""
    import sqlite3
    from core.memory_manager_v2 import get_memory_manager

    data = g.validated_data
    query = (data.query or "").strip()
    query_type = data.query_type or "semantic"

    if not query:
        return jsonify({
            "success": False,
            "error": "Query text is required"
        }), 400

    mm = get_memory_manager()
    db_path = mm._get_db_path("L3")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Keyword search on entities (name LIKE) and relations (source/target LIKE)
            like_pattern = f"%{query}%"
            entities = conn.execute(
                "SELECT name, type, source, created_at FROM kg_entities WHERE name LIKE ? OR type LIKE ? OR source LIKE ? ORDER BY created_at DESC LIMIT 50",
                (like_pattern, like_pattern, like_pattern)
            ).fetchall()

            relations = conn.execute(
                "SELECT source, target, relation, created_at FROM kg_relations WHERE source LIKE ? OR target LIKE ? OR relation LIKE ? ORDER BY created_at DESC LIMIT 50",
                (like_pattern, like_pattern, like_pattern)
            ).fetchall()

            results = []
            for r in entities:
                results.append({
                    "type": "entity",
                    "name": r["name"],
                    "entity_type": r["type"],
                    "source": r["source"],
                    "created_at": r["created_at"],
                })
            for r in relations:
                results.append({
                    "type": "relation",
                    "source": r["source"],
                    "target": r["target"],
                    "relation": r["relation"],
                    "created_at": r["created_at"],
                })

        return jsonify({
            "success": True,
            "data": {
                "query": query,
                "query_type": query_type,
                "results": results,
                "result_count": len(results),
                "note": "Keyword search against SQLite KG store."
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        logger.exception("KG query failed")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
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
            {"path": "/api/kg/history", "method": "GET"},
            {"path": "/api/kg/stats", "method": "GET"},
            {"path": "/api/kg/query", "method": "POST"},
        ]
    }), 200
