"""
扫描前端代码中的用户可见中文字符串，生成 i18n 语言包。
B-2: 多语言国际化基础设施
"""

import json
import re
from pathlib import Path


def extract_user_visible_chinese(src_dir: str) -> dict:
    """提取用户可见的中文字符串（JSX文本、placeholder、title、aria-label等）。"""
    keys = {}
    src = Path(src_dir)

    for path in src.rglob("*.tsx"):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line_no, line in enumerate(lines, 1):
            # 跳过 import 和注释行
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("//") or stripped.startswith("*"):
                continue

            # 模式1: JSX 文本节点 >中文<
            for m in re.finditer(r">([^<>{}]*[\u4e00-\u9fff][^<>{}]*)<", line):
                text = m.group(1).strip()
                if 2 <= len(text) <= 40:
                    key = _make_key(text)
                    keys[key] = text

            # 模式2: placeholder="中文"
            for m in re.finditer(r'placeholder=["\']([^"\']*[\u4e00-\u9fff][^"\']*)["\']', line):
                text = m.group(1).strip()
                if len(text) >= 2:
                    key = _make_key(text)
                    keys[key] = text

            # 模式3: title="中文" 或 aria-label="中文"
            for m in re.finditer(r'(?:title|aria-label|alt)=["\']([^"\']*[\u4e00-\u9fff][^"\']*)["\']', line):
                text = m.group(1).strip()
                if len(text) >= 2:
                    key = _make_key(text)
                    keys[key] = text

            # 模式4: alert('中文') 或 toast('中文')
            for m in re.finditer(r"(?:alert|toast|setError)\s*\(\s*['\"]([^'\"]*[\u4e00-\u9fff][^'\"]*)['\"]", line):
                text = m.group(1).strip()
                if len(text) >= 2:
                    key = _make_key(text)
                    keys[key] = text

    return keys


def _make_key(text: str) -> str:
    """将中文文本转换为 i18n key。"""
    key = text[:25]
    key = re.sub(r"[^\w\s]", "_", key)
    key = re.sub(r"\s+", "_", key)
    key = key.strip("_").lower()
    if not key:
        key = f"text_{hash(text) & 0xFFFFFF:06x}"
    return key


def main():
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "web/frontend/src"

    zh_strings = extract_user_visible_chinese(str(src_dir))
    print(f"Found {len(zh_strings)} user-visible Chinese strings")

    zh_cn = {}
    en_us = {}
    for key, text in zh_strings.items():
        zh_cn[key] = text
        en_us[key] = text  # fallback，后续可人工翻译

    i18n_dir = project_root / "web/frontend/src/i18n/locales"
    i18n_dir.mkdir(parents=True, exist_ok=True)

    with open(i18n_dir / "zh-CN.json", "w", encoding="utf-8") as f:
        json.dump(zh_cn, f, ensure_ascii=False, indent=2)

    with open(i18n_dir / "en-US.json", "w", encoding="utf-8") as f:
        json.dump(en_us, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(zh_cn)} keys to {i18n_dir}")

    # 写入 stdout 样本（避免编码问题）
    with open(i18n_dir / "_sample.txt", "w", encoding="utf-8") as f:
        for k, v in list(zh_cn.items())[:30]:
            f.write(f"{k}: {v}\n")
    print(f"Sample written to {i18n_dir}/_sample.txt")


if __name__ == "__main__":
    main()
