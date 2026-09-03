#!/usr/bin/env python3
"""
每日面试问答网站生成脚本
================================
用法：
  python3 scripts/generate.py --bank          # 从题库选下一题并出页
  python3 scripts/generate.py --bank --dry-run
  python3 scripts/generate.py --list
  python3 scripts/generate.py --slug=sql-window-vs-groupby --force
"""

from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOCS = ROOT / "docs"
ARCHIVE = DOCS / "archive"
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"
BANK_FILE = DATA / "question_bank.json"
HISTORY_FILE = DATA / "history.json"

# 分类 → CSS class
CATEGORY_CLASS_MAP = {
    "SQL": "sql",
    "数仓建模": "dw",
    "指标体系": "metric",
    "数据质量": "dq",
    "大数据计算": "bigdata",
    "数据工程": "de",
    "A/B实验": "ab",
    "业务分析": "biz",
    "Python": "python",
    "计算机基础": "cs",
    "机器学习基础": "ml",
    "行为面试": "behavior",
}


def _html_escape(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _mdish_to_html(text: str) -> str:
    """把题库里的轻量文本转成简单 HTML（段落 + 代码块 + 换行）。"""
    if not text:
        return ""
    text = text.strip()
    # fenced code blocks
    parts: list[str] = []
    cursor = 0
    for m in re.finditer(r"```(?:\w+)?\n(.*?)```", text, flags=re.S):
        before = text[cursor:m.start()].strip()
        if before:
            parts.append(_paragraphs(before))
        code = _html_escape(m.group(1).rstrip("\n"))
        parts.append(f'<pre><code>{code}</code></pre>')
        cursor = m.end()
    rest = text[cursor:].strip()
    if rest:
        parts.append(_paragraphs(rest))
    return "\n".join(parts)


def _paragraphs(text: str) -> str:
    chunks = re.split(r"\n\s*\n", text.strip())
    out = []
    for chunk in chunks:
        lines = [_inline_format(line.strip()) for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue
        # numbered / bullet lines → list-ish paragraphs
        if all(re.match(r"^(\d+\.|[-*])\s+", ln) or ln.startswith("  ") for ln in chunk.split("\n") if ln.strip()):
            items = []
            for ln in chunk.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                ln = re.sub(r"^(\d+\.|[-*])\s+", "", ln)
                items.append(f"<li>{_inline_format(ln)}</li>")
            out.append("<ul>" + "".join(items) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(lines) + "</p>")
    return "\n".join(out)


def _inline_format(text: str) -> str:
    text = _html_escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def load_bank() -> list:
    if not BANK_FILE.exists():
        return []
    with open(BANK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_question(slug: str) -> Optional[dict]:
    for q in load_bank():
        if q.get("slug") == slug:
            return q
    return None


def rebuild_history_from_archives() -> list:
    history = []
    if not ARCHIVE.exists():
        return history
    bank_by_id = {str(q.get("id")): q for q in load_bank()}
    for path in sorted(ARCHIVE.glob("*.html")):
        date_str = path.stem
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            continue
        content = path.read_text(encoding="utf-8")
        mid = re.search(r'problem-id">#(\d+)<', content)
        if not mid:
            continue
        q = bank_by_id.get(mid.group(1))
        title_m = re.search(r'class="problem-title">([^<]+)<', content)
        cat_m = re.search(r'problem-type tag-[\w-]+">([^<]+)<', content)
        history.append({
            "date": date_str,
            "slug": q.get("slug") if q else "",
            "title": (q.get("title") if q else None) or (title_m.group(1).strip() if title_m else ""),
            "category": (q.get("category") if q else None) or (cat_m.group(1).strip() if cat_m else ""),
        })
    return history


def load_history() -> list:
    file_history = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            file_history = json.load(f)
    merged: dict[str, dict] = {}
    for item in file_history:
        merged[item.get("date", "")] = item
    for item in rebuild_history_from_archives():
        merged[item["date"]] = item
    return sorted(merged.values(), key=lambda x: x.get("date", ""))


def save_history(history: list):
    DATA.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _last_used_map(history: list) -> dict:
    last_used: dict[str, str] = {}
    for item in history:
        s = item.get("slug", "")
        d = item.get("date", "")
        if s and d > last_used.get(s, ""):
            last_used[s] = d
    return last_used


def select_question() -> tuple[Optional[str], Optional[str]]:
    """优先选尚未推荐且 ready=True 的题；否则轮换最久未推荐的 ready 题。"""
    history = load_history()
    used = {item.get("slug", "") for item in history}
    bank = load_bank()
    ready = [q for q in bank if q.get("ready")]
    ready.sort(key=lambda q: q.get("id", 0))

    for q in ready:
        if q["slug"] not in used:
            return q["slug"], "bank"

    if ready:
        last_used = _last_used_map(history)
        best = min(ready, key=lambda q: (last_used.get(q["slug"], ""), q.get("id", 0)))
        return best["slug"], "bank-cycle"

    # 无 ready 题：返回下一道未推荐题，供 Agent 补精讲
    for q in sorted(bank, key=lambda x: x.get("id", 0)):
        if q["slug"] not in used:
            return q["slug"], "need-answer"
    return None, None


def _render_framework(framework) -> str:
    if not framework:
        return ""
    if isinstance(framework, list):
        items = "".join(f"<li>{_inline_format(str(x))}</li>" for x in framework)
        return f'<ol class="answer-framework">{items}</ol>'
    return _mdish_to_html(str(framework))


def _render_followups(followups) -> str:
    if not followups:
        return ""
    blocks = []
    for i, fu in enumerate(followups, 1):
        q = _inline_format(fu.get("q", ""))
        a = _mdish_to_html(fu.get("a", ""))
        blocks.append(f"""<div class="followup-item">
            <h4>追问 {i}：{q}</h4>
            <div class="followup-answer">{a}</div>
        </div>""")
    return "\n".join(blocks)


def _render_list(items, css_class: str) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return _mdish_to_html(items)
    lis = "".join(f"<li>{_inline_format(str(x))}</li>" for x in items)
    return f'<ul class="{css_class}">{lis}</ul>'


def _render_keywords(keywords) -> str:
    if not keywords:
        return ""
    chips = "".join(f'<span class="keyword-chip">{_html_escape(str(k))}</span>' for k in keywords)
    return f'<div class="keyword-row">{chips}</div>'


def is_complete(q: dict) -> bool:
    """完整精讲必须具备的字段。"""
    if not q or not q.get("ready"):
        return False
    required = ["intent", "framework", "answer", "followups", "pitfalls", "anchor"]
    return all(q.get(f) for f in required)


def render_template(q: dict, date_str: str) -> str:
    template = (TEMPLATES / "question.html").read_text(encoding="utf-8")
    category = q.get("category", "")
    diff = q.get("difficulty", "中等")
    cat_class = CATEGORY_CLASS_MAP.get(category, "other")
    diff_class = {"简单": "easy", "中等": "medium", "困难": "hard"}.get(diff, "medium")
    topics = q.get("topics") or []
    topics_html = "".join(
        f'<span class="topic-chip">{_html_escape(str(t))}</span>' for t in topics
    )

    replacements = {
        "{{TITLE}}": _html_escape(q.get("title", "")),
        "{{QID}}": str(q.get("id", "")),
        "{{SLUG}}": q.get("slug", ""),
        "{{DATE}}": date_str,
        "{{CATEGORY}}": _html_escape(category),
        "{{CATEGORY_CLASS}}": cat_class,
        "{{DIFFICULTY}}": diff,
        "{{DIFFICULTY_CLASS}}": diff_class,
        "{{TOPICS}}": topics_html,
        "{{INTENT}}": _mdish_to_html(q.get("intent", "")),
        "{{FRAMEWORK}}": _render_framework(q.get("framework")),
        "{{ANSWER}}": _mdish_to_html(q.get("answer", "")),
        "{{FOLLOWUPS}}": _render_followups(q.get("followups")),
        "{{PITFALLS}}": _render_list(q.get("pitfalls"), "pitfall-list"),
        "{{KEYWORDS}}": _render_keywords(q.get("keywords")),
        "{{ANCHOR}}": _inline_format(q.get("anchor", "")),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def generate_index_html(today_q: dict = None, target_date: str = None):
    history = load_history()
    featured_date = target_date or date.today().isoformat()

    today_html = ""
    if today_q:
        cat = today_q.get("category", "")
        cat_class = CATEGORY_CLASS_MAP.get(cat, "other")
        diff = today_q.get("difficulty", "中等")
        diff_class = {"简单": "easy", "中等": "medium", "困难": "hard"}.get(diff, "medium")
        preview = _html_escape((today_q.get("intent") or today_q.get("answer") or "")[:160])
        today_html = f"""<div class="today-problem">
            <div class="today-label">&#x1F4C5; 今日推荐</div>
            <h2><a href="archive/{featured_date}.html">#{today_q.get('id', '')} { _html_escape(today_q.get('title', '')) }</a></h2>
            <div class="today-meta">
                <span class="problem-type tag-{cat_class}">{_html_escape(cat)}</span>
                <span class="problem-difficulty difficulty-{diff_class}">{diff}</span>
            </div>
            <p style="margin-top:12px; color:var(--text-secondary); font-size:0.9rem;">
                {preview}...
                <a href="archive/{featured_date}.html">[查看完整讲解]</a>
            </p>
        </div>"""

    archive_html = ""
    for item in reversed([h for h in history if h.get("date") != featured_date]):
        cat = item.get("category", "")
        cat_class = CATEGORY_CLASS_MAP.get(cat, "other")
        archive_html += f"""<div class="archive-item">
            <a href="archive/{item['date']}.html">
                <div class="archive-date">{item['date']}</div>
                <div class="archive-title">{_html_escape(item.get('title', ''))}</div>
                <span class="archive-type problem-type tag-{cat_class}">{_html_escape(cat)}</span>
            </a>
        </div>"""

    type_groups: dict = {}
    for item in history:
        tname = item.get("category") or "未分类"
        type_groups.setdefault(tname, []).append(item)

    types_html = ""
    for tname, items in sorted(type_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        tclass = CATEGORY_CLASS_MAP.get(tname, "other")
        item_html = ""
        for it in reversed(items):
            item_html += (
                f'<li><a href="archive/{it["date"]}.html">{_html_escape(it["title"])}</a>'
                f'<span class="type-item-date">{it["date"]}</span></li>'
            )
        types_html += f"""<div class="type-card">
            <div class="type-card-header">
                <span class="problem-type tag-{tclass}">{_html_escape(tname)}</span>
                <span class="type-count">{len(items)} 题</span>
            </div>
            <ul class="type-problem-list">
                {item_html}
            </ul>
        </div>"""

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日面试问答 · 知识点深挖</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <header class="site-header">
        <div class="container">
            <a href="index.html" class="logo">
                <span class="logo-icon">&#x25C7;</span>
            </a>
            <span class="header-date">{featured_date}</span>
        </div>
    </header>

    <main class="container">
        <section class="index-hero">
            <h1>每日一道面试题</h1>
            <p class="subtitle">用结构化口述，把「知道名词」练成「答得出深度」</p>
        </section>

        {today_html}

        <section class="archive-section">
            <h2>&#x1F4DA; 往期归档</h2>
            <div class="archive-grid">
                {archive_html if archive_html else '<p style="color:var(--text-tertiary);">暂无归档，第一道题即将推荐！</p>'}
            </div>
        </section>

        <section class="types-section">
            <h2>&#x1F4C2; 按知识点归类</h2>
            <div class="types-grid">
                {types_html if types_html else '<p style="color:var(--text-tertiary);">暂无题目。</p>'}
            </div>
        </section>
    </main>

    <footer class="site-footer">
        <div class="container">
            <p>每日面试问答 &mdash; 面向数据工程 / 数据分析面试的知识点精讲</p>
            <p class="footer-meta">对标 daily-algo · Cursor Automations 自动生成 · 每天更新</p>
        </div>
    </footer>
</body>
</html>"""

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(index_html, encoding="utf-8")


def add_to_history(q: dict, date_str: str, force: bool = False):
    """写入 history.json。

    注意：存在性检查只看「文件里的历史」，不看 archive 重建结果。
    否则 generate_today 若先写了归档页，load_history() 会误判「今日已有」而跳过落盘，
    导致 check_pages 读到空的 history.json。
    """
    file_history: list = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            file_history = json.load(f)

    if any(item.get("date") == date_str for item in file_history):
        if not force:
            print(f"今日 ({date_str}) 已有记录，跳过写入历史")
            return
        file_history = [item for item in file_history if item.get("date") != date_str]

    file_history.append({
        "date": date_str,
        "slug": q.get("slug", ""),
        "title": q.get("title", ""),
        "category": q.get("category", ""),
    })
    # 与 archive 合并后再存，避免丢失仅存在于归档的旧记录
    merged = {item.get("date", ""): item for item in load_history()}
    for item in file_history:
        merged[item.get("date", "")] = item
    save_history(sorted(merged.values(), key=lambda x: x.get("date", "")))


def _existing_history_item(date_str: str) -> Optional[dict]:
    """只看 history.json 文件本身，不合并 archive 重建结果。"""
    if not HISTORY_FILE.exists():
        return None
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        file_history = json.load(f)
    for item in file_history:
        if item.get("date") == date_str:
            return item
    return None


def generate_today(
    dry_run: bool = False,
    force_slug: str = None,
    target_date: str = None,
    force: bool = False,
) -> bool:
    today_date = target_date or date.today().isoformat()

    # 当天已有完整精讲则默认跳过（与 daily-prompt 异常表一致）；重做需 --force
    if not force:
        existing = _existing_history_item(today_date)
        archive_path = ARCHIVE / f"{today_date}.html"
        if existing and archive_path.exists():
            existing_q = get_question(existing.get("slug", ""))
            if existing_q and is_complete(existing_q):
                if force_slug and force_slug != existing.get("slug"):
                    print(
                        f"今日 ({today_date}) 已有记录（{existing.get('slug')}）。"
                        f"覆盖请加 --force"
                    )
                    return False
                print(f"今日 ({today_date}) 已有记录，跳过")
                print(f"题目：{existing_q['title']} (#{existing_q['id']})")
                if dry_run:
                    print("\n[Dry-run] 跳过文件写入")
                    return True
                generate_index_html(existing_q, target_date=today_date)
                print(f"✓ 沿用已有精讲 docs/archive/{today_date}.html")
                return True

    if force_slug:
        slug, source = force_slug, "manual"
    else:
        slug, source = select_question()

    if not slug:
        print("没有可用的题目！")
        return False

    q = get_question(slug)
    if not q:
        print(f"题库中找不到 slug={slug}")
        return False

    if not is_complete(q):
        print(f"⚠ 题目「{q.get('title')}」(#{q.get('id')}, {slug}) 尚无完整精讲，已跳过、未出页。")
        print("  请在 data/question_bank.json 中为该题补齐：")
        print("  intent / framework / answer / followups / pitfalls / keywords / anchor，并将 ready 设为 true。")
        print(f"  补好后运行：python3 scripts/generate.py --slug={slug} --date={today_date} --force")
        return False

    print(f"今日题目：{q['title']} (#{q['id']})")
    print(f"分类：{q['category']} | 难度：{q['difficulty']} | 来源：{source}")

    if dry_run:
        print("\n[Dry-run] 跳过文件写入")
        return True

    # 先写历史，再出归档页，避免 archive 重建干扰「今日是否已有」判断
    add_to_history(q, today_date, force=force)

    html = render_template(q, today_date)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / f"{today_date}.html").write_text(html, encoding="utf-8")
    generate_index_html(q, target_date=today_date)

    print(f"✓ 已生成 docs/archive/{today_date}.html")
    print(f"✓ 已更新 docs/index.html")
    return True


def main():
    parser = ArgumentParser(description="每日面试问答网站生成器")
    parser.add_argument("--bank", action="store_true", help="从本地题库选题（默认行为）")
    parser.add_argument("--dry-run", action="store_true", help="预览但不写入文件")
    parser.add_argument("--slug", type=str, help="指定题目 slug")
    parser.add_argument("--date", type=str, help="指定日期 YYYY-MM-DD")
    parser.add_argument("--force", action="store_true", help="覆盖已有日期的记录")
    parser.add_argument("--list", action="store_true", help="列出题库")
    args = parser.parse_args()

    if args.list:
        bank = load_bank()
        ready = [q for q in bank if q.get("ready")]
        pending = [q for q in bank if not q.get("ready")]
        print(f"=== 题库共 {len(bank)} 题（完整精讲 {len(ready)} / 待补 {len(pending)}）===")
        print("--- 已就绪 ---")
        for q in ready:
            print(f"  #{q['id']:>3} {q['title'][:40]:<40s} [{q['category']}] {q['difficulty']}")
        if pending:
            print("--- 待补精讲（选中时由 Agent 补齐）---")
            for q in pending:
                print(f"  #{q['id']:>3} {q['title'][:40]:<40s} [{q['category']}] {q['difficulty']}")
        # 分类分布
        print("--- 分类分布 ---")
        for name, cnt in Counter(q.get("category") for q in bank).most_common():
            print(f"  {name}: {cnt}")
        return

    generate_today(
        dry_run=args.dry_run,
        force_slug=args.slug,
        target_date=args.date,
        force=args.force,
    )


if __name__ == "__main__":
    main()
