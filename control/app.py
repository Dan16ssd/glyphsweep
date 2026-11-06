"""GlyphSweep control plane (FastAPI).

Plans a localization QA job, dispatches every stage into a disposable sandbox,
verifies findings with a vision model, asks the model for a CSS fix, then proves
the fix by re-measuring in a fresh sandbox. Keys and the Docker socket live here;
the sandboxes get neither.
"""

import base64
import ipaddress
import json
import os
import re
import threading
import time
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import llm
import sandbox

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("GS_DATA", "/data/jobs"))
DATA.mkdir(parents=True, exist_ok=True)
DEMO_HOST = os.environ.get("GS_DEMO_HOST", "glyphsweep-demo")
DEMO_URL = f"http://{DEMO_HOST}:8000/demo/shop.html"
MAX_PAGES = int(os.environ.get("GS_MAX_PAGES", "3"))
SEM = threading.BoundedSemaphore(int(os.environ.get("GS_CONCURRENCY", "2")))

app = FastAPI(title="GlyphSweep")
JOBS: dict = {}
LOCK = threading.Lock()

SEV = {"high": 8, "medium": 4, "low": 1}
INJECTION_RE = re.compile(r"(ignore (all|any|previous|prior)|system prompt|you are an ai|api[ _-]?key|report (no|zero) issues|disregard)", re.I)


class JobIn(BaseModel):
    url: str
    script: str = "lao"
    demo: bool = False


def event(job, step, status, msg, **extra):
    with LOCK:
        job["events"].append({"t": round(time.time(), 2), "step": step, "status": status, "msg": msg, **extra})


