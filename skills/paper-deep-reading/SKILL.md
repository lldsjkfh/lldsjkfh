---
name: paper-deep-reading
description: >-
  论文精读工作流：给一个论文标题 / arXiv ID / DOI，自动定位可读 PDF（arXiv / dblp / Crossref 多源兜底）、
  按七步法精读（筛读 → 背景 → 洞察方法 → 证据审查 → 批判定位 → 笔记），
  在 Zotero 里建立专属文件夹归档 PDF 与阅读笔记，并为笔记生成方法流程图与"主张-证据"定量图。
  触发词：精读论文、读这篇论文、文献阅读、论文笔记、帮我读一下这篇、paper reading、
  这篇论文讲了什么（需要深读时）、给我整理这篇论文的笔记。
  不适用：多篇文献综述对比、全文翻译、只需要摘要的一句话概括。
---

# 论文精读（Paper Deep Reading）

一条命令定位 PDF，一套协议读出**能复用**的笔记，一份归档进 Zotero 随时可查。

## 何时用

- 你给了一个论文名字，要"读懂并留下笔记"
- 你要判断某篇论文值不值得跟、能不能迁移到自己的任务
- 你要在组会/综述里讲清一篇论文的贡献与边界

不适用：一次比较 5 篇论文（那是综述任务）、只要摘要、要全文翻译。

---

## 工作流总览

| 阶段 | 做什么 | 工具 | 产出 |
| --- | --- | --- | --- |
| 0 | 定位论文、下载 PDF、生成阅读索引 | `find_paper.py` + `pdf_outline.py` | `paper.pdf` `meta.json` `paper.md` `outline.json` `pages/` |
| 1 | 筛读：值不值得精读 | 读摘要/图注/结论 | 一句话主张 + 读/不读 |
| 2 | 背景与问题 | 读引言、相关工作 | 背景 2–3 句、问题定义 |
| 3 | 核心洞察与方法 | 精读方法 + 推导公式 | 流程图 `fig/method.svg` + 公式 |
| 4 | 实验与证据 | 读主表（看渲染图）+ 消融 | 证据表（主张→实验→可信度） |
| 5 | 批判与定位 | 读局限 + 查后续引用 | 局限清单 + 三个拒稿理由 |
| 6 | 写笔记 | 模板 + 配图 | `note.md` + `fig/*` |
| 7 | 归档进 Zotero | `zotero_archive.py` | collection + 条目 + PDF + 笔记 |

各步的**提问清单与门禁**见 `references/reading-protocol.md`；笔记模板见 `references/note-template.md`。

---

## 阶段 0：定位与准备

### 0.1 找到 PDF

```bash
python "C:/Users/86139/.workbuddy/skills/paper-deep-reading/scripts/find_paper.py" "<论文标题或 arXiv ID 或 DOI>"
```

输出 JSON 里看三个字段：

- `confidence`：`high` 直接用；`medium`/`low` 时把 `candidates` 的前几条标题念给用户确认，不要硬着头皮往下读
- `pdf.path`：PDF 落盘位置（默认 `D:/WorkBuddyFiles/papers/<年份-短标题>/paper.pdf`）
- `needs_confirmation`：为 `true` 说明没拿到可验证的 PDF，按 `pdf_error` 里的提示换源

> 脚本判定 PDF 的标准是**读到的前 5 字节是 `%PDF-`**，所以不会把落地页、HTML 预览页当成 PDF。

### 0.2 建阅读索引

```bash
python "C:/Users/86139/.workbuddy/skills/paper-deep-reading/scripts/pdf_outline.py" "<paper_dir>/paper.pdf" --render key
```

产出 `outline.json`，里面四样东西是后面精读的指挥棒：

| 字段 | 用途 |
| --- | --- |
| `sections` | 各章节所在行号 → 知道该读哪几行 |
| `read_plan` | 一次读完还是分段读（正文 > 6 万字符时自动给分段方案） |
| `captions` | 图注/表注清单 → 第 4 步定位证据 |
| `figure_table_pages` + `page_images` | 该看图的页 → **表格和公式在 md 里常丢失，必须看图** |
| `code_links` | 论文里提到的 GitHub/HuggingFace 链接 → 填元信息 |

### 0.3 读的策略（很重要）

1. **先读 `outline.json`，再读正文**。不要一上来 `Read` 整个 `paper.md`。
2. 双栏 PDF 转出的 md 会错序、断标题、把表格认成三列——**叙述读 md，数字和公式看图**。
3. 用 `Read` 的 `offset/limit` 按章节读；读到公式或主表时，`ViewImage` 打开对应 `pages/page-00XX.png` 校对。
4. 一篇 10–15 页论文，允许分 3–4 次读，每次读完先落 3 条要点再继续。

### 0.4 记下阅读动机

四选一（可多选）：方法借鉴 / 基线对比 / 写作引用 / 选题判断。
**动机决定详略**——"写作引用"型的论文，第 3 步公式推导可以跳过；"方法借鉴"型则必须把必要 vs 工程选择拆开。

---

## 阶段 1–5：按协议读

严格照 `references/reading-protocol.md` 走。三条硬规则：

1. **第 1 步说不清一句话主张就停**，标"存档待查"，只留元信息。
2. **每个数字都要能指到 Table/Fig/页码**。从渲染页读到的数字，记下页码进附录。
3. **区分"作者说的"与"我判断的"**，后者前面加「我判断：」。

第 4 步的证据表带**可信度评级**：

