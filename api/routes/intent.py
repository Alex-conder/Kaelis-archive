"""
Intent Routes - Auto-generated from OpenAPI
Generated at: 2026-04-13T00:50:27.893995
*** DO NOT MODIFY MANUALLY ***
Run `make sync-backend` to regenerate

This module implements the intent API endpoints as defined in contracts/openapi.yaml.
Each route corresponds to an OpenAPI operation with full type safety via Pydantic.

Usage:
    from api.routes.intent import bp
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
    "intent", 
    __name__, 
    url_prefix="/api/intent"
)

# ============================================================================
# Request/Response Models (Auto-generated from OpenAPI schemas)
# ============================================================================


class IntentParseRequest(BaseModel):
    """
    IntentParseRequest
    
    Auto-generated from OpenAPI schema: IntentParseRequest
    """
    
    
    description: str  
    
    
    
    context: Optional[Dict[str, Any]] = None  
    
    
    
        


class IntentParseResponse(BaseModel):
    """
    IntentParseResponse
    
    Auto-generated from OpenAPI schema: IntentParseResponse
    """
    
    
    success: Optional[bool] = None  
    
    
    
    error: Optional[str] = None  
    
    
    
    message: Optional[str] = None  
    
    
    
    timestamp: Optional[datetime] = None  
    
    
    
    data: Optional[Dict[str, Any]] = None  
    
    
    
        


class ExecutionPlan(BaseModel):
    """Minimal execution plan model."""
    steps: List[Dict[str, Any]] = []
    goal: Optional[str] = None


class ExecutePlanRequest(BaseModel):
    """
    ExecutePlanRequest
    
    Auto-generated from OpenAPI schema: ExecutePlanRequest
    """
    
    
    plan: ExecutionPlan  
    
    
    
    dry_run: Optional[bool] = None  
    
    
    
    skip_sandbox: Optional[bool] = None  
    
    
    
        


class ExecutePlanResponse(BaseModel):
    """
    ExecutePlanResponse
    
    Auto-generated from OpenAPI schema: ExecutePlanResponse
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


@bp.route('/api/intent/parse', methods=['POST'])
@validate_request(IntentParseRequest)
@log_request
def intentParse():
    data = g.validated_data
    description = (data.description or "").lower()
    context = data.context or {}

    # Simple keyword-based intent classification
    intent_type = "unknown"
    confidence = 0.5
    if any(w in description for w in ["how", "what", "why", "explain", "?"]):
        intent_type = "question"
        confidence = 0.85
    elif any(w in description for w in ["run", "execute", "do", "perform", "start"]):
        intent_type = "command"
        confidence = 0.8
    elif any(w in description for w in ["analyze", "compare", "evaluate", "assess"]):
        intent_type = "analysis"
        confidence = 0.75
    elif any(w in description for w in ["create", "make", "build", "generate"]):
        intent_type = "creation"
        confidence = 0.7

    return jsonify({
        "success": True,
        "data": {
            "intent_type": intent_type,
            "confidence": confidence,
            "description": data.description,
            "context_keys": list(context.keys()),
            "entities": []
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200


@bp.route('/api/intent/execute', methods=['POST'])
@validate_request(ExecutePlanRequest)
@log_request
def intentExecute():
    data = g.validated_data
    plan = data.plan
    dry_run = data.dry_run or False

    steps = plan.steps if plan and plan.steps else []
    results = []
    for i, step in enumerate(steps):
        results.append({
            "step_index": i,
            "action": step.get("action", "unknown"),
            "status": "simulated" if dry_run else "completed",
            "output": step.get("expected_output")
        })

    return jsonify({
        "success": True,
        "data": {
            "dry_run": dry_run,
            "step_count": len(steps),
            "results": results,
            "goal": plan.goal if plan else None
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
        Health status of the intent service
    """
    return jsonify({
        "status": "healthy",
        "module": "intent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            
            {"path": "/api/intent/parse", "method": "POST"},
            
            {"path": "/api/intent/execute", "method": "POST"},
            
        ]
    }), 200
