#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zotero_archive.py — 把一篇论文（PDF + 精读笔记）归档进 Zotero

产出结构（Zotero 左侧目录）：
    文献精读/                          ← 根 collection（可配置）
        └─ 2015 Batch Normalization   ← 每篇论文一个子 collection
             ├─ 论文条目（含 PDF 附件）
             ├─ 笔记：精读笔记（Zotero 内可读可搜）
             └─ 附件：note.md（链接到本地原文，含插图）

为什么必须关 Zotero：
    Zotero 对 zotero.sqlite 持有独占锁，运行期间无法写入。脚本会检测进程、
    优雅关闭（不带 /F，等价于点窗口关闭，不会丢数据）、写前自动备份、写完校验。

用法：
    python zotero_archive.py --paper-dir "D:/WorkBuddyFiles/papers/2015-xxx" --auto-close
    python zotero_archive.py --paper-dir ... --dry-run        # 只打印计划
    python zotero_archive.py --paper-dir ... --root "文献精读" --collection "自定义名"
"""

import argparse
import hashlib
import html
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

KEY_ALPHABET = "23456789ABCDEFGHIJKLMNPQRSTUVWXYZ"
ITEM_TYPES = {"attachment": 3, "conferencePaper": 11, "journalArticle": 22,
              "note": 28, "preprint": 31, "report": 34}
CREATOR_AUTHOR = 10
LINK_IMPORTED_FILE, LINK_IMPORTED_URL, LINK_LINKED_FILE = 0, 1, 2
SYNC_TO_UPLOAD, SYNC_IN_SYNC = 1, 2

CONF_HINTS = ("cvpr", "iccv", "eccv", "neurips", "nips", "icml", "iclr", "aaai",
              "ijcai", "acl", "emnlp", "naacl", "coling", "kdd", "sigir", "www",
              "mm", "icra", "iros", "miccai", "interspeech", "icassp", "bmvc",
              "wacv", "3dv", "corl", "rss", "uai", "aistats")


# ---------------------------------------------------------------- 环境

def zotero_exe_candidates():
    return [r"C:\Program Files\Zotero\zotero.exe",
            r"C:\Program Files (x86)\Zotero\zotero.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Zotero\zotero.exe")]


def find_zotero_exe():
    for p in zotero_exe_candidates():
        if os.path.exists(p):
            return p
    return None


def zotero_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq zotero.exe"],
                             capture_output=True, text=True, encoding="gbk",
                             errors="replace", timeout=20).stdout or ""
    except Exception:
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq zotero.exe"],
                                 capture_output=True, timeout=20).stdout.decode(
                                     "gbk", "replace")
        except Exception:
            return False
    return "zotero.exe" in out.lower()


def close_zotero(wait=40):
    """优雅关闭（等同点窗口关闭按钮），不强制 kill。"""
    subprocess.run(["taskkill", "/IM", "zotero.exe"], capture_output=True, timeout=30)
    for _ in range(wait):
        if not zotero_running():
            return True
        time.sleep(1)
    return not zotero_running()


def start_zotero():
    exe = find_zotero_exe()
    if not exe:
        return False
    try:
        os.startfile(exe)  # noqa: S606  Windows 专用
        return True
    except Exception:
        try:
            subprocess.Popen([exe], close_fds=True)
            return True
        except Exception:
            return False


def find_data_dir():
    """优先读 Zotero profile 里的 extensions.zotero.dataDir。"""
    cands = []
    roaming = os.path.expandvars(r"%APPDATA%\Zotero\Zotero\Profiles")
    if os.path.isdir(roaming):
        for d in os.listdir(roaming):
            p = os.path.join(roaming, d, "prefs.js")
            if os.path.exists(p):
                cands.append(p)
    for p in cands:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
            m = re.search(r'user_pref\("extensions\.zotero\.dataDir",\s*"(.+?)"\)', txt)
            if m:
                return m.group(1).replace("\\\\", "\\")
        except Exception:
            pass
    for p in (r"C:\Users\%s\Zotero" % os.environ.get("USERNAME", ""),
              os.path.expanduser("~/Zotero")):
        if os.path.isdir(p):
            return p
    raise RuntimeError("找不到 Zotero 数据目录，请用 --data-dir 指定")


# ---------------------------------------------------------------- 工具

def gen_key(used):
    while True:
        k = "".join(random.choice(KEY_ALPHABET) for _ in range(8))
        if k not in used:
            used.add(k)
            return k


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_name(full):
    """返回 (firstName, lastName, fieldMode)。中文名 / 单词名走单字段模式。"""
    full = re.sub(r"\s+", " ", (full or "").strip())
    if not full:
        return "", "", 1
    if re.search(r"[\u4e00-\u9fff]", full):
        return "", full, 1
    parts = full.split(" ")
    if len(parts) == 1:
        return "", full, 1
    return " ".join(parts[:-1]), parts[-1], 0


def md_to_html(md, base_dir=None):
    """极简 Markdown → HTML（够 Zotero 笔记用：标题/列表/表格/代码/强调/图片）。"""

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                   lambda m: '<img src="%s" alt="%s" style="max-width:100%%">'
                             % (m.group(2), m.group(1)), s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s

    out, in_code, in_table, list_open = [], False, False, None

    def close_list():
        nonlocal list_open
        if list_open:
            out.append("</%s>" % list_open)
            list_open = None

    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            close_list()
            out.append("<pre><code>" if not in_code else "</code></pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if not line.strip():
            close_list()
            if in_table:
                out.append("</table>")
                in_table = False
            continue
        if re.match(r"^\s*\|.*\|\s*$", line):
            if re.match(r"^\s*\|[\s:\-|]+\|\s*$", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not in_table:
                close_list()
                out.append('<table border="1" cellspacing="0" cellpadding="4">')
                in_table = True
                out.append("<tr>" + "".join("<th>%s</th>" % inline(c) for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_list()
            lv = min(6, len(m.group(1)) + 1)
            out.append("<h%d>%s</h%d>" % (lv, inline(m.group(2)), lv))
            continue
        m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", line)
        if m:
            tag = "ul" if m.group(1) in "-*+" else "ol"
            if list_open != tag:
                close_list()
                out.append("<%s>" % tag)
                list_open = tag
            out.append("<li>%s</li>" % inline(m.group(2)))
            continue
        if line.startswith(">"):
            close_list()
            out.append("<blockquote>%s</blockquote>" % inline(line.lstrip("> ")))
            continue
        close_list()
        out.append("<p>%s</p>" % inline(line))

    close_list()
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")
    body = "\n".join(out)
    return '<div class="zotero-note znv1">\n%s\n</div>' % body


# ---------------------------------------------------------------- 元信息

def load_meta(paper_dir, explicit=None):
    if explicit:
        with open(explicit, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("matched", data) if isinstance(data, dict) else data
    for name in ("meta.json", "metadata.json"):
        p = os.path.join(paper_dir, name)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("matched", data) if isinstance(data, dict) else data
    return {}


def guess_item_type(meta):
    if meta.get("_force_type"):
        return meta["_force_type"]
    venue = (meta.get("venue") or "").lower()
    doi = meta.get("doi") or ""
    if meta.get("arxiv_id") and (not venue or "arxiv" in venue):
        return "preprint"
    if any(h in venue for h in CONF_HINTS):
        return "conferencePaper"
    if doi or venue:
        return "journalArticle"
    return "preprint"


def collection_name_of(meta, fallback):
    t = re.sub(r"\s+", " ", ((meta.get("title") or fallback)).strip())
    # 优先用主标题（冒号/破折号之前），像人起的文件夹名
    main = re.split(r"[:：]| — | – ", t)[0].strip()
    if len(main) < 12:
        main = t
    main = main.replace("/", " ").replace("\\", " ")
    if len(main) > 60:
        main = main[:57].rstrip() + "…"
    year = meta.get("year") or ""
    return ("%s %s" % (year, main)).strip()


# ---------------------------------------------------------------- 写库

class ZoteroDB:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.path = os.path.join(data_dir, "zotero.sqlite")
        self.conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.keys = {r[0] for r in self.conn.execute("SELECT key FROM items")}
        self.keys |= {r[0] for r in self.conn.execute("SELECT key FROM collections")}
        self.fields = {r[1]: r[0] for r in
                       self.conn.execute("SELECT fieldID, fieldName FROM fields")}
        self._type_fields = {}

    # --- 基础
    def box(self):
        return self.conn

    def value_id(self, value):
        row = self.conn.execute("SELECT valueID FROM itemDataValues WHERE value=?",
                                (value,)).fetchone()
        if row:
            return row[0]
        cur = self.conn.execute(
            "INSERT INTO itemDataValues (value, valueNormalized) VALUES (?, NULL)", (value,))
        return cur.lastrowid

    def allowed_fields(self, item_type):
        tid = ITEM_TYPES[item_type]
        if tid not in self._type_fields:
            self._type_fields[tid] = {r[0] for r in self.conn.execute(
                "SELECT f.fieldName FROM itemTypeFields itf JOIN fields f USING(fieldID)"
                " WHERE itf.itemTypeID=?", (tid,))}
        return self._type_fields[tid]

    def new_item(self, item_type, library_id=1):
        key = gen_key(self.keys)
        ts = now_str()
        cur = self.conn.execute(
            "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified,"
            " libraryID, key, version, clientVersion, synced) VALUES (?,?,?,?,?,?,0,0,0)",
            (ITEM_TYPES[item_type], ts, ts, ts, library_id, key))
        return cur.lastrowid, key

    def set_fields(self, item_id, item_type, fields):
        allowed = self.allowed_fields(item_type)
        for name, val in fields.items():
            if not val or name not in allowed:
                continue
            self.conn.execute("INSERT OR REPLACE INTO itemData (itemID, fieldID, valueID)"
                              " VALUES (?,?,?)",
                              (item_id, self.fields[name], self.value_id(str(val))))

    def add_creator(self, item_id, full_name, order):
        first, last, mode = split_name(full_name)
        if not last:
            return
        row = self.conn.execute(
            "SELECT creatorID FROM creators WHERE IFNULL(firstName,'')=? AND lastName=?"
            " AND fieldMode=?", (first, last, mode)).fetchone()
        if row:
            cid = row[0]
        else:
            cid = self.conn.execute(
                "INSERT INTO creators (firstName, lastName, fieldMode, firstNameNormalized,"
                " lastNameNormalized) VALUES (?,?,?,NULL,NULL)",
                (first or None, last, mode)).lastrowid
        self.conn.execute("INSERT INTO itemCreators (itemID, creatorID, creatorTypeID,"
                          " orderIndex) VALUES (?,?,?,?)",
                          (item_id, cid, CREATOR_AUTHOR, order))

    # --- collection
    def find_collection(self, name, parent_id=None):
        row = self.conn.execute(
            "SELECT collectionID FROM collections WHERE collectionName=? AND"
            " IFNULL(parentCollectionID,-1)=IFNULL(?,-1) AND libraryID=1",
            (name, parent_id)).fetchone()
        return row[0] if row else None

    def ensure_collection(self, name, parent_id=None):
        cid = self.find_collection(name, parent_id)
        if cid:
            return cid, False
        key = gen_key(self.keys)
        ts = now_str()
        cid = self.conn.execute(
            "INSERT INTO collections (collectionName, parentCollectionID, clientDateModified,"
            " libraryID, key, version, clientVersion, synced) VALUES (?,?,?,1,?,0,0,0)",
            (name, parent_id, ts, key)).lastrowid
        return cid, True

    # --- 附件 / 笔记
    def add_pdf_attachment(self, parent_id, pdf_path, library_id=1):
        key = gen_key(self.keys)
        ts = now_str()
        item_id = self.conn.execute(
            "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified,"
            " libraryID, key, version, clientVersion, synced) VALUES (?,?,?,?,?,?,0,0,0)",
            (ITEM_TYPES["attachment"], ts, ts, ts, library_id, key)).lastrowid
        folder = os.path.join(self.data_dir, "storage", key)
        os.makedirs(folder, exist_ok=True)
        fname = os.path.basename(pdf_path)
        dest = os.path.join(folder, fname)
        shutil.copy2(pdf_path, dest)
        self.conn.execute(
            "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType,"
            " path, syncState, storageModTime, storageHash) VALUES (?,?,?,?,?,?,?,?)",
            (item_id, parent_id, LINK_IMPORTED_FILE, "application/pdf",
             "storage:" + fname, SYNC_TO_UPLOAD,
             int(os.path.getmtime(dest) * 1000), md5_of(dest)))
        self.set_fields(item_id, "attachment", {"title": fname})
        return item_id, key

    def add_linked_attachment(self, parent_id, file_path, title, mime, library_id=1):
        key = gen_key(self.keys)
        ts = now_str()
        item_id = self.conn.execute(
            "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified,"
            " libraryID, key, version, clientVersion, synced) VALUES (?,?,?,?,?,?,0,0,0)",
            (ITEM_TYPES["attachment"], ts, ts, ts, library_id, key)).lastrowid
        self.conn.execute(
            "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType,"
            " path, syncState) VALUES (?,?,?,?,?,0)",
            (item_id, parent_id, LINK_LINKED_FILE, mime, os.path.abspath(file_path)))
        self.set_fields(item_id, "attachment", {"title": title})
        return item_id, key

    def add_note(self, parent_id, html_body, title, library_id=1):
        key = gen_key(self.keys)
        ts = now_str()
        item_id = self.conn.execute(
            "INSERT INTO items (itemTypeID, dateAdded, dateModified, clientDateModified,"
            " libraryID, key, version, clientVersion, synced) VALUES (?,?,?,?,?,?,0,0,0)",
            (ITEM_TYPES["note"], ts, ts, ts, library_id, key)).lastrowid
        self.conn.execute("INSERT INTO itemNotes (itemID, parentItemID, note, title)"
                          " VALUES (?,?,?,?)", (item_id, parent_id, html_body, title))
        return item_id, key

    def add_to_collection(self, collection_id, item_id, order=0):
        # 不用 INSERT OR IGNORE：那会把 NOT NULL / 触发器错误一起吞掉，只吞“已在集合里”
        try:
            self.conn.execute("INSERT INTO collectionItems (collectionID, itemID, orderIndex)"
                              " VALUES (?,?,?)", (collection_id, item_id, order or 0))
        except sqlite3.IntegrityError:
            pass

    def collection_items(self, collection_id):
        return [r for r in self.conn.execute(
            "SELECT i.itemID, i.itemTypeID, i.key FROM collectionItems ci"
            " JOIN items i USING(itemID) WHERE ci.collectionID=?", (collection_id,))]

    def item_title(self, item_id):
        row = self.conn.execute(
            "SELECT v.value FROM itemData d JOIN itemDataValues v USING(valueID)"
            " JOIN fields f USING(fieldID) WHERE d.itemID=? AND f.fieldName='title'",
            (item_id,)).fetchone()
        return row[0] if row else ""


# ---------------------------------------------------------------- 主流程

def build_plan(paper_dir, meta, note_path, figs):
    return {
        "paper_dir": paper_dir,
        "title": meta.get("title"),
        "authors": len(meta.get("authors") or []),
        "item_type": guess_item_type(meta),
        "pdf": os.path.join(paper_dir, "paper.pdf"),
        "note_md": note_path,
        "figures": len(figs),
        "collection": collection_name_of(meta, os.path.basename(paper_dir)),
    }


def main():
    ap = argparse.ArgumentParser(description="把论文与精读笔记归档进 Zotero")
    ap.add_argument("--paper-dir", required=True, help="论文目录（含 paper.pdf / note.md / meta.json）")
    ap.add_argument("--meta", default=None, help="元信息 JSON（默认读 paper-dir/meta.json）")
    ap.add_argument("--note", default=None, help="笔记 md 路径（默认 paper-dir/note.md）")
    ap.add_argument("--root", default="文献精读", help="根 collection 名（默认：文献精读）")
    ap.add_argument("--collection", default=None, help="子 collection 名（默认：年份 + 标题）")
    ap.add_argument("--data-dir", default=None, help="Zotero 数据目录（默认自动探测）")
    ap.add_argument("--auto-close", action="store_true", help="自动优雅关闭并在完成后重启 Zotero")
    ap.add_argument("--no-restart", action="store_true", help="归档后不自动重启 Zotero")
    ap.add_argument("--no-backup", action="store_true", help="跳过备份（不推荐）")
    ap.add_argument("--dry-run", action="store_true", help="只打印归档计划")
    ap.add_argument("--venue", default=None,
                    help="手动指定发表处（如 \"ICML 2015\"）。arXiv 预印本常缺 venue，读论文首页后可用它纠正")
    ap.add_argument("--item-type", default=None,
                    choices=["preprint", "conferencePaper", "journalArticle"],
                    help="手动指定 Zotero 条目类型")
    args = ap.parse_args()

    paper_dir = os.path.abspath(args.paper_dir)
    if not os.path.isdir(paper_dir):
        print(json.dumps({"ok": False, "error": "目录不存在：%s" % paper_dir}, ensure_ascii=False))
        return 2

    meta = load_meta(paper_dir, args.meta)
    if args.venue:
        meta["venue"] = args.venue
    if args.item_type:
        meta["_force_type"] = args.item_type
    pdf = os.path.join(paper_dir, "paper.pdf")
    note_path = os.path.abspath(args.note) if args.note else os.path.join(paper_dir, "note.md")
    figs = []
    fig_dir = os.path.join(paper_dir, "fig")
    if os.path.isdir(fig_dir):
        figs = sorted(f for f in os.listdir(fig_dir)
                      if f.lower().endswith((".png", ".svg", ".jpg")))

    plan = build_plan(paper_dir, meta, note_path if os.path.exists(note_path) else None, figs)
    if args.collection:
        plan["collection"] = args.collection
    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "plan": plan}, ensure_ascii=False, indent=2))
        return 0

    if not os.path.exists(pdf):
        print(json.dumps({"ok": False, "error": "缺少 paper.pdf：%s" % pdf}, ensure_ascii=False))
        return 2

    data_dir = args.data_dir or find_data_dir()
    db_path = os.path.join(data_dir, "zotero.sqlite")
    # 只有指向真实库时才需要检查/关闭 Zotero；指向副本库（测试、迁移）时直接写
    try:
        is_real_lib = os.path.abspath(data_dir) == os.path.abspath(find_data_dir())
    except Exception:
        is_real_lib = True
    was_running = zotero_running() and is_real_lib

    if was_running:
        if not args.auto_close:
            print(json.dumps({
                "ok": False, "need_close": True,
                "error": "Zotero 正在运行，数据库被独占锁定。请关闭 Zotero 后重试，或加 --auto-close 让脚本自动处理。",
            }, ensure_ascii=False, indent=2))
            return 4
        print("[..] 正在优雅关闭 Zotero", file=sys.stderr)
        if not close_zotero():
            print(json.dumps({"ok": False,
                              "error": "Zotero 未能自动退出，请手动关闭（可能有未保存的编辑）后重试。"},
                             ensure_ascii=False))
            return 4

    backup = None
    if not args.no_backup and os.path.exists(db_path):
        backup = db_path + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(db_path, backup)
        for suffix in ("-wal", "-shm"):
            src = db_path + suffix
            if os.path.exists(src):
                shutil.copy2(src, backup + suffix)

    result = {"ok": False}
    try:
        db = ZoteroDB(data_dir)
        db.conn.execute("BEGIN IMMEDIATE")

        root_id, root_new = db.ensure_collection(args.root, None)
        col_name = plan["collection"]
        col_id, col_new = db.ensure_collection(col_name, root_id)

        # 幂等：该 collection 下已有同标题论文则复用
        existing = None
        for iid, itype, _ in db.collection_items(col_id):
            if itype != ITEM_TYPES["attachment"] and \
                    db.item_title(iid).strip().lower() == (meta.get("title") or "").strip().lower():
                existing = iid
                break

        if existing:
            item_id = existing
            created = False
        else:
            itype = plan["item_type"]
            item_id, item_key = db.new_item(itype)
            venue = meta.get("venue") or ""
            fields = {
                "title": meta.get("title") or os.path.basename(paper_dir),
                "abstractNote": meta.get("abstract"),
                "date": meta.get("year"),
                "DOI": meta.get("doi"),
                "url": meta.get("abs_url") or
                       ("https://arxiv.org/abs/%s" % meta["arxiv_id"] if meta.get("arxiv_id") else None),
                "language": "en",
                "libraryCatalog": "arXiv" if meta.get("arxiv_id") else None,
                "extra": "\n".join(x for x in [
                    "arXiv: %s" % meta["arxiv_id"] if meta.get("arxiv_id") else "",
                    "Citations: %s" % meta["citation_count"] if meta.get("citation_count") else "",
                    "PDF: %s" % (meta.get("pdf_url") or "") if meta.get("pdf_url") else "",
                ] if x) or None,
            }
            if itype == "journalArticle":
                fields["publicationTitle"] = venue
            elif itype == "conferencePaper":
                fields["proceedingsTitle"] = venue
                fields["conferenceName"] = venue
            else:
                fields["repository"] = "arXiv" if meta.get("arxiv_id") else (venue or None)
            db.set_fields(item_id, itype, fields)
            for i, name in enumerate(meta.get("authors") or []):
                db.add_creator(item_id, name, i)
            db.add_to_collection(col_id, item_id)
            created = True

        # 附件与笔记（每次都会补齐缺失项，可重复执行）
        pdf_att = db.add_pdf_attachment(item_id, pdf)
        note_att = None
        note_item = None
        if os.path.exists(note_path):
            with open(note_path, "r", encoding="utf-8", errors="replace") as f:
                md = f.read()
            note_item = db.add_note(item_id, md_to_html(md), "精读笔记", )
            note_att = db.add_linked_attachment(item_id, note_path, "note.md（本地原文，含插图）",
                                                "text/markdown")
        for f in figs:
            db.add_linked_attachment(item_id, os.path.join(fig_dir, f), "图：" + f,
                                     "image/svg+xml" if f.endswith(".svg") else "image/png")

        db.conn.execute("COMMIT")

        # 校验
        check = db.collection_items(col_id)
        att_row = db.conn.execute(
            "SELECT path FROM itemAttachments WHERE itemID=?", (pdf_att[0],)).fetchone()
        att_file = os.path.join(data_dir, "storage", pdf_att[1],
                                (att_row[0] or "").replace("storage:", ""))
        result = {
            "ok": True,
            "data_dir": data_dir,
            "backup": backup,
            "root_collection": {"name": args.root, "id": root_id, "created": root_new},
            "collection": {"name": col_name, "id": col_id, "created": col_new},
            "item": {"id": item_id, "created": created, "type": plan["item_type"],
                     "title": meta.get("title")},
            "attachments": {"pdf": os.path.exists(att_file),
                            "pdf_path": att_file,
                            "note": bool(note_item),
                            "note_md": bool(note_att),
                            "figures": len(figs)},
            "collection_items": len(check),
            "note": "Zotero 下次启动即可看到；若开启同步，新条目会自动上传。",
        }
        db.conn.close()
    except Exception as e:
        try:
            db.conn.execute("ROLLBACK")
        except Exception:
            pass
        result = {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "backup": backup}
    finally:
        if was_running and args.auto_close and not args.no_restart:
            time.sleep(0.5)
            if start_zotero():
                result["restarted_zotero"] = True

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 5


if __name__ == "__main__":
    sys.exit(main())