| 级别 | 含义 |
| --- | --- |
| A | 直接对照、多数据集/多种子、提升显著 |
| B | 有对照但单数据集或单次运行 |
| C | 间接支持、缺关键基线或只报最优设置 |

---

## 阶段 6：写笔记与配图

### 6.1 笔记

复制 `references/note-template.md` 的骨架到 `<paper_dir>/note.md`，逐格填。
十一个主字段必须齐：论文 / 一句话主张 / 背景与不足 / 问题定义 / 核心洞察 / 方法关键点 / 实验证据 / 局限与假设 / 领域定位 / 与我的关系 / 可跟进。

写不出就标 `TODO`、`未验证`——**留白优于编造**。

### 6.2 配图（最多三张）

| 图 | 用什么 | 命令要点 |
| --- | --- | --- |
| 方法流程图 | `textbook-svg` Track A | `scaffold --archetype branch/pillars/matrix/contrast` → 改文字 → `lint` 门禁 |
| 主张-证据图 | `figures4papers` 规范 + `scripts/paper_style.py` | `from paper_style import setup, style_axes, save, annotate_values` |
| 失败边界示意 | `textbook-svg` contrast | 同上 |

细节与可复制代码见 `references/figure-routing.md`。两条红线：

- **数据必须来自论文原表**，图注写明出处；缺数据留白标注，不要用 0 冒充。
- SVG 必须过 `lint`（0 error）才能交付。

---

## 阶段 7：归档进 Zotero

```bash
python "C:/Users/86139/.workbuddy/skills/paper-deep-reading/scripts/zotero_archive.py" \
  --paper-dir "<paper_dir>" --auto-close
```

结果：

```
文献精读/<年份 标题>/
  ├── 论文条目（含 PDF 副本）
  ├── 精读笔记（Zotero 原生笔记，可搜索/同步）
  ├── note.md（本地原文，含插图）
  └── 图：method.svg / evidence.svg
```

- `--auto-close`：脚本优雅关闭 Zotero → 写库 → 自动重启。不加则要求你先手动关（会返回 `need_close`）。
- 写库前自动备份 `zotero.sqlite.bak-<时间戳>`；脚本只新增，不改不删已有内容。
- 先看计划不落盘：`--dry-run`。

**两个实测坑**：

1. **自动重启在受限环境下会失效**：脚本的 `os.startfile` 可能被沙箱拦住（返回成功但进程没起来）。归档后确认 Zotero 是否真的在运行；没在就用
   `cmd //c start "" "C:\Program Files\Zotero\zotero.exe"`，或让用户手动打开。
2. **arXiv 预印本的 venue 常缺失**：arXiv 的 `journal_ref` 对很多会议论文是空的，条目会落成 `preprint`。
   读到 PDF 首页/致谢里的会议信息后，用 `--venue "ICML 2015"` 纠正（会自动切成 `conferencePaper`）。

**验证归档结果**（不用肉眼找）：拿 collection 的 key 直接跳转

```bash
python -c "import sqlite3;print(sqlite3.connect(r'C:/Users/86139/Zotero/zotero.sqlite').execute('SELECT key FROM collections WHERE collectionID=3').fetchone())"
cmd //c start "" "zotero://select/library/collections/<key>"
```

原理与故障排查见 `references/zotero-archive.md`。

---

## 交付检查清单

- [ ] `meta.json` 里 `confidence=high`（否则已与用户确认过）
- [ ] 笔记十一字段齐全，无空壳段落
- [ ] 每个数字有出处；不确定的标了「未验证」
- [ ] 至少有一张方法流程图，`lint` 通过
- [ ] 图的数据与论文原表一致
- [ ] Zotero 里能打开 PDF、能看到笔记
- [ ] 把 `note.md` 路径和 Zotero collection 名报给用户

---

## 目录结构

```
skills/paper-deep-reading/
├── SKILL.md
├── references/
│   ├── reading-protocol.md    # 七步协议、提问清单、门禁、时间预算
│   ├── note-template.md       # 笔记骨架 + 写作要求
│   ├── figure-routing.md      # 画图分工与可复制模板
│   └── zotero-archive.md      # Zotero 结构、原理、故障排查
└── scripts/
    ├── find_paper.py          # 论文定位 + PDF 下载校验
    ├── pdf_outline.py         # PDF→md + 章节/图表/页码索引 + 关键页渲染
    ├── zotero_archive.py      # 建 collection + 条目 + 附件 + 笔记
    └── paper_style.py         # 配图统一样式（figures4papers 同源）
```

## 常见故障

| 现象 | 处理 |
| --- | --- |
| `confidence` 为 low / PDF 拿不到 | 换用 DOI 或 arXiv ID 重试；仍不行就请用户提供 PDF 或访问权限 |
| 找不到 `workbuddy-pdf` | 检查 `~/.workbuddy/external-packages/pdf-cli/` 是否存在 |
| 双栏论文 md 错乱 | 正常现象，靠 `pages/*.png` 看图，不要试图"修"文本 |
| Zotero 未关闭导致写库失败 | 加 `--auto-close`，或手动关闭后重试 |
| `paper.md` 字符数 > 8 万 | 按 `read_plan.chunks` 分段读，别硬塞 |
| 归档成功但 Zotero 没起来 | `os.startfile` 被环境拦截，用 `cmd //c start "" "<zotero.exe>"` |
| 需要引用数 / 开放 PDF | 加 `--with-s2`（Semantic Scholar 匿名额度低，常 429） |
| 想要更准的会议名 | 加 `--with-dblp`（dblp 有反爬挑战，常失败，默认关闭） |
