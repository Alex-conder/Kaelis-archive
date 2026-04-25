"""
AutoImmune-2: 依赖一致性自动校验与修复
扫描所有 .py 文件的 import 语句，对比 requirements.txt，
发现缺失时报告并尝试自动安装。
"""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# 标准库模块列表（Python 3.12）
STDLIB = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "atexit",
    "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins",
    "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd", "code",
    "codecs", "codeop", "collections", "colorsys", "compileall", "concurrent",
    "configparser", "contextlib", "contextvars", "copy", "copyreg", "cProfile",
    "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm",
    "decimal", "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass", "gettext",
    "glob", "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html",
    "http", "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect",
    "io", "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re",
    "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets",
    "select", "selectors", "shelve", "shlex", "shutil", "signal", "site",
    "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo",
    # 常用但常被误认为第三方的
    "typing_extensions", "_thread", "__future__", "fractions", "numbers",
    "csv", "html", "xml", "http", "email", "json", "urllib", " pathlib",
    "msvcrt", "pkg_resources", "pkgutil", "setuptools", "pip", "wheel",
    "distutils", "ensurepip", "idlelib", "lib2to3", "tkinter", "turtledemo",
}

# import 名称 -> requirements.txt 包名 映射
IMPORT_TO_PACKAGE: Dict[str, str] = {
    "flask": "flask",
    "flask_cors": "flask-cors",
    "waitress": "waitress",
    "dotenv": "python-dotenv",
    "chromadb": "chromadb",
    "faiss": "faiss-cpu",
    "neo4j": "neo4j",
    "yaml": "pyyaml",
    "sqlalchemy": "sqlalchemy",
    "supabase": "supabase",
    "langchain": "langchain",
    "langchain_community": "langchain-community",
    "langchain_core": "langchain-core",
    "langchain_openai": "langchain-openai",
    "langchain_text_splitters": "langchain-text-splitters",
    "openai": "openai",
    "anthropic": "anthropic",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "sklearn": "scikit-learn",
    "pypdf": "pypdf",
    "duckduckgo_search": "duckduckgo-search",
    "requests": "requests",
    "diskcache": "diskcache",
    "simpleeval": "simpleeval",
    "watchdog": "watchdog",
    "PIL": "pillow",
    "prometheus_client": "prometheus-client",
    "apscheduler": "apscheduler",
    "psutil": "psutil",
    "matplotlib": "matplotlib",
    "cv2": "opencv-python",
    "pyautogui": "pyautogui",
    "pynput": "pynput",
    "mcp": "mcp",
    "pydantic": "pydantic",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "tqdm": "tqdm",
    "jinja2": "jinja2",
    "werkzeug": "werkzeug",
    "markupsafe": "markupsafe",
    "itsdangerous": "itsdangerous",
    "click": "click",
    "cryptography": "cryptography",
    "jwt": "pyjwt",
    "bcrypt": "bcrypt",
    "passlib": "passlib",
    "httpx": "httpx",
    "aiohttp": "aiohttp",
    "websockets": "websockets",
    "sseclient": "sseclient",
    "grpc": "grpcio",
    "protobuf": "protobuf",
    "pytest": "pytest",
    "black": "black",
    "mypy": "mypy",
    "ruff": "ruff",
    "isort": "isort",
    "coverage": "coverage",
    "sphinx": "sphinx",
    "mkdocs": "mkdocs",
    "twine": "twine",
    "build": "build",
    "setuptools": "setuptools",
    "wheel": "wheel",
    "pip": "pip",
    "packaging": "packaging",
    "toml": "toml",
    "tomli": "tomli",
    "tomllib": "tomli",
    "anyio": "anyio",
    "sniffio": "sniffio",
    "idna": "idna",
    "certifi": "certifi",
    "charset_normalizer": "charset-normalizer",
    "urllib3": "urllib3",
    "zstandard": "zstandard",
    "brotli": "brotli",
}

# 忽略的项目内部模块前缀
INTERNAL_PREFIXES = {"core", "api", "scripts", "tests", "web", "electron", "vscode_kaelis", "services"}


