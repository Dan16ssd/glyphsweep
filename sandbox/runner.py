"""GlyphSweep sandbox runner.

Runs INSIDE the disposable sandbox container. It receives a job spec (pages, script,
optional CSS patch), drives Chromium through the per-job egress proxy, runs the
deterministic detectors in checks.js, renders a "bare device" profile with no
system fonts for the target script, OCRs both renders, and prints one JSON result.

The sandbox holds no API keys. It never talks to the model; the control plane does.
"""

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS_JS = open(os.path.join(HERE, "checks.js"), encoding="utf-8").read()
OCR_LANG = {"lao": "lao", "thai": "tha", "khmer": "khm", "myanmar": "mya"}
BARE_FONTCONFIG = os.environ.get("GS_BARE_FONTCONFIG", "/opt/glyphsweep/bare-fonts.conf")
RESULT_MARK = "GLYPHSWEEP_RESULT "


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def cer(ref: str, hyp: str) -> float:
    ref = "".join(ref.split())
    hyp = "".join(hyp.split())
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i]
        for j, hc in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return round(min(1.0, prev[-1] / len(ref)), 3)


def ocr_blocks(png: bytes, blocks, script):
    if not shutil.which("tesseract") or not blocks:
        return []
    img = Image.open(io.BytesIO(png)).convert("L")
    out = []
    for b in blocks:
        x, y, w, h = b["bbox"]["x"], b["bbox"]["y"], b["bbox"]["w"], b["bbox"]["h"]
        if w < 8 or h < 8 or y + h > img.height:
            continue
        pad = 6
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(img.width, x + w + pad), min(img.height, y + h + pad)
        if x1 - x0 < 8 or y1 - y0 < 8:  # off-screen (carousel slides, hidden menus): nothing to read
            continue
        crop = img.crop((x0, y0, x1, y1))
        crop = crop.resize((crop.width * 2, crop.height * 2))
        buf = io.BytesIO()
        crop.save(buf, "PNG")
        try:
            r = subprocess.run(
                ["tesseract", "stdin", "stdout", "-l", OCR_LANG[script], "--psm", "6"],
                input=buf.getvalue(), capture_output=True, timeout=30,
            )
            text = r.stdout.decode("utf-8", "replace").strip()
        except Exception as e:  # noqa: BLE001
            text = f"<ocr error {e}>"
        out.append({"dom": b["text"][:200], "ocr": text[:200], "cer": cer(b["text"], text), "bbox": b["bbox"]})
    return out


def shot(page, max_h):
    png = page.screenshot(full_page=True, type="png")
    img = Image.open(io.BytesIO(png))
    if img.height > max_h:
        img = img.crop((0, 0, img.width, max_h))
        b = io.BytesIO()
        img.save(b, "PNG")
        png = b.getvalue()
    jb = io.BytesIO()
    img.convert("RGB").save(jb, "JPEG", quality=72)
    return png, base64.b64encode(jb.getvalue()).decode(), img.width, img.height


def launch(p, spec, env=None):
    kw = {"headless": True, "args": ["--disable-dev-shm-usage", "--no-first-run", "--proxy-bypass-list=<-loopback>"]}
    if spec.get("proxy"):
        kw["proxy"] = {"server": spec["proxy"]}
    if env:
        kw["env"] = env
    if spec.get("no_chromium_sandbox", True):
        kw["chromium_sandbox"] = False
    return p.chromium.launch(**kw)


def new_page(browser, spec, net):
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        ignore_https_errors=True,
        service_workers="block",
        accept_downloads=False,
    )
    page = ctx.new_page()
    page.on("dialog", lambda d: d.dismiss())
    page.on("popup", lambda pp: (net["popups"].append(pp.url), pp.close()))

    def on_req(r):
        host = urlparse(r.url).hostname or r.url[:40]
        net["requests"][host] = net["requests"].get(host, 0) + 1

    def on_fail(r):
        net["failed"].append({"url": r.url[:200], "error": (r.failure or "")[:120]})

    page.on("request", on_req)
    page.on("requestfailed", on_fail)
    return ctx, page


