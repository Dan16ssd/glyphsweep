"""GlyphSweep release gate: run a sweep, fail the job if the page isn't script-ready.

Used by the GitHub Action in action.yml; also works anywhere with Python 3 (no dependencies):
    GS_URL=https://staging.example.la/ GS_SCRIPT=lao GS_MIN=70 python3 ci/gate.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("GS_API", "https://45-77-254-54.sslip.io").rstrip("/")
URL = os.environ.get("GS_URL", "")
SCRIPT = os.environ.get("GS_SCRIPT", "lao")
MIN = int(os.environ.get("GS_MIN", "70"))
DEMO = os.environ.get("GS_DEMO", "false").lower() in ("1", "true", "yes")
TIMEOUT = float(os.environ.get("GS_TIMEOUT", "15")) * 60


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, headers={"Content-Type": "application/json",
                                 "User-Agent": "glyphsweep-gate/1.0"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def out(**kw):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in kw.items():
                f.write(f"{k}={v}\n")


def summary(md):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    print(md)


def main():
    if not DEMO and not URL:
        sys.exit("GlyphSweep: set `url` (or demo: true).")
    try:
        jid = call("POST", "/api/jobs", {"url": URL, "script": SCRIPT, "demo": DEMO})["id"]
    except urllib.error.HTTPError as e:
        sys.exit(f"GlyphSweep: could not start a sweep: HTTP {e.code} {e.read().decode()[:200]}")
    report, badge = f"{API}/#{jid}", f"{API}/api/jobs/{jid}/badge.svg"
    out(report=report, badge=badge)
    print(f"GlyphSweep sweep {jid} started: {report}", flush=True)

    t0, seen, job = time.time(), 0, {}
    while time.time() - t0 < TIMEOUT:
        try:
            job = call("GET", f"/api/jobs/{jid}")
        except Exception as e:  # noqa: BLE001  transient network errors: keep polling
            print(f"  (poll error {e})", flush=True)
            time.sleep(5)
            continue
        for e in job.get("events", [])[seen:]:
            print(f"  [{e['step']}] {e['msg']}", flush=True)
        seen = len(job.get("events", []))
        if job.get("status") in ("done", "error"):
            break
        time.sleep(5)
    else:
        sys.exit(f"GlyphSweep: timed out after {TIMEOUT / 60:.0f} min ({report})")

    if job["status"] == "error":
        summary(f"### ❌ GlyphSweep: no verdict\n{job.get('error', 'unknown error')}\n\n[Report]({report})")
        sys.exit(1)

    sc = job.get("score") or {}
    before, after = sc.get("before"), sc.get("after")
    out(before=before, after=after)
    issues = job.get("before") or []
    fixed = sum(1 for f in issues if f.get("fixed"))
    ocr = job.get("ocr_proof") or {}
    ocr_line = (f"| Bare-phone OCR error | {ocr['cer_before'] * 100:.0f}% | {ocr['cer_after'] * 100:.0f}% |\n"
                if ocr.get("cer_after") is not None else "")
    passed = before is not None and before >= MIN
    sandboxes = len(job.get("containment") or [])
    summary(
        f"### {'✅' if passed else '❌'} GlyphSweep {SCRIPT} readiness: {before}/100 (gate: {MIN})\n\n"
        f"![GlyphSweep]({badge})\n\n"
        f"| | Now | With proven patch |\n|---|---|---|\n| Script readiness | {before} | {after} |\n{ocr_line}"
        f"\n{len(issues)} issue(s) found, {fixed} proven fixable by CSS. "
        f"{sandboxes} disposable gVisor sandboxes were used and destroyed.\n\n"
        f"**The patch is locked until a human approves it:** [review before/after and approve]({report})\n"
    )
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
