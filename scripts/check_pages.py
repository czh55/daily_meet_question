#!/usr/bin/env python3
"""校验站点完整性。

1. 精讲完整性：归档页必须含考察意图 / 回答框架 / 参考答案 / 追问 / 踩坑 / 记忆锚点
2. 首页一致性：index.html 与 history.json 对齐
3. 分类配色：CATEGORY_CLASS_MAP 中每个 class 在 style.css 有 .tag-xxx
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.generate import CATEGORY_CLASS_MAP

DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive"
DATA = ROOT / "data"
HISTORY_FILE = DATA / "history.json"
INDEX_FILE = DOCS / "index.html"
STYLE_FILE = DOCS / "style.css"

REQUIRED = {
    "考察意图": "考察意图",
    "回答框架": 'class="answer-framework"',
    "参考答案": 'class="answer-body"',
    "追问": 'class="followups"',
    "常见踩坑": 'class="pitfalls"',
    "记忆锚点": 'class="anchor-quote"',
}


def check_page(html: str) -> list:
    return [name for name, marker in REQUIRED.items() if marker not in html]


def check_index_consistency(history: list) -> list:
    problems = []
    if not INDEX_FILE.exists():
        return [("index.html", "首页文件不存在")]

    index_html = INDEX_FILE.read_text(encoding="utf-8")

    for date_str in sorted(set(re.findall(r"archive/(\d{4}-\d{2}-\d{2})\.html", index_html))):
        if not (ARCHIVE / f"{date_str}.html").exists():
            problems.append((date_str, f"首页链接指向的 archive/{date_str}.html 不存在"))

    for item in history:
        date_str = item.get("date", "")
        if not date_str:
            continue
        if not (ARCHIVE / f"{date_str}.html").exists():
            problems.append((date_str, f"归档页 archive/{date_str}.html 不存在"))
        if f"archive/{date_str}.html" not in index_html:
            problems.append((date_str, "首页缺少该题的归档链接"))

    cards = re.findall(
        r'class="problem-type tag-[\w-]+">([^<]+)</span>\s*<span class="type-count">(\d+) 题</span>',
        index_html,
    )
    actual_counts = {name.strip(): int(count) for name, count in cards}
    expected_counts = Counter(item.get("category") or "未分类" for item in history)
    for tname in sorted(set(expected_counts) | set(actual_counts)):
        exp, act = expected_counts.get(tname, 0), actual_counts.get(tname, 0)
        if exp != act:
            problems.append((tname, f"归类数量不一致：首页 {act} 题，history {exp} 题"))

    return problems


def check_type_colors() -> list:
    if not STYLE_FILE.exists():
        return [("style.css", "样式文件不存在")]
    css = STYLE_FILE.read_text(encoding="utf-8")
    return [
        (tname, f"样式缺失 .tag-{cls}")
        for tname, cls in CATEGORY_CLASS_MAP.items()
        if f".tag-{cls}" not in css
    ]


def main(argv: list) -> int:
    wanted = set(argv)
    failures = []
    pages = []

    if not ARCHIVE.exists():
        print(f"未找到归档目录：{ARCHIVE}")
    else:
        pages = sorted(
            p for p in ARCHIVE.glob("*.html")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)
            and (not wanted or p.stem in wanted)
        )
        for p in pages:
            missing = check_page(p.read_text(encoding="utf-8"))
            if missing:
                failures.append((p.name, "缺 " + ", ".join(missing)))

    if not wanted:
        history = None
        if HISTORY_FILE.exists():
            try:
                history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                failures.append(("history.json", f"JSON 解析失败：{e}"))
        else:
            failures.append(("history.json", "文件不存在，无法校验首页一致性"))

        if history is not None:
            failures.extend(check_index_consistency(history))
        failures.extend(check_type_colors())

    if failures:
        print(f"✗ 校验失败：{len(failures)} 个问题")
        for name, msg in failures:
            print(f"  - {name}：{msg}")
        return 1

    msg = f"✓ 校验通过：{len(pages)} 个归档页均为完整面试精讲。"
    if not wanted:
        msg += " 首页一致性 + 分类配色校验通过。"
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
