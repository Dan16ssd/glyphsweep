"""Batch-scan many websites with the GlyphSweep detectors (research / measurement mode).

For each site in sites.csv: render the homepage in Chromium at a desktop AND a phone
viewport, run sandbox/checks.js, save a screenshot for manual verification, and append
one JSON line to the results file. Resumable: sites already in the results file are skipped.

This mode only *reads* public homepages, like a normal visitor. It does not patch,
submit forms or follow logins. Run it on your own machine:

    python research/scan.py --sites research/sites.csv --out research/results/scan.jsonl --workers 3
"""

import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time
import traceback
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHECKS_JS = open(os.path.join(REPO, "sandbox", "checks.js"), encoding="utf-8").read()
SEV = {"high": 8, "medium": 4, "low": 1}
VIEWPORTS = {"desktop": {"width": 1280, "height": 900}, "phone": {"width": 390, "height": 844}}
SCRIPT_RE = {"lao": re.compile(r"[຀-໿]"), "thai": re.compile(r"[฀-๿]"),
             "khmer": re.compile(r"[ក-៿]"), "myanmar": re.compile(r"[က-႟]")}
# Two fonts that both draw the script but have different metrics. Inside the sandbox image these are the
# Noto Sans / Noto Serif pair (same as the live agent); override with GS_SENTINELS="A,B" elsewhere.
NOTO = {"lao": "Lao", "thai": "Thai", "khmer": "Khmer", "myanmar": "Myanmar"}
def sentinels(script):
    env = os.environ.get("GS_SENTINELS")
    return env.split(",") if env else [f"Noto Sans {NOTO[script]}", f"Noto Serif {NOTO[script]}"]


def score(findings):
    """Research score: each problem *type* counts once (at its worst severity), so a long page
    isn't punished just for having more elements. 100 = no problems."""
    worst = {}
    for f in findings:
        worst[f["check"]] = max(worst.get(f["check"], 0), SEV.get(f["severity"], 1))
    return round(100 * math.exp(-sum(worst.values()) / 40))


def slim(f):
    return {k: f.get(k) for k in ("check", "severity", "selector", "text", "bbox", "detail", "verified")}


def verify_clips(page, findings, shots_dir, stem, max_checks=10, pad=14, min_px=25):
    """Ground truth for text_clipped: screenshot the element's area, switch its overflow to visible,
    screenshot again. If pixels change, content really was hidden (verified=True, evidence saved).
    If nothing changes, the detector's estimate was wrong (verified=False)."""
    from PIL import Image, ImageChops
    import io
    n = 0
    for f in findings:
        if f["check"] != "text_clipped":
            continue
        if n >= max_checks:
            f["verified"] = None
            continue
        n += 1
        try:
            h = page.query_selector(f["selector"])
            if not h:
                f["verified"] = None
                continue
            h.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(150)
            box = h.bounding_box()
            vp = page.viewport_size
            if not box or box["width"] < 2 or box["height"] < 2:
                f["verified"] = None
                continue
            x0, y0 = max(0, box["x"] - pad), max(0, box["y"] - pad)
            x1, y1 = min(vp["width"], box["x"] + box["width"] + pad), min(vp["height"], box["y"] + box["height"] + pad)
            clip = {"x": x0, "y": y0, "width": max(1, x1 - x0), "height": max(1, y1 - y0)}
            before = page.screenshot(clip=clip, animations="disabled")
            page.wait_for_timeout(250)
            again = page.screenshot(clip=clip, animations="disabled")
            if before != again:
                da = ImageChops.difference(Image.open(io.BytesIO(before)).convert("L"), Image.open(io.BytesIO(again)).convert("L"))
                if sum(1 for p in da.point(lambda p: 255 if p > 40 else 0).getdata() if p) >= min_px:
                    f["verified"] = None  # region is animating (carousel/ticker); can't judge
                    f["verify_error"] = "animated region"
                    continue
            h.evaluate("e => { e.dataset.gsOv = e.getAttribute('style') || ''; "
                       "e.style.setProperty('overflow', 'visible', 'important'); }")
            page.wait_for_timeout(120)
            after = page.screenshot(clip=clip, animations="disabled")
            h.evaluate("e => e.setAttribute('style', e.dataset.gsOv)")
            a, b = Image.open(io.BytesIO(before)).convert("L"), Image.open(io.BytesIO(after)).convert("L")
            diff = ImageChops.difference(a, b).point(lambda p: 255 if p > 40 else 0)
            changed = sum(1 for p in diff.getdata() if p)
            f["verify_px"] = changed
            f["verified"] = changed >= min_px
            if f["verified"]:
                base = os.path.join(shots_dir, "clips", f"{stem}.{n}")
                os.makedirs(os.path.dirname(base), exist_ok=True)
                open(base + ".clipped.png", "wb").write(before)
                open(base + ".full.png", "wb").write(after)
                f["evidence"] = os.path.relpath(base, HERE).replace("\\", "/")
        except Exception as e:  # noqa: BLE001
            f["verified"] = None
            f["verify_error"] = str(e)[:120]


