"""Record the human-approval moment of a real demo run (for the pitch video).

Starts a Thai demo sweep through the API, waits for it to finish (unrecorded), then records a short
clip: the job waiting for approval, a person clicking Approve, the timeline logging it and the patch
becoming downloadable. Same docker invocation as record_demo.py.
"""
import json
import os
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = os.environ.get("GS_URL", "https://45-77-254-54.sslip.io/").rstrip("/")
OUT = "/out"
W, H = 1600, 900


def api(path, body=None):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


jid = api("/api/jobs", {"url": "", "script": "thai", "demo": True})["id"]
print("job", jid, flush=True)
while True:
    j = api(f"/api/jobs/{jid}")
    if j["status"] in ("done", "error"):
        break
    time.sleep(3)
print("status", j["status"], j.get("approval"), flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=OUT, record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    page.goto(f"{URL}/#{jid}", wait_until="networkidle")
    page.wait_for_selector("#approveBox", timeout=30000)
    page.evaluate("window.scrollTo(0, document.querySelector('#app').getBoundingClientRect().top + scrollY - 20)")
    page.wait_for_timeout(500)
    # show the end of the agent timeline (the 'waiting for approval' event)
    page.evaluate("const e = document.querySelector('#events'); if (e) e.scrollTop = e.scrollHeight")
    page.wait_for_timeout(4500)
    page.screenshot(path=f"{OUT}/ap-pending.png")
    btn = page.locator("#approveBox button.ok")
    box = btn.bounding_box()
    page.mouse.move(box["x"] - 200, box["y"] + 120)
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)
    page.wait_for_timeout(900)
    btn.click()
    page.wait_for_selector(".approved", timeout=15000)
    page.wait_for_timeout(600)
    page.evaluate("const e = document.querySelector('#events'); if (e) e.scrollTop = e.scrollHeight")
    page.wait_for_timeout(4000)
    page.screenshot(path=f"{OUT}/ap-approved.png")
    page.locator('a.dl[href$="patch.css"]').hover()
    page.wait_for_timeout(2500)
    ctx.close()
    b.close()
print("ok", flush=True)
