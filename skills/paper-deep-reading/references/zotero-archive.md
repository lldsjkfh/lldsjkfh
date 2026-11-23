# Zotero 归档：结构、原理与故障排查

## 一、归档后的目录形态

```
文献精读/                                    ← 根 collection（--root，可改）
└── 2015 Batch Normalization Accelerating…  ← 每篇论文一个子 collection
    ├── 📄 论文条目（preprint / conferencePaper / journalArticle）
    │   └── paper.pdf                        ← 库内副本（storage/<key>/paper.pdf）
    ├── 📝 精读笔记                          ← Zotero 原生笔记，可搜索、可同步、可导出
    ├── note.md（本地原文，含插图）           ← linked attachment，双击用外部编辑器打开
    └── 图：method.svg / evidence.svg        ← linked attachment
```

要点：

- **PDF 是库内副本**（`linkMode=0`），不是链接——移动原目录不会失效。
- **笔记同时存在两份**：Zotero note（HTML，便于搜索/同步/手机看）+ 本地 `note.md`（带图，便于二次编辑）。两者内容一致，以 md 为源。
- 子条目（附件、笔记）不需要单独加入 collection——Zotero 的触发器明确禁止子条目进 collection，父条目在即可。

## 二、为什么必须关 Zotero

Zotero 对 `zotero.sqlite` 持有**独占锁**，运行期间连只读打开都会报 `database is locked`。
所以归档脚本只有两条路：

| 模式 | 行为 | 适用 |
| --- | --- | --- |
| 默认 | 检测到 Zotero 运行 → 返回 `need_close` 让你手动关 | 你正在 Zotero 里干活 |
| `--auto-close` | 优雅关闭（等同点窗口 ×，**不强制 kill**）→ 写入 → 自动重启 | 常规使用 |
| `--data-dir <别的库>` | 指向副本库时跳过进程检查 | 测试 / 迁移 |

优雅关闭用的是 `taskkill /IM zotero.exe`（不带 `/F`），Zotero 会正常落盘。若 40 秒内没退出，脚本会**放弃并提示手动关闭**，不会强杀——强杀可能丢你正在编辑的笔记。

## 三、脚本实际写入的内容

| 层 | 写入 |
| --- | --- |
| `collections` | 根 + 子 collection，`key` 随机 8 位，`version=0 / synced=0`（本地新增） |
| `items` | 条目本体，`itemTypeID` 按 venue 猜：arXiv→preprint(31)、顶会→conferencePaper(11)、其余→journalArticle(22) |
| `itemData` | 只写该类型**允许**的字段（查 `itemTypeFields`），未知字段自动丢弃，避免 Zotero 报 schema 错 |
| `creators` / `itemCreators` | 作者按空格拆姓/名；中文名或单词名走单字段模式（`fieldMode=1`） |
| `itemAttachments` | PDF 复制到 `storage/<key>/`，`syncState=1`（待上传）+ `storageHash`=md5 |
| `itemNotes` | 笔记 HTML，统一包 `<div class="zotero-note znv1">` |
| `collectionItems` | 只挂父条目，`orderIndex=0` |

**幂等**：同一 collection 下已有同标题条目时复用，不会重复插入；重复执行只会补缺失的附件。

**备份**：写前自动 `zotero.sqlite → zotero.sqlite.bak-<时间戳>`（连带 `-wal/-shm`）。出问题就把备份改回原名。

## 四、故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `需要关闭 Zotero (need_close)` | 数据库被独占锁 | 关 Zotero，或加 `--auto-close` |
| `Zotero 未能自动退出` | 有未保存编辑 / 弹窗阻塞 | 手动关闭后重试（不要强杀） |
| 归档成功但 Zotero 里看不到 | Zotero 还没重启 | 打开 Zotero；collection 会出现在左侧对应位置 |
| 条目在，但 PDF 打不开 | storage 目录未被识别 | 检查 `storage/<key>/paper.pdf` 是否存在；Zotero 中右键「重新索引」 |
| 同步后条目重复 | 本地 key 与服务器冲突（极少） | 删掉重复条目，保留带附件那份 |
| `找不到 Zotero 数据目录` | 数据目录被改到非默认位置 | `--data-dir "D:/Zotero"` |
| 笔记里图片不显示 | Zotero 笔记不加载相对路径图片 | 图看 `note.md`（外部编辑器打开），Zotero note 里保留图注文字 |

## 五、安全边界

脚本**只新增**，不改不删：

- 不修改已有条目的任何字段
- 不删除 collection / item / 附件
- 不碰 `deletedItems`、不同步状态机
- 写入前必留备份

如果要对已有条目做改动，属于另一件事——用 Zotero 自带界面或 Web API。