def scan_site(browser, row, shots_dir, script):
    host = row.get("host") or urlparse(row["url"]).hostname
    rec = {"url": row["url"], "host": host, "script": script, "category": row.get("category", ""), "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "views": {}}
    for vname, vp in VIEWPORTS.items():
        ctx = browser.new_context(viewport=vp, ignore_https_errors=True, service_workers="block", accept_downloads=False,
                                  is_mobile=(vname == "phone"), has_touch=(vname == "phone"),
                                  )  # default browser locale: measure what sites serve by default
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())
        page.on("popup", lambda p: p.close())
        t0 = time.time()
        v = {"status": None, "error": None}
        try:
            resp = page.goto(row["url"], wait_until="domcontentloaded", timeout=30000)
            v["status"] = resp.status if resp else None
            v["final_url"] = page.url
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(800)
            res = page.evaluate(CHECKS_JS, {"script": script, "sentinels": sentinels(script)})
            text = res.get("pageText", "")
            v.update({
                "title": res.get("title"),
                "html_lang": res.get("htmlLang"),
                "script_share": res.get("scriptShare"),
                "script_chars": len(SCRIPT_RE[script].findall(text)),
                "target_elements": res.get("targetElements"),
                "fonts": res.get("fonts"),
                "page_height": res.get("pageHeight"),
                "findings": [slim(f) for f in res.get("findings", [])],
            })
            os.makedirs(shots_dir, exist_ok=True)
            verify_clips(page, v["findings"], shots_dir, f"{re.sub(r'[^a-z0-9.-]', '_', host)}.{vname}")
            # unverified clip suspicions don't count toward the score
            v["score"] = score([f for f in v["findings"] if f["check"] != "text_clipped" or f.get("verified")])
            fn = os.path.join(shots_dir, f"{re.sub(r'[^a-z0-9.-]', '_', host)}.{vname}.jpg")
            page.screenshot(path=fn, type="jpeg", quality=60, full_page=False)
            v["screenshot"] = os.path.relpath(fn, HERE).replace("\\", "/")
        except Exception as e:  # noqa: BLE001
            v["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        finally:
            v["ms"] = int((time.time() - t0) * 1000)
            ctx.close()
        rec["views"][vname] = v
    return rec


def worker(rows, out_path, shots_dir, script, lock, wid):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-first-run"])
        for i, row in enumerate(rows):
            try:
                rec = scan_site(browser, row, shots_dir, script)
            except Exception:  # noqa: BLE001
                rec = {"url": row["url"], "host": row.get("host"), "category": row.get("category"),
                       "fatal": traceback.format_exc()[-500:]}
                try:  # browser may have died; restart it
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass
                browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-first-run"])
            with lock:
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            d = rec.get("views", {}).get("desktop", {})
            ph = rec.get("views", {}).get("phone", {})
            print(f"[w{wid} {i + 1}/{len(rows)}] {rec['host']:35} desktop={d.get('score', 'ERR')!s:>4} "
                  f"phone={ph.get('score', 'ERR')!s:>4}  {(d.get('error') or '')[:60]}", flush=True)
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=os.path.join(HERE, "sites.csv"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "scan.jsonl"))
    ap.add_argument("--shots", default=os.path.join(HERE, "results", "shots"))
    ap.add_argument("--script", default="lao", choices=["lao", "thai", "khmer", "myanmar"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.sites, encoding="utf-8")))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    done = set()
    if os.path.exists(a.out):
        for line in open(a.out, encoding="utf-8"):
            try:
                done.add(json.loads(line)["url"])
            except (ValueError, KeyError):
                pass
    todo = [r for r in rows if r["url"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(rows)} sites, {len(done)} already scanned, {len(todo)} to go, {a.workers} workers", file=sys.stderr)
    if not todo:
        return
    lock = mp.Lock()
    n = max(1, min(a.workers, len(todo)))
    procs = [mp.Process(target=worker, args=(todo[i::n], a.out, a.shots, a.script, lock, i)) for i in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
