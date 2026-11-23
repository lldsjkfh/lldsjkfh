# Skills

WorkBuddy / Agent 技能包归档。每个子目录都是一个独立的 skill，目录内 `SKILL.md` 是入口文件。

## 清单

| Skill | 分类 | 来源 | 用途 | 许可 |
|---|---|---|---|---|
| [`ppt-master/`](./ppt-master/) | 文档产出 | [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) v6.10.0 | 从 PDF / DOCX / URL / Markdown 生成**原生可编辑** PPTX（真实 DrawingML 形状、文本框、图表、动画），也支持套用模板与给成品加旁白/视频 | MIT |
| [`lieflat-less-ai-tone/`](./lieflat-less-ai-tone/) | 文字处理 | [larashero3-dotcom/lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone) | 中文成稿的「去 AI 味」：脚本分级检测 → 语义层判读 → 交付改前报告 → 按建议改写并复测出前后对比 | CC BY-NC 4.0（禁止商用） |
| [`video-knowledge-notes/`](./video-knowledge-notes/) | 文献阅读 | [GandalfLotion/video-knowledge-notes](https://github.com/GandalfLotion/video-knowledge-notes) | 视频 / 字音轨 → 简体中文 Obsidian 知识笔记，优先抓平台现成字幕（B 站已适配） | 未声明 |
| [`lab-weekly-report/`](./lab-weekly-report/) | 流程自动化 | 本机（agent 创建） | AIIA_Lab 实验室周报提交流程：读 PPT → 生成 `W周次-周日` 格式 md → 笔记先推个人仓库 → 链接填进周报 → **停下等审阅**，同意后才 commit / push / PR | 未声明 |
| [`paper-deep-reading/`](./paper-deep-reading/) | 文献阅读 | 本机（来源未标注） | 论文精读七步法：给标题 / arXiv ID / DOI 自动定位可读 PDF（arXiv / dblp / Crossref 多源兜底），Zotero 归档，产出笔记 + 方法流程图 + 主张-证据定量图 | 未声明 |
| [`textbook-svg/`](./textbook-svg/) | 画图 | 本机（来源未标注） | 教材 / 讲义 / 研究报告 / 论文的矢量配图，三轨制：Track A 极简纯 SVG 概念图、Track B 高信息密度写作配图、Track C 顶刊机制与架构图（Matplotlib 纯矢量 PDF） | 未声明 |
| [`figures4papers/`](./figures4papers/) | 画图 | 本机（来源未标注） | 顶会顶刊定量实验数据插图（Python / Matplotlib）：分组柱状图、消融实验图、超宽多指标面板，内置印刷字号预算与同源色板 | CC BY-NC 4.0（禁止商用） |

## 安装方式

把需要的子目录整个复制到 WorkBuddy 的用户级技能目录即可：

```bash
cp -r skills/ppt-master        ~/.workbuddy/skills/
cp -r skills/lab-weekly-report ~/.workbuddy/skills/
# 其余同理
```

Windows 下对应 `C:\Users\<用户名>\.workbuddy\skills\`。放置后**新开一个对话**，技能列表才会重新加载。

## 依赖说明

**ppt-master** — Python 3.10–3.14，在 skill 目录内装依赖：

```bash
cd ~/.workbuddy/skills/ppt-master && python -m pip install -r requirements.txt
```

可选：在该目录（或 `~/.ppt-master/`）放一个 `.env` 配置生图后端（`IMAGE_BACKEND` + 对应 KEY），才会自动配图；不配也能跑完整流程。

**lieflat-less-ai-tone** — 纯标准库，无依赖。

**video-knowledge-notes** — 需要 `pip install playwright`；抓 B 站字幕时用 `--channel msedge` 或 `chrome` 复用本机浏览器，不必额外下载 Chromium。首次抓取若返回 `login_required`，用 `login bilibili` 开一次专用窗口登录（登录态存在 `~/.video-knowledge-notes/`，之后复用）。

**paper-deep-reading** — 依赖本机 Zotero（用于建分类文件夹、归档 PDF 与阅读笔记）；PDF 定位走 arXiv / dblp / Crossref 公开接口，不需要额外 Key。

**textbook-svg / figures4papers** — Track A/B 是纯 SVG + HTML/CSS，不需要 Python 环境；Track C 与 figures4papers 需要 Python + `matplotlib`，做印前检查时还需要 `pdffonts` / `pdftoppm`（来自 poppler）。

**lab-weekly-report** — 只需本机 git 且能访问 GitHub。该技能带硬规矩：**未经明确同意，不得向 AIIA_Lab 写入任何内容**，它会在生成周报后停下等审阅。

## 说明

本目录是个人备份归档，内容版权归各原作者，按各自许可使用。各 skill 均为原始目录的直接副本，未做修改。

`figures4papers` 的 `assets/` 与 `figure_*/` 是自带的效果样例图（约 33MB），保留以便对照参考。