def validate_url(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HTTPException(400, "URL must be http(s)://host/...")
    try:
        ip = ipaddress.ip_address(u.hostname)
        if not ip.is_global:
            raise HTTPException(400, "Private / internal addresses are not allowed")
    except ValueError:
        pass
    if u.hostname.lower() in ("localhost",) or u.hostname.endswith((".internal", ".local")):
        raise HTTPException(400, "Internal hostnames are not allowed")
    return u.hostname.lower()


def score(findings):
    """0-100 readiness: 100 = no issues; decays smoothly with weighted severity."""
    import math
    return round(100 * math.exp(-sum(SEV.get(f["severity"], 1) for f in findings) / 80))


def save_shot(job_id, name, shot):
    if not shot:
        return None
    p = DATA / job_id / f"{name}.jpg"
    p.write_bytes(base64.b64decode(shot["jpeg_b64"]))
    return {"src": f"/api/jobs/{job_id}/img/{name}.jpg", "width": shot["width"], "height": shot["height"]}


def collect(job_id, stage, result):
    """Strip screenshots out of the sandbox result into files, tag findings by page."""
    pages = []
    for i, pg in enumerate(result.get("pages", [])):
        img = save_shot(job_id, f"{stage}_{i}", pg.pop("screenshot", None))
        for f in pg.get("findings", []):
            f["page"] = pg["url"]
            f["key"] = f"{pg['url']}|{f['check']}|{f['selector']}"
        pg["image"] = img
        pages.append(pg)
    bare = result.get("bare")
    if bare:
        bare["image"] = save_shot(job_id, f"{stage}_bare", bare.pop("screenshot", None))
    return pages, bare


def injection_findings(pages):
    out = []
    for pg in pages:
        for f in pg.get("findings", []):
            s = f.get("text", "") + " " + json.dumps(f.get("detail", {}), ensure_ascii=False)
            if INJECTION_RE.search(s):
                out.append({"page": pg["url"], "text": f.get("text", "")[:160], "selector": f["selector"]})
    return out


def run_job(job):
    jid, url, script = job["id"], job["url"], job["script"]
    host = job["host"]
    internal_ok = DEMO_HOST if job["demo"] else None
    with SEM:
        try:
            job["status"] = "running"
            event(job, "plan", "done", f"Target {host}; script {script}; egress allowlist = [{host}, Google Fonts]; "
                  f"model = {llm.MODEL if llm.enabled() else 'none (deterministic mode)'}")

            # 1. discovery sandbox
            event(job, "dispatch", "running", "Sandbox #1: render start page, run detectors")
            res, ev = sandbox.dispatch("discover", [url], script, host, internal_ok=internal_ok)
            job["containment"].append(ev)
            if not res:
                raise RuntimeError(f"sandbox produced no result (exit {ev.get('exit_code')}): {ev.get('stderr_tail', '')[-400:]}")
            pages, bare = collect(jid, "before", res)
            if pages and pages[0].get("error"):
                raise RuntimeError(f"Start page failed to load in the sandbox: {pages[0]['error'][:300]}")
            job["net"].append(res.get("net"))
            event(job, "dispatch", "done", f"Sandbox #1 destroyed={ev['destroyed']} · {len(pages[0].get('findings', []))} findings · "
                  f"{len(ev['egress']['denied'])} egress attempts blocked", run=ev["run_id"])

            # 2. planner picks more pages (only from links the sandbox actually saw)
            extra = []
            if llm.enabled() and MAX_PAGES > 1:
                try:
                    plan = llm.plan_pages(url, script, pages[0].get("links", []), MAX_PAGES - 1)
                    extra = plan["pages"]
                    job["model"]["plan"] = plan
                    event(job, "plan", "done", f"Planner chose {len(extra)} more page(s): {plan['reasoning']}"
                          + (f" (rejected {len(plan['rejected'])} URL(s) not seen by the sandbox)" if plan.get("rejected") else ""))
                except Exception as e:  # noqa: BLE001
                    event(job, "plan", "warn", f"Planner failed, auditing start page only: {e}")
            if extra:
                event(job, "dispatch", "running", f"Sandbox #2: audit {len(extra)} more page(s)")
                res2, ev2 = sandbox.dispatch("audit", extra, script, host, bare_profile=False, internal_ok=internal_ok)
                job["containment"].append(ev2)
                if res2:
                    p2, _ = collect(jid, "before_more", res2)
                    pages += p2
                    job["net"].append(res2.get("net"))
                event(job, "dispatch", "done", f"Sandbox #2 destroyed={ev2['destroyed']}", run=ev2["run_id"])

            before = [f for pg in pages for f in pg.get("findings", [])]
            job["pages"] = [{k: pg.get(k) for k in ("url", "title", "htmlLang", "scriptShare", "fonts", "image", "ocr", "status", "error")} for pg in pages]
            job["before"] = before
            job["bare_before"] = bare
            job["injections"] = injection_findings(pages)
            if job["injections"]:
                event(job, "verify", "warn", f"{len(job['injections'])} page string(s) look like prompt injection; passed to the model only as quoted data")

            # 3. vision verification
            if llm.enabled() and before:
                try:
                    p0 = pages[0]
                    img = (DATA / jid / "before_0.jpg").read_bytes()
                    v = llm.verify(script, [f for f in before if f["page"] == p0["url"]], img)
                    job["model"]["verify"] = v
                    vis = {x["id"]: x for x in v["verdicts"]}
                    for f in before:
                        if f["page"] == p0["url"] and f["id"] in vis:
                            f["vision"] = vis[f["id"]]
                    yes = sum(1 for x in v["verdicts"] if x["visible"] == "yes")
                    event(job, "verify", "done", f"Vision model confirmed {yes}/{len(v['verdicts'])} boxed findings as visible to readers")
                except Exception as e:  # noqa: BLE001
                    event(job, "verify", "warn", f"Vision verification skipped: {e}")

            # 4. fix
            css, source = None, "deterministic"
            if llm.enabled() and before:
                try:
                    fx = llm.fix(script, before, pages[0].get("fonts"))
                    clean, problems = llm.sanitize_css(fx.get("css", ""))
                    fx["sanitizer"] = problems
                    job["model"]["fix"] = {k: fx.get(k) for k in ("translations", "source_changes", "injection_attempts", "sanitizer", "usage")}
                    if clean:
                        css, source = clean, "model"
                    event(job, "fix", "done" if clean else "warn",
                          f"Model proposed a {len(fx.get('css', ''))}-char CSS patch; sanitizer: {', '.join(problems) or 'clean'}"
                          + ("" if clean else " → rejected, using deterministic patch"))
                except Exception as e:  # noqa: BLE001
                    event(job, "fix", "warn", f"Model fix failed ({e}); using deterministic patch")
            if not css and before:
                css = llm.fallback_css(script, before)
            job["patch"] = {"css": css, "source": source}

            # 5. prove: re-measure with the patch in a brand-new sandbox
            if css:
                event(job, "prove", "running", "Sandbox #3: re-render every page with the patch, re-run detectors + OCR")
                res3, ev3 = sandbox.dispatch("prove", [pg["url"] for pg in pages], script, host, css_patch=css, internal_ok=internal_ok)
                job["containment"].append(ev3)
                if res3:
                    after_pages, bare_after = collect(jid, "after", res3)
                    after = [f for pg in after_pages for f in pg.get("findings", [])]
                    job["after"] = after
                    job["after_pages"] = [{k: pg.get(k) for k in ("url", "image", "ocr")} for pg in after_pages]
                    job["bare_after"] = bare_after
                    job["net"].append(res3.get("net"))
                    akeys = {f["key"] for f in after}
                    for f in before:
                        f["fixed"] = f["key"] not in akeys
                    event(job, "prove", "done", f"Sandbox #3 destroyed={ev3['destroyed']} · {sum(f['fixed'] for f in before)}/{len(before)} findings gone after patch")
                else:
                    event(job, "prove", "warn", "Proof sandbox returned no result")

            job["score"] = {"before": score(before), "after": score(job.get("after", before))}
            job["status"] = "done"
            event(job, "report", "done", f"Script readiness {job['score']['before']} → {job['score']['after']}")
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = str(e)
            event(job, "error", "error", str(e))
            traceback.print_exc()
        finally:
            (DATA / jid / "report.json").write_text(json.dumps(job, ensure_ascii=False, default=str), encoding="utf-8")


@app.on_event("startup")
def startup():
    if sandbox.LOCAL:
        print("[glyphsweep] GS_LOCAL=1: dev mode, sandboxes are local subprocesses (NOT isolated)", flush=True)
        return
    try:
        sandbox.ensure_networks()
        n = sandbox.sweep_orphans()
        print(f"[glyphsweep] runtime={sandbox.runtime()} orphans_removed={n}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[glyphsweep] docker not ready: {e}", flush=True)


@app.post("/api/jobs")
def create_job(body: JobIn):
    if body.script not in llm.LANG_NAME:
        raise HTTPException(400, "script must be one of " + ", ".join(llm.LANG_NAME))
    url = DEMO_URL if body.demo else body.url.strip()
    host = urlparse(url).hostname if body.demo else validate_url(url)
    jid = uuid.uuid4().hex[:12]
    (DATA / jid).mkdir(parents=True, exist_ok=True)
    job = {"id": jid, "url": url, "host": host, "script": body.script, "demo": body.demo, "status": "queued",
           "created": time.time(), "events": [], "containment": [], "model": {}, "net": []}
    JOBS[jid] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return {"id": jid}


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        p = DATA / re.sub(r"[^a-f0-9]", "", jid) / "report.json"
        if p.exists():
            return JSONResponse(json.loads(p.read_text(encoding="utf-8")))
        raise HTTPException(404)
    return JSONResponse(json.loads(json.dumps(job, ensure_ascii=False, default=str)))


@app.get("/api/jobs/{jid}/img/{name}")
def get_img(jid: str, name: str):
    jid = re.sub(r"[^a-f0-9]", "", jid)
    name = re.sub(r"[^a-z0-9_.]", "", name)
    p = DATA / jid / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/health")
def health():
    info = {"model": llm.MODEL, "model_configured": llm.enabled()}
    try:
        info["runtime"] = "local-dev (not isolated)" if sandbox.LOCAL else sandbox.runtime()
    except Exception as e:  # noqa: BLE001
        info["runtime"] = f"unavailable: {e}"
    return info


app.mount("/demo", StaticFiles(directory=ROOT / "demo", html=True), name="demo")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
