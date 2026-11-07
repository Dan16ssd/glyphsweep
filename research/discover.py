"""Discover Lao-language websites by crawling outward from a seed list.

Fast and polite: plain HTTP GET of each site's homepage only (no browser), a few
threads, one request per domain. A site is kept if its homepage HTML contains a
meaningful amount of Lao script. Outbound links to new domains are queued.

    python research/discover.py --seeds research/seeds.txt --out research/sites.csv --limit 500
"""

import argparse
import concurrent.futures as cf
import csv
import re
import ssl
import sys
import urllib.request
from collections import deque
from html import unescape
from urllib.parse import urljoin, urlparse

LAO = re.compile(r"[຀-໿]")
HREF = re.compile(r"""href\s*=\s*["']([^"'#>]+)""", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
UA = "Mozilla/5.0 (GlyphSweep research crawler; Lao web rendering study)"
SKIP = ("facebook.", "fb.com", "google.", "youtube.", "youtu.be", "twitter.", "x.com", "instagram.", "tiktok.",
        "linkedin.", "wa.me", "whatsapp.", "t.me", "line.me", "apple.com", "microsoft.", "wikipedia.", "gstatic.",
        "googleapis.", "doubleclick.", "w3.org", "wordpress.org", "jquery", "cloudflare", "bootstrapcdn")
# internal systems, not public websites (webmail, meetings, document systems, logins, LMS, ...)
APP_LABELS = {"mail", "email", "webmail", "meet", "drive", "edoc", "idoc", "lms", "login", "booking", "cpanel", "admin",
              "vpn", "owa", "ftp", "sso", "erp", "hr", "hrm", "dms", "cloud", "zoom", "elearning", "moodle", "ebook",
              "api", "app", "apps", "portal-admin", "intranet", "office", "doc", "docs", "file", "files", "jira", "git"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE  # many Lao sites have broken/expired certs; we only read public HTML


def category(host, title):
    h, t = host.lower(), (title or "").lower()
    if h.endswith(".gov.la") or ".gov." in h or "ກະຊວງ" in t or "ກົມ" in t:
        return "government"
    if h.endswith(".edu.la") or "university" in t or "ມະຫາວິທະຍາໄລ" in t or "ວິທະຍາໄລ" in t or "ໂຮງຮຽນ" in t:
        return "education"
    if "bank" in h or "bank" in t or "ທະນາຄານ" in t:
        return "bank"
    if any(k in h for k in ("news", "times", "post", "press", "tv", "radio", "kpl", "pasaxon")) or any(
            k in t for k in ("ຂ່າວ", "news", "ໜັງສືພິມ")):
        return "news"
    if any(k in h for k in ("laotel", "unitel", "etl", "tplus", "telecom")):
        return "telecom"
    return "business/other"


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # no Lao preference: measure default content
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        final = r.geturl()
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype:
            return final, ""
        raw = r.read(1_500_000)
        enc = r.headers.get_content_charset() or "utf-8"
        return final, raw.decode(enc, "replace")


def probe(host, min_lao=200):
    for scheme in ("https", "http"):
        try:
            final, html = fetch(f"{scheme}://{host}/")
        except Exception:  # noqa: BLE001
            continue
        lao = len(LAO.findall(html))
        tm = TITLE.search(html)
        if lao < min_lao:  # not a Lao site: don't spend time on its inner pages
            return {"host": host, "url": final, "lao_chars": lao, "title": "", "links": set()}
        title = re.sub(r"\s+", " ", unescape(tm.group(1))).strip()[:120] if tm else ""
        out = set()
        for href in HREF.findall(html):
            u = urlparse(urljoin(final, href.strip()))
            if u.scheme in ("http", "https") and u.hostname:
                out.add(u.hostname.lower())
        # inner pages most likely to list other organisations (links / partners / about / contact)
        inner = []
        for href in HREF.findall(html):
            u = urlparse(urljoin(final, href.strip()))
            if u.hostname and norm(u.hostname) == norm(urlparse(final).hostname or "") and u.path not in ("", "/"):
                score = sum(k in (u.path + u.query).lower() for k in ("link", "partner", "about", "contact", "network",
                                                                        "relat", "member", "org", "ministr", "depart"))
                inner.append((-score, u.geturl()))
        for _, iu in sorted(set(inner))[:3]:
            try:
                _, ih = fetch(iu, timeout=10)
            except Exception:  # noqa: BLE001
                continue
            for href in HREF.findall(ih):
                v = urlparse(urljoin(iu, href.strip()))
                if v.scheme in ("http", "https") and v.hostname:
                    out.add(v.hostname.lower())
        return {"host": host, "url": final, "lao_chars": lao, "title": title, "links": out}
    return None


def norm(host):
    host = host.lower().strip().strip(".")
    return host[4:] if host.startswith("www.") else host


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", default=["research/seeds.txt"])
    ap.add_argument("--out", default="research/sites.csv")
    ap.add_argument("--limit", type=int, default=500, help="stop after this many Lao sites")
    ap.add_argument("--max-probes", type=int, default=3000)
    ap.add_argument("--min-lao", type=int, default=200, help="min Lao characters in homepage HTML")
    ap.add_argument("--threads", type=int, default=12)
    a = ap.parse_args()

    seeds = list(dict.fromkeys(norm(l.split("#")[0]) for path in a.seeds for l in open(path, encoding="utf-8")
                               if l.split("#")[0].strip()))
    queue, seen = deque(seeds), set()
    kept, probes = [], 0
    with cf.ThreadPoolExecutor(a.threads) as ex:
        while queue and len(kept) < a.limit and probes < a.max_probes:
            batch = []
            while queue and len(batch) < a.threads * 2:
                h = queue.popleft()
                if h in seen or any(s in h for s in SKIP) or h.split(".")[0] in APP_LABELS:
                    continue
                seen.add(h)
                batch.append(h)
            probes += len(batch)
            for r in ex.map(lambda h: probe(h, a.min_lao), batch):
                if not r:
                    continue
                if r["lao_chars"] >= a.min_lao:
                    r["category"] = category(r["host"], r["title"])
                    kept.append(r)
                    print(f"[{len(kept):4}] {r['category']:14} {r['lao_chars']:6}  {r['host']}  {r['title'][:50]}",
                          flush=True)
                    for h in r["links"]:
                        h = norm(h)
                        # follow .la domains and anything linked from a Lao site (filtered by Lao content later)
                        if h not in seen and (h.endswith(".la") or len(queue) < 4000):
                            (queue.appendleft if h.endswith(".la") else queue.append)(h)
    kept = kept[: a.limit]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "host", "category", "lao_chars", "title"])
        for r in sorted(kept, key=lambda r: (r["category"], r["host"])):
            w.writerow([r["url"], r["host"], r["category"], r["lao_chars"], r["title"]])
    print(f"\n{len(kept)} Lao sites from {probes} probes -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
