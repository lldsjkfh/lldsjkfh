---
name: lab-weekly-report
description: AIIA_Lab 实验室周报的完整提交流程：读 PPT、生成 W周次-周日 格式的 md、把相关笔记先传到个人 GitHub 仓库、将 GitHub 链接填进周报，然后停下等用户审阅，用户明确同意后才 commit / push 分支 / 建 PR。硬规矩：未经同意不得向 AIIA_Lab 写入任何内容。包含周次口径、五段模板写法、链接逐个验活，以及本机 git 与代理必踩的坑：HTTP/1.1、代理端口漂移、私有仓库 404、仓库改名 301。触发词：提交周报、写周报、实验室周报、周报 PR、AIIA_Lab 周报、这周的周报。
agent_created: true
---

# AIIA_Lab 实验室周报：端到端流程

**核心原则：周报里每个条目都要能被点开验证。** 先有可访问的产出，再写文字；链接必须实测 200，不能凭文件名猜。

> ## ⛔ 红线：周报仓库的提交必须等用户明确同意
>
> **「把周报提交到 AIIA_Lab」这件事（commit / push 分支 / 建 PR）只能发生在用户说出「可以提交 / 可以提 PR」之后。**
>
> - 写完 md 就**停**，把文件路径和内容摘要交给用户审阅，**不要** `git add`、**不要** commit、**不要** push、**不要** 建分支。
> - 需要给用户看内容时，用 `present_files` 展示本地文件、或在 VS Code 打开，**不要用「先推上去再说」的方式让他看**。
> - 用户说「审阅完毕 / 可以提 PR」之后，才一次性完成：commit → push 分支 → 建 PR。
> - 中间任何环节想「顺手先推一下」都属于违规，即使只是推分支不建 PR。
>
> 例外（不受此闸门约束）：`lldsjkfh` 个人笔记仓库的内容上传——那是「准备素材」，必须先做，因为周报要引用它的链接。

## 一、口径（写错就白干）

| 项 | 规则 |
| --- | --- |
| 周次 | 2026 年按 ISO 周；**W42=10-18、W43=10-25、W44=11-01、W45=11-08、W46=11-15、W47=11-22**（周日结束） |
| 目录 | `D:\课题组周报\AIIA_Lab\docs\26级周报\2026\卢磊\` |
| 文件名 | `W[周次]-[日期].md`，日期取**该周周日**，如 `W46-1115.md` |
| 分支 | `weekly/lulei-w[周次]`（小写 w） |
| 提交信息 | `docs(weekly): add lulei w[周次] report` |
| 个人仓库 | `lldsjkfh/lldsjkfh`（public，放笔记/代码/复现包） |
| 周报仓库 | `aiia-one/AIIA_Lab`（**private**；旧名 havvk/AIIA_Lab 会 301） |

PPT 封面日期可能是周三/周五（如 W44 标 10-30、W46 标 11-14），**以周次为准**，文件名用周日。

## 二、五段结构（模板）

```markdown
# 实验室周报 (2026-Wxx)

- **汇报人**：卢磊
- **日期**：2026-MM-DD
- **负责项目/课题**：无

