#!/usr/bin/env python3
"""
Kaelis Electron Smoke Test
打包后自动运行烟雾测试，验证应用可启动且后端服务就绪
"""

import sys
import os
import time
import subprocess
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RELEASE_DIR = PROJECT_ROOT / "release"
HEALTH_URL = "http://localhost:5000/api/auth/health"
TIMEOUT_SECONDS = 60


def find_executable():
    """查找打包后的可执行文件"""
    sys_platform = sys.platform
    if sys_platform == "win32":
        candidates = list(RELEASE_DIR.glob("win-unpacked/*.exe"))
        if not candidates:
            candidates = list(RELEASE_DIR.glob("**/*.exe"))
    elif sys_platform == "darwin":
        candidates = list(RELEASE_DIR.glob("**/*.app"))
    else:
        candidates = list(RELEASE_DIR.glob("**/*.AppImage"))

    if not candidates:
        print(f"[FAIL] No Electron executable found in {RELEASE_DIR}")
        return None

    return candidates[0]


def start_app(exe_path):
    """启动应用并返回进程"""
    print(f"[INFO] Starting application: {exe_path}")
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    out_log = open(log_dir / "electron_smoke_stdout.log", "w")
    err_log = open(log_dir / "electron_smoke_stderr.log", "w")
    if sys.platform == "win32":
        proc = subprocess.Popen(
            [str(exe_path)],
            stdout=out_log,
            stderr=err_log,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    else:
        proc = subprocess.Popen(
            [str(exe_path)],
            stdout=out_log,
            stderr=err_log
        )
    proc._out_log = out_log
    proc._err_log = err_log
    return proc


def wait_for_health(timeout=TIMEOUT_SECONDS):
    """轮询后端健康检查"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(HEALTH_URL, method="GET")
            with urllib.request.urlopen(req, timeout=2) as res:
                if res.status == 200:
                    data = res.read().decode()
                    print(f"[PASS] Backend health check passed: {data}")
                    return True
        except Exception:
            pass
        time.sleep(1)
    print(f"[FAIL] Backend health check failed after {timeout}s")
    return False


def kill_process(proc):
    """终止应用进程"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], check=False)
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception as e:
        print(f"[WARN] Failed to terminate process: {e}")
    finally:
        if hasattr(proc, '_out_log'):
            proc._out_log.close()
        if hasattr(proc, '_err_log'):
            proc._err_log.close()


def main():
    print("=" * 60)
    print("Kaelis Electron Smoke Test")
    print("=" * 60)

    exe_path = find_executable()
    if not exe_path:
        sys.exit(1)

    proc = start_app(exe_path)
    time.sleep(3)  # 给 Electron 窗口创建留出时间

    try:
        print("[INFO] Waiting for backend service to be ready...")
        health_ok = wait_for_health()

        if health_ok:
            print("\n[PASS] Smoke test passed! Application starts correctly.")
            return_code = 0
        else:
            print("\n[FAIL] Smoke test failed! Backend did not become healthy.")
            return_code = 1
    finally:
        print("[INFO] Shutting down application...")
        kill_process(proc)
        time.sleep(2)

    sys.exit(return_code)


if __name__ == "__main__":
    main()