def run_page(browser, url, spec, net, with_shot=True):
    ctx, page = new_page(browser, spec, net)
    t0 = time.time()
    status = None
    err = None
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
        status = resp.status if resp else None
        try:
            page.wait_for_load_state("networkidle", timeout=4000)  # sites with analytics never go idle
        except Exception:  # noqa: BLE001
            pass
        if spec.get("css_patch"):
            page.add_style_tag(content=spec["css_patch"])
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(400)
        res = page.evaluate(CHECKS_JS, {"script": spec["script"], "sentinels": spec.get("sentinels")})
        if with_shot:
            png, jpg, w, h = shot(page, spec.get("max_height", 3200))
            res["screenshot"] = {"jpeg_b64": jpg, "width": w, "height": h}
            try:
                res["ocr"] = ocr_blocks(png, res.get("ocrBlocks"), spec["script"])
            except Exception as oe:  # noqa: BLE001  OCR is evidence, never a reason to lose the audit
                res["ocr"], res["ocr_error"] = [], str(oe)[:200]
    except Exception as e:  # noqa: BLE001
        err = str(e)[:400]
        res = {"findings": [], "links": []}
    finally:
        ctx.close()
    res.update({"url": url, "status": status, "error": err, "ms": int((time.time() - t0) * 1000)})
    return res


def self_probe():
    """Attack our own sandbox from the inside and record what happens (shown in the UI)."""
    import socket
    res = []

    def tcp(host, port):
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.close()
            return "OPEN (!)"
        except Exception as e:  # noqa: BLE001
            return f"blocked: {type(e).__name__}: {str(e)[:60]}"

    res.append({"probe": "direct TCP to Vultr metadata 169.254.169.254:80 (bypassing proxy)", "result": tcp("169.254.169.254", 80)})
    res.append({"probe": "direct TCP to internet 1.1.1.1:443 (bypassing proxy)", "result": tcp("1.1.1.1", 443)})
    for path in ("/var/run/docker.sock", "/run/docker.sock"):
        res.append({"probe": f"open {path}", "result": "EXISTS (!)" if os.path.exists(path) else "blocked: not present"})
    for path in ("/etc/glyphsweep-probe", "/opt/glyphsweep/probe", "/usr/bin/probe"):
        try:
            with open(path, "w") as f:
                f.write("x")
            res.append({"probe": f"write {path}", "result": "WRITABLE (!)"})
        except Exception as e:  # noqa: BLE001
            res.append({"probe": f"write {path}", "result": f"blocked: {type(e).__name__}"})
    secrets = sorted(k for k in os.environ if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD", "VULTR")))
    res.append({"probe": "secret-looking env vars", "result": f"{len(secrets)} found" + (f" (!) {secrets}" if secrets else "")})
    res.append({"probe": "running as", "result": f"uid {os.getuid() if hasattr(os, 'getuid') else '?'}"})
    return res


def main():
    spec = json.loads(base64.b64decode(os.environ["JOB_SPEC"]).decode())
    net = {"requests": {}, "failed": [], "popups": []}
    out = {"pages": [], "bare": None, "net": net, "env": {
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "secrets_in_env": sorted(k for k in os.environ if any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET", "PASSWORD"))),
        "hostname": os.environ.get("HOSTNAME"),
    }}
    out["probe"] = self_probe()
    with sync_playwright() as p:
        browser = launch(p, spec)
        for url in spec["pages"][: spec.get("max_pages", 4)]:
            log("page", url)
            out["pages"].append(run_page(browser, url, spec, net))
        browser.close()

        # "Bare device" render: same first page, but no system font for the script.
        if spec.get("bare_profile", True) and spec["pages"] and os.path.exists(BARE_FONTCONFIG):
            env = dict(os.environ, FONTCONFIG_FILE=BARE_FONTCONFIG)
            env.pop("JOB_SPEC", None)
            b2 = launch(p, spec, env=env)
            bare_spec = dict(spec, sentinels=None)
            r = run_page(b2, spec["pages"][0], bare_spec, net)
            out["bare"] = {k: r.get(k) for k in ("url", "screenshot", "ocr", "error")}
            b2.close()

    print(RESULT_MARK + json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
