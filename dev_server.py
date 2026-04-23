#!/usr/bin/env python3
"""Development server entry for testing."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prod_server import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
