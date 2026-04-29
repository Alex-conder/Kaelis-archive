"""
Pytest configuration and shared fixtures
Auto-generated from OpenAPI specification
Generated at: 2026-04-13T00:50:28.280207
"""

import os
import pytest
import json

# CI 稳定性：禁用 ChromaDB ONNX 模型自动下载，避免网络超时
os.environ.setdefault("CHROMA_DISABLE_ONNX", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


@pytest.fixture
def api_base_url():
    """Base URL for API tests"""
    return "http://localhost:5000"


@pytest.fixture
def api_headers():
    """Default headers for API requests"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


@pytest.fixture
def sample_kg_extract_request():
    """Sample request for KG extract endpoint"""
    return {
        "text": "代谢物具有抗氧化功能",
        "domain": "metabolomics",
        "min_confidence": 0.7
    }


@pytest.fixture
def sample_report_export_request():
    """Sample request for report export endpoint"""
    return {
        "report_type": "knowledge_graph",
        "format": "pdf",
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31"
        }
    }


# TODO: Add more fixtures for other endpoints
