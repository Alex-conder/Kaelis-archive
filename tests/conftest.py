"""
Pytest configuration and shared fixtures
Auto-generated from OpenAPI specification
Generated at: 2026-04-13T00:50:28.280207
"""

import os
import pytest
import json
import pathlib
import os
import warnings

# CI 稳定性：禁用 ChromaDB ONNX 模型自动下载，避免网络超时
os.environ.setdefault("CHROMA_DISABLE_ONNX", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


# =====================================================================
# Global data directory isolation -- C1 contract: test environment isolation
# =====================================================================

_original_path_init = pathlib.Path.__init__


def _isolated_path_init(self, *args, **kwargs):
    """Redirect Path('data/...') to a temporary directory during tests."""
    if args:
        first = str(args[0])
        test_dir = os.environ.get("_KAELIS_TEST_DATA_DIR")
        if test_dir:
            relative = None
            if first.startswith(("data/", "data\\")):
                relative = first[5:].lstrip("/\\")
            elif first in ("data", "data/", "data\\"):
                relative = ""
            elif first.startswith(("./data/", ".\\data\\")):
                relative = first[7:].lstrip("/\\")
            elif first in ("./data", ".\\data"):
                relative = ""

            if relative is not None:
                new_path = str(pathlib.Path(test_dir) / relative) if relative else test_dir
                args = (new_path,) + args[1:]
    return _original_path_init(self, *args, **kwargs)


# Apply the patch globally. It only activates when _KAELIS_TEST_DATA_DIR is set.
pathlib.Path.__init__ = _isolated_path_init


@pytest.fixture(autouse=True)
def isolate_data_dir(monkeypatch, tmp_path, request):
    """
    Redirect data/ directory access to a per-test temporary directory.

    1. Sets _KAELIS_TEST_DATA_DIR so the patched Path.__init__ redirects
       any Path("data") or Path("data/...") to tmp_path/kaelis_data.
    2. Sets KAELIS_DATA_DIR environment variable for future code that
       respects it explicitly.
    3. After the test, warns if any new files appeared in the real data/ dir.
    """
    test_data = tmp_path / "kaelis_data"
    test_data.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("_KAELIS_TEST_DATA_DIR", str(test_data))
    monkeypatch.setenv("KAELIS_DATA_DIR", str(test_data))

    # Reset global memory manager singleton so each test gets a fresh instance
    # pointing to the isolated temporary directory (C1 contract)
    try:
        import core.memory_manager_v2 as mm_module
        mm_module._mm_instance = None
    except Exception:
        pass

    # Capture baseline of real data/ directory
    # Use os.walk to avoid the patched Path() redirecting to temp dir
    baseline = set()
    if os.path.isdir("data"):
        for root, _, files in os.walk("data"):
            for f in files:
                baseline.add(os.path.relpath(os.path.join(root, f), "data").replace("\\", "/"))

    yield test_data

    # Detect any new files written to real data/
    current = set()
    if os.path.isdir("data"):
        for root, _, files in os.walk("data"):
            for f in files:
                current.add(os.path.relpath(os.path.join(root, f), "data").replace("\\", "/"))
    new_files = current - baseline
    if new_files:
        # Raise warning (not error) to avoid breaking existing tests
        warnings.warn(
            f"Test '{request.node.nodeid}' wrote to production data/ directory: {sorted(new_files)}",
            RuntimeWarning,
            stacklevel=2,
        )


# =====================================================================
# Existing fixtures
# =====================================================================

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
        "text": "\u4ee3\u8c22\u7269\u5177\u6709\u6297\u6c27\u5316\u529f\u80fd",
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
