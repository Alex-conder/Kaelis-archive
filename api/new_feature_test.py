"""Test auto-discovery of new module"""
from api.routes.system import bp as system_bp
from api.routes.knowledge_graph import bp as kg_bp

# Use environment variable
import os
API_KEY = os.getenv("NEW_TEST_API_KEY", "default")