def _build_internal_modules() -> Set[str]:
    """扫描项目目录，建立内部模块名称集合"""
    internal = set()
    for src_dir in ["core", "api", "scripts", "tests"]:
        if not os.path.isdir(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    internal.add(file[:-3])
            for d in dirs:
                if not d.startswith("__") and not d.startswith("."):
                    internal.add(d)
    return internal


_INTERNAL_MODULES = _build_internal_modules()


def scan_imports(src_dirs: List[str] = None) -> Set[str]:
    """扫描所有第三方 import"""
    if src_dirs is None:
        src_dirs = ["core", "api", "scripts"]

    third_party: Set[str] = set()

    for src_dir in src_dirs:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            pkg = alias.name.split(".")[0]
                            if _is_third_party(pkg):
                                third_party.add(pkg)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            pkg = node.module.split(".")[0]
                            if _is_third_party(pkg):
                                # 记录 from 的模块名（用于检查子模块）
                                sub_pkg = node.module.split(".")[-1] if "." in node.module else node.module
                                # 如果是 from xxx import yyy 且 xxx 不是内部前缀，但 yyy 可能是内部模块
                                # 这里我们只关心 pkg 级别
                                third_party.add(pkg)

    return third_party


def _is_third_party(pkg: str) -> bool:
    """判断是否为第三方包（排除标准库和项目内部模块）"""
    if pkg in STDLIB:
        return False
    if pkg in INTERNAL_PREFIXES:
        return False
    if pkg in _INTERNAL_MODULES:
        return False
    if pkg.startswith("test_") or pkg.endswith("_test"):
        return False
    return True


def scan_requirements(req_file: str = "requirements.txt") -> Dict[str, str]:
    """解析 requirements.txt，返回 {normalized_pkg: original_line}"""
    declared: Dict[str, str] = {}
    if not os.path.exists(req_file):
        return declared

    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 提取包名（去掉版本约束和 extras）
            pkg = line.split("[")[0].split(">=")[0].split("==")[0].split("<")[0].strip().lower()
            declared[pkg] = line
    return declared


def check_deps() -> Tuple[Set[str], Set[str], Set[str]]:
    """
    检查依赖一致性。
    返回: (missing_packages, uninstalled_packages, extra_packages)
    """
    imports = scan_imports()
    declared = scan_requirements()

    # 忽略的包：间接依赖或仅诊断脚本使用
    IGNORE_PACKAGES = {"anyio", "torch"}

    # import 名称 -> requirements 包名
    required_packages: Set[str] = set()
    for imp in imports:
        pkg = IMPORT_TO_PACKAGE.get(imp, imp)
        if pkg.lower() not in IGNORE_PACKAGES:
            required_packages.add(pkg.lower())

    # 缺失声明：在代码中 import 但 requirements.txt 中没有
    declared_keys = set(declared.keys())
    missing = required_packages - declared_keys

    # 未安装：requirements.txt 中有但 pip 环境中没有
    uninstalled: Set[str] = set()
    try:
        import importlib.metadata
        installed = {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}
        for pkg in declared_keys:
            # 处理一些特殊的包名映射
            check_names = {pkg}
            if pkg == "faiss-cpu":
                check_names.add("faiss")
            if pkg == "pillow":
                check_names.add("pil")
            if pkg == "opencv-python":
                check_names.add("cv2")
            if pkg == "scikit-learn":
                check_names.add("sklearn")
            if pkg == "langchain-community":
                check_names.add("langchain_community")
            if pkg == "langchain-core":
                check_names.add("langchain_core")
            if pkg == "langchain-openai":
                check_names.add("langchain_openai")
            if pkg == "flask-cors":
                check_names.add("flask_cors")
            if pkg == "python-dotenv":
                check_names.add("dotenv")
            if pkg == "prometheus-client":
                check_names.add("prometheus_client")
            if pkg == "beautifulsoup4":
                check_names.add("bs4")
            if pkg == "pyyaml":
                check_names.add("yaml")
            if pkg == "duckduckgo-search":
                check_names.add("duckduckgo_search")
            if pkg == "typing-extensions":
                check_names.add("typing_extensions")
            if not check_names & installed:
                uninstalled.add(pkg)
    except Exception as e:
        print(f"[WARN] Could not check installed packages: {e}")

    # 多余声明：requirements.txt 中有但代码中未 import
    extra = declared_keys - required_packages
    # 排除一些常见的运行时依赖（如 gunicorn, pytest 等）
    runtime_extras = {"gunicorn", "pytest", "pytest-cov", "pytest-asyncio", "black", "mypy", "ruff", "isort", "coverage", "sphinx", "mkdocs", "twine", "build", "setuptools", "wheel", "pip", "pre-commit", "husky"}
    extra = extra - runtime_extras

    return missing, uninstalled, extra


def auto_fix_install(uninstalled: Set[str]) -> List[str]:
    """尝试自动安装缺失的依赖"""
    installed = []
    for pkg in sorted(uninstalled):
        print(f"  Installing {pkg}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
            installed.append(pkg)
            print(f"    [OK] {pkg} installed")
        except subprocess.CalledProcessError as e:
            print(f"    [FAIL] {pkg}: {e}")
    return installed


def generate_requirements_patch(missing: Set[str]) -> str:
    """生成 requirements.txt 补全建议"""
    lines = []
    for imp in sorted(missing):
        pkg = IMPORT_TO_PACKAGE.get(imp, imp)
        lines.append(f"{pkg}>=0.0.0  # auto-detected from import '{imp}'")
    return "\n".join(lines)


def main():
    apply = "--apply" in sys.argv

    print("=" * 60)
    print(" AutoImmune-2: Dependency Consistency Check & Fix")
    print("=" * 60)

    missing, uninstalled, extra = check_deps()

    if not missing and not uninstalled and not extra:
        print("\n[OK] All dependencies are consistent.")
        return 0

    if missing:
        print(f"\n[WARN] {len(missing)} packages imported but not declared in requirements.txt:")
        for pkg in sorted(missing):
            print(f"  - {pkg}")
        print("\n[PLAN] Append to requirements.txt:")
        print(generate_requirements_patch(missing))

    if uninstalled:
        print(f"\n[WARN] {len(uninstalled)} packages declared but not installed:")
        for pkg in sorted(uninstalled):
            print(f"  - {pkg}")
        if apply:
            installed = auto_fix_install(uninstalled)
            print(f"\n[OK] Auto-installed {len(installed)}/{len(uninstalled)} packages.")
        else:
            print("\n[INFO] Run with --apply to auto-install missing packages.")

    if extra:
        print(f"\n[INFO] {len(extra)} packages declared but not imported in source:")
        for pkg in sorted(extra):
            print(f"  - {pkg}")

    return len(missing) + len(uninstalled)


if __name__ == "__main__":
    sys.exit(main())
