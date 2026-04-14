#!/usr/bin/env python3
"""
Static file server for Kaelis frontend
Usage: python server.py [port]
"""

import os
import sys
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='dist')

@app.route('/')
def index():
    return send_from_directory('dist', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('dist', path)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    print(f"Serving Kaelis frontend at http://localhost:{port}/")
    print(f"Static folder: {os.path.abspath('dist')}")
    app.run(host='127.0.0.1', port=port, debug=False)
