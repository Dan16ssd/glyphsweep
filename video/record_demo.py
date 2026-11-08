"""Record a real run of the live hostile demo (Thai) for the pitch video.

Runs on the VM inside the sandbox image (it already has Playwright + Chromium + Noto fonts):
    docker run --rm -v /root/rec:/out -e GS_URL=https://45-77-254-54.sslip.io/ \
        glyphsweep-sandbox:latest python /out/record_demo.py
Writes /out/*.webm (the screen recording), /out/marks.json (seconds since recording start for
each moment) and /out/shot-*.png stills.
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("GS_URL", "https://45-77-254-54.sslip.io/")
SCRIPT = os.environ.get("GS_SCRIPT", "thai")
OUT = "/out"
W, H = 1600, 900
marks = {}
T0 = None


def mark(name):
    marks[name] = round(time.time() - T0, 2)
    print(f"{marks[name]:7.1f}s  {name}", flush=True)


def smooth(page, y, ms=1200):
    page.evaluate(
        """([y, ms]) => new Promise(r => { const s = scrollY, t0 = performance.now();
        const f = t => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2*k*k : 1 - (-2*k + 2)**2 / 2;
        scrollTo(0, s + (y - s) * e); k < 1 ? requestAnimationFrame(f) : r(); }; requestAnimationFrame(f); })""",
        [y, ms])


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=OUT,
                        record_video_size={"width": W, "height": H}, ignore_https_errors=True)
    page = ctx.new_page()
    T0 = time.time()
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(1500)
    mark("home")
    page.screenshot(path=f"{OUT}/shot-home.png")
    page.wait_for_timeout(5000)
    y = page.evaluate("document.querySelector('#evidence').getBoundingClientRect().top + scrollY - 40")
    smooth(page, y, 1600)
    mark("stats")
    page.wait_for_timeout(5000)
    page.screenshot(path=f"{OUT}/shot-stats.png")
    smooth(page, 0, 1200)
    page.wait_for_timeout(1000)
    page.select_option("#script", SCRIPT)
    page.wait_for_timeout(800)
    page.click("#demo")
    mark("demo_click")
    seen = 0
    done = False
    deadline = time.time() + 600
    while time.time() < deadline:
        n = page.evaluate("document.querySelectorAll('#events .ev').length")
        if n != seen:
            steps = page.evaluate("[...document.querySelectorAll('#events .step')].map(e => e.textContent)")
            for i in range(seen, len(steps)):
                mark(f"ev{i:02d}:{steps[i]}")
            seen = n
        if page.evaluate("!document.querySelector('#events .dot.running') && document.querySelectorAll('#events .ev').length > 2"):
            done = True
            break
        page.wait_for_timeout(500)
    mark("done" if done else "timeout")
    page.wait_for_timeout(1500)
    y = page.evaluate("document.querySelector('#app').getBoundingClientRect().top + scrollY - 20")
    smooth(page, y, 900)
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/shot-done.png")
    for t in ["contain", "findings", "device", "shots", "patch"]:
        page.click(f'#tabs button[data-t="{t}"]')
        page.wait_for_timeout(600)
        mark(f"tab_{t}")
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT}/shot-{t}.png")
        # scroll through the tab content slowly
        top = page.evaluate("document.querySelector('#view').getBoundingClientRect().top + scrollY - 20")
        bottom = page.evaluate("document.querySelector('#view').getBoundingClientRect().bottom + scrollY")
        smooth(page, top, 900)
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT}/shot-{t}-top.png")
        if bottom - top > H:
            smooth(page, bottom - H + 40, 4000)
            page.wait_for_timeout(2500)
            page.screenshot(path=f"{OUT}/shot-{t}-bottom.png")
        mark(f"tab_{t}_end")
        smooth(page, y, 900)
        page.wait_for_timeout(500)
    # final timeline
    page.wait_for_timeout(1000)
    mark("end")
    ev = page.evaluate("[...document.querySelectorAll('#events .ev')].map(e => e.innerText)")
    sc = page.evaluate("document.querySelector('#scorecard') && document.querySelector('#scorecard').innerText")
    json.dump({"marks": marks, "events": ev, "scorecard": sc}, open(f"{OUT}/marks.json", "w"), ensure_ascii=False, indent=1)
    ctx.close()
    b.close()
print("ok")
