# Skills

WorkBuddy / Agent 技能包归档。每个子目录都是一个独立的 skill，目录内 `SKILL.md` 是入口文件。

| Skill | 版本/来源 | 用途 | 许可 |
|---|---|---|---|
| [`ppt-master/`](./ppt-master/) | v6.10.0 · [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | 从 PDF / DOCX / URL / Markdown 生成**原生可编辑** PPTX（真实 DrawingML 形状、文本框、图表、动画），也支持套用模板与给成品加旁白/视频 | MIT |
| [`lieflat-less-ai-tone/`](./lieflat-less-ai-tone/) | [larashero3-dotcom/lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone) | 中文成稿的「去 AI 味」：脚本分级检测 → 语义层判读 → 交付改前报告 → 按建议改写并复测出前后对比 | CC BY-NC 4.0（禁止商用） |
| [`video-knowledge-notes/`](./video-knowledge-notes/) | [GandalfLotion/video-knowledge-notes](https://github.com/GandalfLotion/video-knowledge-notes) | 视频 / 字音轨 → 简体中文 Obsidian 知识笔记，优先抓平台现成字幕（B 站已适配） | 未声明 |

## 安装方式

把需要的子目录整个复制到 WorkBuddy 的用户级技能目录即可：

```bash
cp -r skills/ppt-master ~/.workbuddy/skills/
cp -r skills/lieflat-less-ai-tone ~/.workbuddy/skills/
cp -r skills/video-knowledge-notes ~/.workbuddy/skills/
```

Windows 下对应 `C:\Users\<用户名>\.workbuddy\skills\`。放置后**新开一个对话**，技能列表才会重新加载。

## 依赖说明

**ppt-master** 需要 Python 3.10–3.14，并在 skill 目录内装依赖：

```bash
cd ~/.workbuddy/skills/ppt-master
python -m pip install -r requirements.txt
```

可选：在该目录（或 `~/.ppt-master/`）放一个 `.env` 配置生图后端（`IMAGE_BACKEND` + 对应 KEY），才会自动配图；不配也能跑完整流程。

**lieflat-less-ai-tone** 纯标准库，无依赖。

**video-knowledge-notes** 需要 `pip install playwright`；抓 B 站字幕时用 `--channel msedge` 或 `chrome` 复用本机浏览器，不必额外下载 Chromium。首次抓取若返回 `login_required`，需用 `login bilibili` 开一次专用窗口登录（登录态存在 `~/.video-knowledge-notes/`，之后可复用）。

## 说明

本目录是个人备份归档，内容版权归各原作者，按各自许可使用。`ppt-master` 与 `lieflat-less-ai-tone` 为原仓库的直接副本；`video-knowledge-notes` 同样未做修改。
