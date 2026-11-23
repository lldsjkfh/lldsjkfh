#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_outline.py — PDF 转 Markdown 并生成「精读导航索引」

为什么需要它：
    双栏论文转出的 Markdown 常有错序、断标题、表格误判，直接让模型“从头读到尾”
    既浪费上下文又容易漏掉关键图表。本脚本把 PDF 变成：
        paper.md      可 grep、可摘引的全文文本
        pages/*.png   关键页渲染图（公式 / 主表 / 框架图以此为准，视觉校对）
        outline.json  页码 → 行号区间、章节锚点、图表清单、精读读法建议

用法：
    python pdf_outline.py paper.pdf
    python pdf_outline.py paper.pdf --render key      # 只渲染含图表的关键页
    python pdf_outline.py paper.pdf --render all
    python pdf_outline.py paper.pdf --no-render
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PDF_CLI_CANDIDATES = [
    shutil.which("workbuddy-pdf"),
    os.path.expanduser("~/.workbuddy/external-packages/pdf-cli/workbuddy-pdf.exe"),
]

# 论文章节锚点（英文 + 中文），用于定位“该读哪一段”
SECTION_ANCHORS = [
    ("abstract", r"^#*\s*abstract\b"),
    ("introduction", r"^#*\s*(?:\d+\.?\s*)?introduction\b"),
    ("related_work", r"^#*\s*(?:\d+\.?\s*)?(?:related\s+work|background|prior\s+work)\b"),
    ("method", r"^#*\s*(?:\d+\.?\s*)?(?:method|approach|model|proposed|framework|formulation)\b"),
    ("experiments", r"^#*\s*(?:\d+\.?\s*)?(?:experiment|evaluation|result|empirical)\b"),
    ("ablation", r"^#*\s*(?:\d+\.?\s*)?(?:ablation|analysis|study)\b"),
    ("discussion", r"^#*\s*(?:\d+\.?\s*)?(?:discussion|limitation)\b"),
    ("conclusion", r"^#*\s*(?:\d+\.?\s*)?(?:conclusion|concluding|summary)\b"),
    ("references", r"^#*\s*(?:\d+\.?\s*)?(?:references|bibliography)\b"),
    ("appendix", r"^#*\s*(?:\d+\.?\s*)?(?:appendix|supplementary)\b"),
]


def find_cli():
    for c in PDF_CLI_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("命令失败：%s\n%s\n%s" % (" ".join(cmd), p.stdout, p.stderr))
    return (p.stdout or "") + (p.stderr or "")


def to_markdown(cli, pdf, md_path, force=False):
    if os.path.exists(md_path) and not force:
        return "cached"
    run([cli, pdf, md_path, "--format", "md-plain"])
    return "converted"


def render_pages(cli, pdf, out_dir, mode="key", key_pages=None):
    """workbuddy-pdf 只能整篇渲染；key 模式下渲染后仅保留关键页，避免几十张图干扰。"""
    if mode == "none":
        return []
    os.makedirs(out_dir, exist_ok=True)
    raw_dir = os.path.join(out_dir, "_all") if mode == "key" else out_dir
    if mode == "key":
        os.makedirs(raw_dir, exist_ok=True)
    run([cli, pdf, raw_dir, "--format", "png"])
    imgs = []
    for f in os.listdir(raw_dir):
        if f.lower().endswith((".png", ".jpg")):
            imgs.append(os.path.join(raw_dir, f))
    imgs.sort(key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1))
              if re.search(r"(\d+)", os.path.basename(p)) else 0)
    if mode == "key" and key_pages:
        keep = set(int(p) for p in key_pages)
        for p in imgs:
            m = re.search(r"(\d+)", os.path.basename(p))
            if m and int(m.group(1)) in keep:
                shutil.copy2(p, os.path.join(out_dir, os.path.basename(p)))
        shutil.rmtree(raw_dir, ignore_errors=True)
        return [os.path.join(out_dir, os.path.basename(p)) for p in imgs
                if re.search(r"(\d+)", os.path.basename(p))
                and int(re.search(r"(\d+)", os.path.basename(p)).group(1)) in keep]
    return imgs


def page_of_images(imgs):
    """把 pages/page-3.png 之类的文件名映射回页码。"""
    m = {}
    for p in imgs:
        n = re.search(r"(\d+)", os.path.basename(p))
        if n:
            m[int(n.group(1))] = p
    return m


def build_outline(md_text):
    lines = md_text.splitlines()
    pages = []          # (page_no, start_line, end_line)
    cur_page, cur_start = 0, 1
    for i, ln in enumerate(lines, 1):
        m = re.match(r"<!--\s*page\s+(\d+)\s*-->", ln.strip())
        if m:
            if cur_page:
                pages.append({"page": cur_page, "from": cur_start, "to": i - 1})
            cur_page, cur_start = int(m.group(1)), i
    if cur_page:
        pages.append({"page": cur_page, "from": cur_start, "to": len(lines)})

    headings = []
    for i, ln in enumerate(lines, 1):
        if re.match(r"^#{2,4}\s+\S", ln):
            headings.append({"line": i, "text": ln.lstrip("# ").strip()[:120]})

    # 章节锚点：只认短行（标题行），避免正文里出现 "In the introduction..." 误判
    sections = {}
    for name, pat in SECTION_ANCHORS:
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if len(s) <= 90 and re.match(pat, s, re.I):
                sections.setdefault(name, i)
                break

    captions = []
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^\s*(?:#+\s*)?(?:\*\*)?(Figure|Fig\.|Table)\s*([0-9]+[a-z]?)\s*[:.]\s*(.{0,160})",
                     ln, re.I)
        if m:
            captions.append({"line": i, "kind": m.group(1).lower().rstrip("."),
                             "no": m.group(2), "text": m.group(3).strip()[:160]})

    # 表格 / 架构图常被转成图片：按页统计图片密度，标出“必须看图”的页
    img_density = {}
    for ln in lines:
        m = re.search(r"<!--\s*image:\s*page\s+(\d+)", ln)
        if m:
            img_density[int(m.group(1))] = img_density.get(int(m.group(1)), 0) + 1

    refs_line = sections.get("references", 10 ** 9)
    body_chars = sum(len(l) for l in lines[:refs_line])
    total_chars = sum(len(l) for l in lines)

    return {
        "lines": len(lines),
        "chars": total_chars,
        "body_chars_before_refs": body_chars,
        "body_end_line": max(1, refs_line - 1),
        "pages": pages,
        "headings": headings,
        "sections": dict(sorted(sections.items(), key=lambda kv: kv[1])),
        "captions": captions,
        "image_density": dict(sorted(img_density.items())),
    }


def read_plan(outline, budget_chars=60000):
    """给出“一次读完 / 分节读”的建议，避免上下文超载。"""
    body = outline["body_chars_before_refs"]
    pages = outline["pages"]
    if body <= budget_chars:
        return {
            "mode": "single_pass",
            "note": "正文约 %d 字符，可一次读完：优先读 1-%d 行，参考文献从第 %d 行起可跳过"
                    % (body, outline["body_end_line"], outline["body_end_line"] + 1),
            "chunks": [],
        }
    n = max(2, -(-body // budget_chars))
    per = max(1, len(pages) // n + 1)
    chunks = []
    for k in range(0, len(pages), per):
        grp = pages[k:k + per]
        if grp:
            chunks.append({"pages": "%d-%d" % (grp[0]["page"], grp[-1]["page"]),
                           "lines": "%d-%d" % (grp[0]["from"], grp[-1]["to"])})
    return {
        "mode": "chunked",
        "note": "正文约 %d 字符，建议分 %d 段读，每段读完先落要点再读下一段" % (body, len(chunks)),
        "chunks": chunks,
    }


def main():
    ap = argparse.ArgumentParser(description="PDF → Markdown + 精读导航索引")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("--out", default=None, help="输出目录（默认与 PDF 同目录）")
    ap.add_argument("--render", choices=["key", "all", "none"], default="key",
                    help="渲染页面图：key=只渲染含图表的页（默认），all=全部，none=不渲染")
    ap.add_argument("--force", action="store_true", help="强制重新转换")
    args = ap.parse_args()

    pdf = os.path.abspath(args.pdf)
    if not os.path.exists(pdf):
        print("PDF 不存在：%s" % pdf, file=sys.stderr)
        return 2
    cli = find_cli()
    if not cli:
        print("找不到 workbuddy-pdf CLI", file=sys.stderr)
        return 2

    out_dir = os.path.abspath(args.out or os.path.dirname(pdf))
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "paper.md")

    st1 = to_markdown(cli, pdf, md_path, args.force)
    with open(md_path, "r", encoding="utf-8", errors="replace") as f:
        md_text = f.read()

    outline = build_outline(md_text)
    plan = read_plan(outline)

    # 关键页 = 图注所在页 + 图片密度高的页（表格/架构图常被转成图片，只能看图）
    key_page_nos = []
    for c in outline["captions"]:
        p = next((p["page"] for p in outline["pages"]
                  if p["from"] <= c["line"] <= p["to"]), None)
        if p and p not in key_page_nos:
            key_page_nos.append(p)
    for p, n in outline["image_density"].items():
        if n >= 3 and p not in key_page_nos:
            key_page_nos.append(p)
    key_page_nos.sort()

    imgs = render_pages(cli, pdf, os.path.join(out_dir, "pages"), args.render, key_page_nos)
    img_map = page_of_images(imgs)

    result = {
        "pdf": pdf,
        "markdown": md_path,
        "outline": outline,
        "read_plan": plan,
        "pages_dir": os.path.join(out_dir, "pages") if imgs else None,
        "page_images": {str(k): v for k, v in sorted(img_map.items())},
        "figure_table_pages": key_page_nos,
        "stats": {
            "md_lines": outline["lines"],
            "md_chars": outline["chars"],
            "headings": len(outline["headings"]),
            "captions": len(outline["captions"]),
            "figures": sum(1 for c in outline["captions"] if c["kind"].startswith("fig")),
            "tables": sum(1 for c in outline["captions"] if c["kind"] == "table"),
        },
    }

    # 顺手把代码仓库、数据集线索挖出来，第 0 步填“代码”字段可直接用
    code_links = sorted(set(re.findall(
        r"https?://(?:github\.com|gitlab\.com|huggingface\.co)/[\w\-./]+", md_text)))[:10]
    result["code_links"] = code_links

    with open(os.path.join(out_dir, "outline.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps({k: result[k] for k in
                      ("markdown", "pages_dir", "stats", "read_plan", "code_links",
                       "figure_table_pages")}, ensure_ascii=False, indent=2))
    if st1 == "converted":
        print("[ok] 已生成 paper.md / outline.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
