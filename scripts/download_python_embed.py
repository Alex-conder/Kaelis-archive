#!/usr/bin/env python3
"""
Kaelis Python Embedded Runtime Downloader
下载并配置 Python 嵌入式运行时，用于 Electron 零依赖打包
"""

import sys
import os
import zipfile
import urllib.request
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent
RESOURCES_DIR = PROJECT_ROOT / "electron" / "resources"
PYTHON_DIR = RESOURCES_DIR / "python"
CONTRACT_FILE = PROJECT_ROOT / "contracts" / "electron.yaml"


def load_contract():
    import yaml
    if not CONTRACT_FILE.exists():
        print(f"[ERR] Contract file not found: {CONTRACT_FILE}")
        sys.exit(1)
    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_file(url, dest):
    print(f"[INFO] Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)
    print(f"[OK] Saved to {dest}")


def setup_python_embed():
    contract = load_contract()
    cfg = contract.get("python_embed", {})
    version = cfg.get("version", "3.11.9")
    url = cfg.get("url", f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip")
    extra_packages = cfg.get("extra_packages", ["pip", "setuptools", "wheel"])
    requirements_file = cfg.get("required_pip_packages_from", "requirements.txt")

    if (PYTHON_DIR / "python.exe").exists():
        print(f"[SKIP] Python embed already exists at {PYTHON_DIR / 'python.exe'}")
        return

    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PYTHON_DIR / f"python-{version}-embed-amd64.zip"

    if not zip_path.exists():
        download_file(url, zip_path)

    print(f"[INFO] Extracting {zip_path.name} ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(PYTHON_DIR)
    print("[OK] Extraction complete")

    # 修改 python._pth 文件以启用 site-packages
    pth_files = list(PYTHON_DIR.glob("python*._pth"))
    if pth_files:
        pth_file = pth_files[0]
        content = pth_file.read_text(encoding="utf-8")
        lines = []
        for line in content.splitlines():
            if line.strip().startswith("#import site"):
                lines.append("import site")
            else:
                lines.append(line)
        # 确保 Lib/site-packages 在路径中
        if "Lib/site-packages" not in content:
            lines.append("Lib/site-packages")
        pth_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[OK] Updated {pth_file.name}")

    # 安装 pip
    pip_py = PYTHON_DIR / "get-pip.py"
    if not pip_py.exists():
        print("[INFO] Downloading get-pip.py ...")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", pip_py)

    print("[INFO] Installing pip ...")
    subprocess.run(
        [str(PYTHON_DIR / "python.exe"), str(pip_py)],
        check=True,
        cwd=PYTHON_DIR
    )
    print("[OK] pip installed")

    # 升级核心包
    if extra_packages:
        print(f"[INFO] Installing core packages: {', '.join(extra_packages)} ...")
        subprocess.run(
            [str(PYTHON_DIR / "python.exe"), "-m", "pip", "install", "--upgrade"] + extra_packages,
            check=True,
            cwd=PYTHON_DIR
        )
        print("[OK] Core packages installed")

    # 安装项目依赖
    req_path = PROJECT_ROOT / requirements_file
    if req_path.exists():
        print(f"[INFO] Installing requirements from {requirements_file} ...")
        subprocess.run(
            [str(PYTHON_DIR / "python.exe"), "-m", "pip", "install", "-r", str(req_path)],
            check=True,
            cwd=PYTHON_DIR
        )
        print("[OK] Project requirements installed")
    else:
        print(f"[WARN] Requirements file not found: {req_path}")

    print(f"\n[OK] Python {version} embedded runtime ready at {PYTHON_DIR}")


if __name__ == "__main__":
    setup_python_embed()