## 1. 本周工作进展（已完成/可验证）
## 2. 学术研究与文献精读（本周输入）
## 3. 遇到的技术阻碍与解决方案（知识沉淀）
## 4. 下周规划（可量化的工作目标）
## 5. 待讨论问题 / 需导师协助
```

写法要点（前两周验证过有效）：

- **第 1 节**：按 PPT 的主线分组，每条给「机制 + 具体数字 + 链接」。数字必须来自 PPT 或原始笔记，不编。
  每条结尾一行链接：`[说明（GitHub）](https://github.com/lldsjkfh/lldsjkfh/blob/main/...)`。
  续行用 6 空格缩进（GitHub 上仍是同一段落）。
- **第 2 节**：论文题目要写**准确的会议与年份**（PPT 常常只写会议名）。查 ACM DL / arXiv 核对，别默认最新年份。
  本周无新论文就如实写「本周无新增论文精读，输入为课程 X」，并说明下周恢复。
- **第 3 节**：每条 `问题描述 / 解决方法 / 沉淀` 三段，「沉淀」要写成别人能直接复用的一句话规律。
- **第 4 节**：从 PPT 最后一页的「下周计划」抄，给每条补**可验收标准**（N 个 worker、误差 <1e-3、能 `make && ./run`）。
- **第 5 节**：用户通常写「无」；如从实验里发现真问题可列 1–2 条，但**不要擅自补回被用户删掉的内容**。

## 三、先传内容，再写链接

1. 从 PPT 找出本周真正的产出（笔记 / 代码 / 复现包）。
2. 传到 `lldsjkfh`，遵守既有目录：`论文精读/`、`Linux/`、`深度学习/`、`刷题/`；新目录要在根 `README.md` 索引里加一行。
3. 更新根 `README.md` 与对应子目录 `README.md` 的索引。
4. 用 **API 的 contents 接口**确认每个路径 200，再拿 URL 填进周报。

> 这一步（传个人笔记仓库 + 填链接）是**允许在用户审阅之前做**的，因为周报正文依赖这些链接。
> 但周报本身写完就停，见开头的红线。

**传什么、不传什么**

- 单文件、图片已内嵌的 HTML → 可以传（`data:image` 数 > 0、外链 `<img>` 数 = 0 才算自包含）。
- 引用 `xxx.assets/` 的 md/html → **不要只传主文件**，会全断图（曾遇 226 张图 55MB）。改为写一份聚焦版笔记，并在文末注明「完整版在本地」。
- 累计型大笔记（几百 KB）优先做「本周聚焦版」，比整本上传更可读。

## 四、Git 操作（⚠️ 仅在用户同意后执行）

```bash
cd D:/课题组周报/AIIA_Lab
git config http.version HTTP/1.1      # ★ 必做，否则代理直接 502
git config http.sslVerify false
git checkout main && git pull origin main
git checkout -b weekly/lulei-w46
# 写文件…
git add "docs/26级周报/2026/卢磊/W46-1115.md"   # ★ 只 add 周报文件
git commit -m "docs(weekly): add lulei w46 report"
git push -u origin weekly/lulei-w46
```

**五个坑（都真实发生过）**

1. **git 走本机代理必须 `http.version=HTTP/1.1`**。默认 HTTP/2 会被代理拒成
   `CONNECT tunnel failed, response 502`，而同一端口 `curl -x` 却 200——别据此误判网络。
2. **代理端口每次会话都变**（见过 1033 / 11505 / 14190）。只能读 `$HTTPS_PROXY`，不要写死。
3. **`api.github.com` 与 `github.com` 的连通性会独立变化**。`github.com` 死、api 活时，
   用 Git Data API 建 blob→tree→commit→ref 仍能提交（脚本见下）。
4. **`AIIA_Lab` 是私有仓库**，未登录抓页面返回 404（不是链接错）；`havvk/` 旧名 API 返回 301。
5. **只 `git add` 周报文件**。工作区常有与本周无关的 ` D`（已删除）条目，`git add .` 会把它们一起提交。

**API 兜底脚本**（github.com 不通时）：`git credential fill` 取 token（不要打印），
然后 `POST /git/blobs`（`encoding: utf-8`）→ `POST /git/trees`（`base_tree` = 远端 main 的 tree）→
`POST /git/commits`（parent = 远端 main）→ `POST /git/refs`。**parent 必须用远端 main，不要用本地陈旧 main。**

## 五、链接验证（写完 md 后、交审阅前必做）

```js
// 解码每个 github blob URL → 调 contents API 查 200
const re = /\]\((https:\/\/github\.com\/lldsjkfh\/lldsjkfh\/blob\/main\/[^)]+)\)/g;
const rel = decodeURIComponent(u.split('/blob/main/')[1]);
api('/repos/lldsjkfh/lldsjkfh/contents/' + rel.split('/').map(encodeURIComponent).join('/') + '?ref=main');
```

- 中文路径必须 `encodeURIComponent` **逐段**编码。手写编码极易漏掉开头的 `%`（曾把 `%E8%AE%BA` 写成 `E8%AE%BA`，四条链接全 404）。
- 用生成器脚本产出 URL，不要手打。
- 校验脚本里的代理要读 `process.env.HTTPS_PROXY`。

## 六、PR（与推送同一批执行，仍需用户同意）

用户说「审阅通过 / 可以提 PR / 可以提交」之后再建。**推送分支与建 PR 属于同一批动作**，不要出现「已推送但未获同意」的中间态：

```js
POST /repos/aiia-one/AIIA_Lab/pulls
{ title: "周报: 卢磊 - 2026-WXX", head: "weekly/lulei-wXX", base: "main", body: "..." }
```

- 标题格式固定：`周报: 卢磊 - 2026-W[周次]`。
- Body：本周内容分组 + 交付物链接表 + 关键实测结论 + 下周计划。
- PR 建完查一次 `mergeable_state`（刚建时是 `unknown`，几秒后才 `clean`）。
- **Assignee / Reviewers 让用户自己在页面上设**，API 不代设。

## 七、协作注意事项

- **用户会同时在 VS Code 里改这份 md 并保存**。我改完链接后，他的保存会覆盖回去。
  → 交付时明确说「先保存，我再统一校验」；他保存后再跑一次链接校验。
- 用户会自行裁剪（删「待讨论」、把「负责项目/课题」改成「无」、缩写下周计划）——**尊重裁剪，不补回**。
- 明显的错别字（如「算法题联系」→「练习」）可以顺手改，但要在回复里说明改了哪一处。

## 八、收尾清单

**提交前（写完 md 即可自查）**

- [ ] 文件名日期 = 该周周日；分支名小写 w
- [ ] 第 1–5 节齐全，每条有可点开的链接
- [ ] 所有链接 API 查过 200；无残留 `file:///` 本地路径
- [ ] 已把文件路径 + 内容摘要交给用户审阅 —— **此时必须停下，等同意**

**用户同意后**

- [ ] 重新比对「本地文件 vs 远端 blob」，用户可能在此期间改过（contents API 取 base64 或 `git diff --no-index`）
- [ ] 只提交周报一个文件（别夹带工作区里无关的 ` D` 条目）
- [ ] 推完 `ls-remote` / API 确认分支存在
- [ ] PR 标题 `周报: 卢磊 - 2026-WXX`，建完查 `mergeable_state`
- [ ] 回报 PR 号 + mergeable 状态，提醒用户设 Assignee / Reviewers
