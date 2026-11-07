"""List .la hostnames seen by Common Crawl (an unbiased-ish sample of the public Lao web).

    python research/cc_domains.py --crawl CC-MAIN-2026-43 --out research/cc_hosts.txt
Then feed them to discover.py as seeds (it keeps only sites whose homepage is in Lao).
"""

import argparse
import json
import time
import urllib.request
from urllib.parse import urlparse

API = "https://index.commoncrawl.org/{crawl}-index?url=*.la&output=json&fl=url,status,mime&page={page}"


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "GlyphSweep research"}),
                                        timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print("  retry", i + 1, str(e)[:80], flush=True)
            time.sleep(5 * (i + 1))
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", nargs="+", default=["CC-MAIN-2026-43"])
    ap.add_argument("--out", default="research/cc_hosts.txt")
    a = ap.parse_args()
    hosts = {}
    for crawl in a.crawl:
      try:
        pages = json.loads(get(API.format(crawl=crawl, page=0) + "&showNumPages=true"))["pages"]
      except ValueError:
        print("skip", crawl); continue
      for p in range(pages):
        body = get(API.format(crawl=crawl, page=p))
        for line in body.splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("status") != "200" or "html" not in (rec.get("mime") or ""):
                continue
            h = (urlparse(rec["url"]).hostname or "").lower()
            if h.startswith("www."):
                h = h[4:]
            if h.endswith(".la"):
                hosts[h] = hosts.get(h, 0) + 1
        print(f"page {p + 1}/{pages}: {len(hosts)} hosts", flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for h, n in sorted(hosts.items(), key=lambda kv: -kv[1]):
            f.write(f"{h}\n")
    print(f"{len(hosts)} hosts -> {a.out}")


if __name__ == "__main__":
    main()
