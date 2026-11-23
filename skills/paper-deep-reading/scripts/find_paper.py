#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_paper.py — 论文定位与 PDF 获取

输入：论文标题 / arXiv ID / DOI / URL
输出：候选列表 + 最佳匹配元信息 + 可下载的 PDF（magic number 校验通过）

用法：
    python find_paper.py "Batch Normalization: Accelerating Deep Network Training"
    python find_paper.py 1502.03167
    python find_paper.py 10.1109/CVPR.2016.90
    python find_paper.py "Attention is all you need" --out D:/WorkBuddyFiles/papers
    python find_paper.py "..." --no-download --json meta.json

数据源（按可靠性排序，逐级兜底）：
    arXiv 网页检索 > arXiv API > dblp（CS 会议/期刊元数据权威） > Crossref > Semantic Scholar（默认关闭，常限流）
"""

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) paper-deep-reading/1.0"
DEFAULT_LIB = os.environ.get("PAPER_LIB", "D:/WorkBuddyFiles/papers")
TIMEOUT = 30
ATOM = "{http://www.w3.org/2005/Atom}"


# ---------------------------------------------------------------- HTTP 基础

def http_get(url, timeout=TIMEOUT, retries=2, headers=None):
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503) and i < retries:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            last = e
            if i < retries:
                time.sleep(1.5 * (i + 1))
                continue
            raise
    raise last


def get_json(url, **kw):
    raw, _ = http_get(url, **kw)
    return json.loads(raw.decode("utf-8", "replace"))


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- 输入识别

ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?\s*(\d{4}\.\d{4,5})(v\d+)?$", re.I)
DOI_RE = re.compile(r"^(?:doi:\s*)?(10\.\d{4,9}/[^\s]+)$", re.I)


def detect_query(q):
    q = q.strip()
    m = ARXIV_ID_RE.match(q)
    if m:
        return "arxiv_id", m.group(1)
    m = DOI_RE.match(q)
    if m:
        return "doi", m.group(1).rstrip(".")
    if "arxiv.org/" in q:
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", q)
        if m:
            return "arxiv_id", m.group(1)
    if q.lower().startswith(("http://", "https://")):
        return "url", q
    return "title", q


def norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_score(a, b):
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def slugify(title, max_words=6):
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-]*", title or "")
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "via", "is"}
    keep = [w for w in words if w.lower() not in stop][:max_words]
    return ("-".join(keep) or "paper")[:80]


# ---------------------------------------------------------------- arXiv

def _parse_arxiv_entry(e):
    eid = (e.findtext(ATOM + "id", "") or "").strip()
    m = re.search(r"abs/([^v]+?)(v\d+)?$", eid)
    if not m:
        return None
    aid = m.group(1)
    jr = e.find(ATOM + "journal_ref")
    return {
        "source": "arxiv",
        "arxiv_id": aid,
        "title": re.sub(r"\s+", " ", e.findtext(ATOM + "title", "") or "").strip(),
        "abstract": re.sub(r"\s+", " ", e.findtext(ATOM + "summary", "") or "").strip(),
        "authors": [a.findtext(ATOM + "name", "") for a in e.findall(ATOM + "author")],
        "year": (e.findtext(ATOM + "published", "") or "")[:4],
        "venue": (jr.text.strip() if jr is not None and jr.text else "arXiv"),
        "pdf_url": "https://arxiv.org/pdf/%s" % aid,
        "abs_url": "https://arxiv.org/abs/%s" % aid,
    }


def arxiv_batch(ids):
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return []
    url = ("https://export.arxiv.org/api/query?id_list=%s&max_results=%d"
           % (",".join(ids), len(ids)))
    raw, _ = http_get(url, retries=1)
    out = []
    for e in ET.fromstring(raw).findall(ATOM + "entry"):
        c = _parse_arxiv_entry(e)
        if c:
            out.append(c)
    return out


def search_arxiv_html(title, max_results=8):
    """arXiv 网页检索：对长标题、带副标题的论文比官方 API 的 ti: 语法宽容得多。"""
    q = re.sub(r"[^\w\s\-]", " ", title or "")
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return []
    ids = []
    for stype in ("title", "all"):
        url = ("https://arxiv.org/search/?query=%s&searchtype=%s&size=50"
               % (urllib.parse.quote(q), stype))
        try:
            raw, _ = http_get(url, retries=1)
        except Exception:
            continue
        ids = re.findall(r"https://arxiv\.org/abs/(\d{4}\.\d{4,5})",
                         raw.decode("utf-8", "replace"))
        if ids:
            break
    return arxiv_batch(list(dict.fromkeys(ids))[:max_results])


def search_arxiv_api(title, max_results=6):
    """官方 API 兜底：取前几个实词做 AND 查询。"""
    words = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", title or "")
             if len(w) > 2][:4]
    if not words:
        return []
    q = " AND ".join("ti:%s" % w for w in words)
    url = ("https://export.arxiv.org/api/query?search_query=%s&max_results=%d"
           % (urllib.parse.quote(q, safe=":"), max_results))
    try:
        raw, _ = http_get(url, retries=1)
    except Exception:
        return []
    out = []
    for e in ET.fromstring(raw).findall(ATOM + "entry"):
        c = _parse_arxiv_entry(e)
        if c:
            out.append(c)
    return out


# ---------------------------------------------------------------- dblp

def search_dblp(title):
    url = ("https://dblp.org/search/publ/api?q=%s&format=json&h=8"
           % urllib.parse.quote(title))
    try:
        data = get_json(url, retries=1)
    except Exception:
        return []
    hits = (((data.get("result") or {}).get("hits") or {}).get("hit") or [])
    out = []
    for h in hits:
        info = h.get("info") or {}
        authors = info.get("authors", {}).get("author") or []
        if isinstance(authors, dict):
            authors = [authors]
        names = []
        for a in authors:
            names.append(a.get("text") if isinstance(a, dict) else str(a))
        ee = info.get("ee") or ""
        out.append({
            "source": "dblp",
            "title": (info.get("title") or "").rstrip("."),
            "abstract": "",
            "authors": names,
            "year": str(info.get("year") or ""),
            "venue": info.get("venue") or "",
            "doi": info.get("doi"),
            "pdf_url": ee if str(ee).lower().endswith(".pdf") else None,
            "abs_url": ee or None,
        })
    return out


# ---------------------------------------------------------------- 其他源

def search_crossref(title):
    url = ("https://api.crossref.org/works?query.bibliographic=%s&rows=5"
           "&select=title,DOI,issued,container-title,author,link,is-referenced-by-count"
           % urllib.parse.quote(title))
    try:
        data = get_json(url, retries=1)
    except Exception:
        return []
    out = []
    for it in (data.get("message", {}).get("items") or []):
        pdf = None
        for l in it.get("link") or []:
            if "pdf" in (l.get("content-type") or "").lower():
                pdf = l.get("URL")
                break
        out.append({
            "source": "crossref",
            "title": (it.get("title") or [""])[0],
            "abstract": "",
            "authors": ["%s %s" % (a.get("given", ""), a.get("family", ""))
                        for a in (it.get("author") or [])],
            "year": str(((it.get("issued", {}).get("date-parts") or [[None]])[0][0]) or ""),
            "venue": (it.get("container-title") or [""])[0],
            "doi": it.get("DOI"),
            "pdf_url": pdf,
            "citation_count": it.get("is-referenced-by-count"),
        })
    return out


S2_FIELDS = "title,year,venue,abstract,authors,externalIds,openAccessPdf,citationCount"


def search_s2(title):
    """Semantic Scholar 匿名配额极低，常 429；仅作可选增强（引用数 / 开放 PDF）。"""
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query=%s&limit=6&fields=%s"
           % (urllib.parse.quote(title), S2_FIELDS))
    try:
        data = get_json(url, retries=0)
    except Exception:
        return []
    out = []
    for p in (data.get("data") or []):
        ext = p.get("externalIds") or {}
        out.append({
            "source": "s2",
            "title": p.get("title") or "",
            "abstract": p.get("abstract") or "",
            "authors": [a.get("name") for a in (p.get("authors") or [])],
            "year": str(p.get("year") or ""),
            "venue": p.get("venue") or "",
            "doi": ext.get("DOI"),
            "arxiv_id": ext.get("ArXiv"),
            "pdf_url": (p.get("openAccessPdf") or {}).get("url"),
            "citation_count": p.get("citationCount"),
        })
    return out


# ---------------------------------------------------------------- PDF

def probe_pdf(url):
    """确认 URL 真的是 PDF（读头部字节）。"""
    if not url:
        return False
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Range": "bytes=0-4095", "Accept": "application/pdf,*/*"})
        with urllib.request.urlopen(req, timeout=45) as r:
            head = r.read(4096)
            ctype = (r.headers.get("Content-Type") or "").lower()
        return head[:5] == b"%PDF-" or ("pdf" in ctype and b"%PDF" in head[:2048])
    except Exception:
        return False


def download_pdf(url, dest):
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    with open(tmp, "rb") as f:
        magic = f.read(5)
    if magic != b"%PDF-":
        os.remove(tmp)
        raise RuntimeError("下载内容不是 PDF（可能是落地页或被拦截）：%s" % url)
    size = os.path.getsize(tmp)
    if size < 20_000:
        os.remove(tmp)
        raise RuntimeError("PDF 过小（%d bytes），疑似错误页：%s" % (size, url))
    os.replace(tmp, dest)
    return size


def pick_pdf_url(cand):
    urls = []
    if cand.get("arxiv_id"):
        urls.append("https://arxiv.org/pdf/%s" % cand["arxiv_id"])
    if cand.get("pdf_url"):
        urls.append(cand["pdf_url"])
    if cand.get("doi"):
        urls.append("https://doi.org/%s" % cand["doi"])
    return list(dict.fromkeys(u for u in urls if u))


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="论文定位与 PDF 获取")
    ap.add_argument("query", help="论文标题 / arXiv ID / DOI / URL")
    ap.add_argument("--out", default=DEFAULT_LIB, help="论文库根目录（默认 %s）" % DEFAULT_LIB)
    ap.add_argument("--dir-name", default=None, help="自定义子目录名")
    ap.add_argument("--no-download", action="store_true", help="只检索不下载")
    ap.add_argument("--json", default=None, help="结果写入 JSON 文件")
    ap.add_argument("--top", type=int, default=3, help="输出候选数量")
    ap.add_argument("--with-s2", action="store_true", help="额外查询 Semantic Scholar（易限流）")
    ap.add_argument("--with-dblp", action="store_true",
                    help="额外查询 dblp（会议/期刊信息权威，但站点常有反爬校验）")
    args = ap.parse_args()

    kind, value = detect_query(args.query)
    candidates = []

    if kind == "arxiv_id":
        candidates = arxiv_batch([value])
    elif kind == "doi":
        candidates = search_crossref(value)[:1]
        for c in candidates:
            c["pdf_url"] = None
        candidates.append({"source": "doi", "doi": value, "title": value, "authors": [],
                           "year": "", "venue": "", "pdf_url": "https://doi.org/%s" % value})
    elif kind == "url":
        candidates = [{"source": "url", "title": value, "authors": [], "year": "",
                       "venue": "", "pdf_url": value}]
    else:
        for fn in (search_arxiv_html, search_crossref):
            try:
                got = fn(value)
            except Exception as e:
                print("[warn] %s 失败：%s" % (fn.__name__, e), file=sys.stderr)
                continue
            candidates += got
        if not any(c.get("source") == "arxiv" for c in candidates):
            try:
                candidates += search_arxiv_api(value)
            except Exception as e:
                print("[warn] arxiv api 失败：%s" % e, file=sys.stderr)
        # dblp 的会议/期刊信息最权威，但站点有反爬挑战，默认关闭
        if args.with_dblp:
            try:
                candidates += search_dblp(value)
            except Exception as e:
                print("[warn] dblp 失败（常有反爬验证）：%s" % e, file=sys.stderr)
        if args.with_s2:
            try:
                candidates += search_s2(value)
            except Exception as e:
                print("[warn] S2 失败：%s" % e, file=sys.stderr)

    if not candidates:
        print(json.dumps({"ok": False, "error": "未检索到任何结果", "query": args.query},
                         ensure_ascii=False, indent=2))
        return 2

    for c in candidates:
        s = title_score(value, c.get("title")) if kind == "title" else 1.0
        if c.get("arxiv_id"):
            s = min(1.0, s + 0.02)
        c["score"] = round(s, 3)
    candidates.sort(key=lambda c: (-c["score"], -(c.get("citation_count") or 0)))

    best = dict(candidates[0])
    for c in candidates[1:]:
        if title_score(best["title"], c["title"]) >= 0.95:
            for k in ("doi", "arxiv_id", "citation_count", "venue", "pdf_url",
                      "abstract", "abs_url"):
                if not best.get(k) and c.get(k):
                    best[k] = c[k]

    confidence = "high" if best["score"] >= 0.86 else (
        "medium" if best["score"] >= 0.62 else "low")

    result = {
        "ok": True,
        "query": args.query,
        "query_kind": kind,
        "confidence": confidence,
        "matched": {
            "title": best.get("title"),
            "authors": best.get("authors") or [],
            "year": best.get("year"),
            "venue": best.get("venue") or "",
            "abstract": best.get("abstract") or "",
            "doi": best.get("doi"),
            "arxiv_id": best.get("arxiv_id"),
            "citation_count": best.get("citation_count"),
            "abs_url": best.get("abs_url"),
            "score": best.get("score"),
        },
        "candidates": [{k: c.get(k) for k in
                        ("source", "title", "year", "venue", "doi", "arxiv_id",
                         "pdf_url", "score", "citation_count")}
                       for c in candidates[:args.top]],
        "pdf": None,
        "needs_confirmation": confidence != "high",
    }

    if not args.no_download:
        slug = args.dir_name or "%s%s" % (
            (best.get("year") + "-") if best.get("year") else "",
            slugify(best.get("title") or value))
        folder = os.path.join(args.out, slug)
        dest = os.path.join(folder, "paper.pdf")
        if os.path.exists(dest) and os.path.getsize(dest) > 20_000:
            result["pdf"] = {"url": None, "path": dest,
                             "bytes": os.path.getsize(dest), "cached": True}
        else:
            errors = []
            for url in pick_pdf_url(best):
                if not probe_pdf(url):
                    errors.append("不是有效 PDF：%s" % url)
                    continue
                try:
                    size = download_pdf(url, dest)
                    result["pdf"] = {"url": url, "path": dest,
                                     "bytes": size, "cached": False}
                    break
                except Exception as e:
                    errors.append(str(e))
            if result["pdf"] is None:
                result["pdf_error"] = errors
                result["needs_confirmation"] = True
        result["paper_dir"] = folder
        result["slug"] = slug
        # 顺手落一份 meta.json，后续归档（zotero_archive.py）直接读它
        try:
            with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return 0 if (result.get("pdf") or args.no_download) else 3


if __name__ == "__main__":
    sys.exit(main())
