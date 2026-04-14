#!/usr/bin/env python3
"""
Kaelis Electron Config Generator
读取 contracts/electron.yaml，生成 Electron 相关配置文件
"""

import sys
import json
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONTRACT_FILE = PROJECT_ROOT / "contracts" / "electron.yaml"
ELECTRON_DIR = PROJECT_ROOT / "web" / "frontend" / "electron"
BUILDER_JSON = PROJECT_ROOT / "electron-builder.json"


def load_contract():
    if not CONTRACT_FILE.exists():
        print(f"[ERR] Contract file not found: {CONTRACT_FILE}")
        sys.exit(1)
    with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_builder_json(contract):
    build = contract["build"]
    app = contract["app"]

    files = [
        "dist/**/*",
        f"{ELECTRON_DIR.name}/**/*",
        "package.json"
    ]

    extra_resources = []
    for res in build.get("extra_resources", []):
        entry = {
            "from": f"../../{res['from']}",
            "to": res["to"]
        }
        if "filter" in res:
            entry["filter"] = res["filter"]
        extra_resources.append(entry)

    builder = {
        "appId": app["appId"],
        "productName": app["name"],
        "directories": {
            "output": "../../release",
            "buildResources": "../../electron/assets"
        },
        "files": files,
        "extraResources": extra_resources,
        "publish": None
    }

    for target_def in build.get("targets", []):
        platform = target_def["platform"]
        key = "mac" if platform == "mac" else ("win" if platform == "win" else "linux")
        builder[key] = {
            "target": [{"target": target_def["target"], "arch": target_def["arch"]}],
            "icon": f"../../electron/assets/icon.{platform_icon_ext(platform)}"
        }
        if platform == "mac":
            builder[key]["category"] = "public.app-category.developer-tools"
        if platform == "linux":
            builder[key]["category"] = "Development"

    installer = build.get("installer", {}).get("windows", {})
    builder["nsis"] = {
        "oneClick": installer.get("one_click", False),
        "allowToChangeInstallationDirectory": installer.get("allow_directory_change", True),
        "perMachine": installer.get("per_machine", False),
        "createDesktopShortcut": installer.get("create_desktop_shortcut", True),
        "createStartMenuShortcut": installer.get("create_start_menu_shortcut", True),
        "shortcutName": installer.get("shortcut_name", app["name"])
    }

    with open(BUILDER_JSON, "w", encoding="utf-8") as f:
        json.dump(builder, f, indent=2, ensure_ascii=False)
    print(f"[OK] Generated {BUILDER_JSON}")


def platform_icon_ext(platform):
    return {"win": "ico", "mac": "icns", "linux": "png"}.get(platform, "png")


def generate_main_skeleton(contract):
    module_type = contract["app"]["module_type"]
    main_entry = contract["main_process"]["entry"]
    ext = ".cjs" if module_type == "commonjs" else ".mjs"
    target_file = ELECTRON_DIR / f"main{ext}"

    # 仅当文件不存在时生成骨架，避免覆盖已实现的业务逻辑
    if target_file.exists():
        print(f"[SKIP] Main process file already exists: {target_file}")
        return

    if module_type == "commonjs":
        content = '''/**
 * Kaelis Desktop - Electron Main Process (CommonJS)
 * Generated from contracts/electron.yaml
 */

const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // Load frontend dist or dev server based on environment
  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
'''
    else:
        content = '''/**
 * Kaelis Desktop - Electron Main Process (ES Module)
 * Generated from contracts/electron.yaml
 */

import { app, BrowserWindow } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (process.env.NODE_ENV === 'development') {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
'''

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Generated main process skeleton: {target_file}")


def generate_preload_skeleton(contract):
    module_type = contract["app"]["module_type"]
    ext = ".cjs" if module_type == "commonjs" else ".mjs"
    target_file = ELECTRON_DIR / f"preload{ext}"

    if target_file.exists():
        print(f"[SKIP] Preload script already exists: {target_file}")
        return

    if module_type == "commonjs":
        content = '''const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  checkHealth: () => ipcRenderer.invoke('check-health'),
});
'''
    else:
        content = '''import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  getConfig: () => ipcRenderer.invoke('get-config'),
  checkHealth: () => ipcRenderer.invoke('check-health'),
});
'''

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Generated preload skeleton: {target_file}")


def update_frontend_package_json(contract):
    pkg_path = PROJECT_ROOT / "web" / "frontend" / "package.json"
    if not pkg_path.exists():
        print(f"[ERR] package.json not found: {pkg_path}")
        sys.exit(1)

    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    main_entry = contract["main_process"]["entry"]
    module_type = contract["app"]["module_type"]

    pkg["main"] = main_entry
    if module_type == "module":
        pkg["type"] = "module"
    else:
        pkg.pop("type", None)  # 移除 type 字段，默认按 CommonJS 处理

    with open(pkg_path, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2, ensure_ascii=False)
    print(f"[OK] Updated {pkg_path}")


def main():
    contract = load_contract()
    generate_builder_json(contract)
    generate_main_skeleton(contract)
    generate_preload_skeleton(contract)
    update_frontend_package_json(contract)
    print("\n[OK] All Electron configurations generated from contract.")


if __name__ == "__main__":
    main()
