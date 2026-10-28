# daily_meet_question — 每日面试问答

## 概述

对标 [daily-algo](https://github.com/czh55/daily-algo) 的全自动站点：每天生成 **一道面试问答题 + 完整口述答案**，托管到 GitHub Pages。

| | daily-algo | daily_meet_question |
|---|---|---|
| 目标 | 编码能力 | 知识点深度与广度 |
| 内容 | 算法题 + 变量语义法精讲 | 面试问答 + 结构化口述答案 |
| 方向 | LeetCode | 数据工程 / 数据分析 / 通用基础 |

## 每道题的讲解结构

1. **考察意图** — 面试官为什么问
2. **回答框架** — 口述提纲（先说什么、再说什么）
3. **参考答案** — 可直接练习的口述版
4. **关键词** — 答到这些词才算踩点
5. **追问** — 2～3 个深挖问题 + 答法
6. **常见踩坑** — 容易露怯的点
7. **记忆锚点** — 一句话带走

## 项目结构

```
daily_meet_question/
├── docs/                   # GitHub Pages 根目录
│   ├── index.html          # 主页（今日推荐 + 归档 + 分类）
│   ├── archive/            # 往期页面 YYYY-MM-DD.html
│   ├── style.css
│   └── .nojekyll
├── scripts/
│   ├── generate.py         # 选题 + 渲染 HTML
│   └── check_pages.py      # 精讲完整性 / 首页一致性 / 配色校验
├── data/
│   ├── question_bank.json  # 题库（含完整精讲与待补题目）
│   └── history.json        # 推荐历史
├── templates/
│   └── question.html
└── .cursor/automations/
    └── daily-prompt.md     # Cursor Automation 执行说明
```

## 本地使用

```bash
# 生成今日题目（从题库选下一道 ready 题）
python3 scripts/generate.py --bank

# 预览
python3 scripts/generate.py --bank --dry-run

# 列出题库
python3 scripts/generate.py --list

# 指定题目并覆盖当天
python3 scripts/generate.py --slug=sql-window-vs-groupby --force

# 提交前校验（必须通过）
python3 scripts/check_pages.py
```

## Cursor Automation（推荐）

每天定时触发 Agent，执行 `.cursor/automations/daily-prompt.md`：

1. `python3 scripts/generate.py --bank`
2. 若题库缺精讲 → 在 `question_bank.json` 补齐后 `--slug=... --force` 重跑
3. `python3 scripts/check_pages.py` 通过后 commit + push

GitHub Pages 指向 `main` 分支的 `/docs` 即可。

## 题库说明

- 已内置完整精讲（SQL / 数仓 / 指标 / 质量 / Spark / A/B / 行为等）+ 待补题目
- 另有待补题目：被选中且 `ready=false` 时脚本会跳过出页，由 Agent 按同一结构补齐
- 选题策略：按 `id` 顺序取未推荐过的 `ready` 题；全部讲完后按「最久未推荐」轮换

## 专题：项目深挖（行为面试）

个人经历与项目深挖是面试场景 ROI 最高的准备方向。题库用 `topics` 含 **「项目深挖」** 的一组题形成专题（`category=行为面试`，id 57–64）：

| slug | 对应准备点 |
|------|------------|
| `behavioral-project-deepdive-roi` | 为何深挖 ROI 最高 + 深挖卡准备法 |
| `behavioral-project-pain-contribution` | 数据基础 / 痛点 / 个人贡献 |
| `behavioral-project-goal-drive-iterate` | 目标来源 / 驱动 / 迭代 |
| `behavioral-transfer-people-matter-thing` | 能力迁移：人 / 事 / 物 |
| `behavioral-fast-fix-to-land` | 快速解决问题并落地 |
| `behavioral-domain-fundamentals` | 行业 + 技术基本面 |
| `behavioral-discover-to-ship` | 发现问题 → 推动落地 |
| `behavioral-team-raci-roadmap-sop` | 全责边界 / 资源 / 上线标准 / roadmap / SOP |

一句话锚点：**用可验证事实证明你在真实约束下能判断与推动，并把能力拆成可迁移的人/事/物。**

指定练习示例：

```bash
python3 scripts/generate.py --slug=behavioral-project-deepdive-roi --force
```
