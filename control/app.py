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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import llm
import redteam
import sandbox

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("GS_DATA", "/data/jobs"))
DATA.mkdir(parents=True, exist_ok=True)
DEMO_HOST = os.environ.get("GS_DEMO_HOST", "glyphsweep-demo")
DEMO_URL = f"http://{DEMO_HOST}:8000/demo/shop.html"


def demo_url(script):
    """The hostile demo shop exists in every supported script (same bugs, same attacks)."""
    return DEMO_URL if script == "lao" else f"http://{DEMO_HOST}:8000/demo/{script}/shop.html"
MAX_PAGES = int(os.environ.get("GS_MAX_PAGES", "3"))
SEM = threading.BoundedSemaphore(int(os.environ.get("GS_CONCURRENCY", "2")))

app = FastAPI(title="GlyphSweep")
JOBS: dict = {}
LOCK = threading.Lock()

SEV = {"high": 8, "medium": 4, "low": 1}
SOURCE_ONLY = {"html_lang", "untranslated"}  # need an HTML/content change, not CSS
MAX_ROUNDS = int(os.environ.get("GS_FIX_ROUNDS", "2"))
RATE = {}  # ip -> [timestamps]
RATE_LIMIT = int(os.environ.get("GS_JOBS_PER_HOUR", "8"))
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
    """0-100 readiness: 100 = no issues; decays smoothly with weighted severity.
    Findings the vision model judged NOT visible to a reader don't count."""
    import math
    # Each problem TYPE counts once, at its worst severity (same formula as research/scan.py), so a big
    # site isn't scored 0 just for having 500 elements with the same CSS rule.
    worst = {}
    for f in findings:
        if (f.get("vision") or {}).get("visible") == "no" or f["check"] == "text_truncated":
            continue
        worst[f["check"]] = max(worst.get(f["check"], 0), SEV.get(f["severity"], 1))
    return round(100 * math.exp(-sum(worst.values()) / 40))


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
    """Scan ALL page text (visible + hidden + alt/title/aria/meta) for instructions aimed at AI agents."""
    out = []
    for pg in pages:
        text = pg.pop("pageText", "") or ""
        for m in INJECTION_RE.finditer(text):
            a, b = max(0, m.start() - 60), min(len(text), m.end() + 100)
            snippet = text[a:b].strip()
            if not any(snippet[:40] in x["text"] for x in out):
                out.append({"page": pg["url"], "text": snippet[:200]})
    return out[:10]


def mean_cer(bare):
    o = (bare or {}).get("ocr") or []
    return round(sum(x["cer"] for x in o) / len(o), 3) if o else None


def residual_for_model(after):
    return [{"check": f["check"], "selector": f["selector"], "detail": f.get("detail")}
            for f in after if f["check"] not in SOURCE_ONLY][:25]


def run_job(job):
    jid, url, script = job["id"], job["url"], job["script"]
    host = job["host"]
    internal_ok = DEMO_HOST if job["demo"] else None
    with SEM:
        try:
            job["status"] = "running"
            allow = f"[{host}, Google Fonts]" if job["demo"] else f"[{host} + its subdomains, Google Fonts, common CDNs]"
            event(job, "plan", "done", f"Target {host}; script {script}; egress allowlist = {allow}; "
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
            # Never report a perfect score for a page we didn't really see (bot wall, error page, wrong language).
            p0, lname = pages[0] if pages else {}, llm.LANG_NAME[script]
            if (p0.get("status") or 0) >= 400:
                raise RuntimeError(f"Inconclusive: the site answered HTTP {p0['status']} (“{(p0.get('title') or '')[:60]}”), "
                                   "probably bot protection, so there was nothing real to audit. No score is given.")
            if not p0.get("targetElements"):
                raise RuntimeError(f"Inconclusive: no {lname} text was found on the rendered page "
                                   f"(title “{(p0.get('title') or '')[:60]}”). Try the site's {lname}-language URL.")
            job["net"].append(res.get("net"))
            event(job, "dispatch", "done", f"Sandbox #1 destroyed={ev['destroyed']} · {len(pages[0].get('findings', []))} findings · "
                  f"{len(ev['egress']['denied'])} egress attempts blocked", run=ev["run_id"])

            # 2. planner picks more pages (only from links the sandbox actually saw)
            extra = []
            if llm.enabled() and (MAX_PAGES if job.get("demo") else min(MAX_PAGES, 2)) > 1:
                try:
                    # real sites: at most 1 extra page, so every prove sandbox stays fast; the demo shop is tiny
                    budget = MAX_PAGES if job.get("demo") else min(MAX_PAGES, 2)
                    plan = llm.plan_pages(url, script, pages[0].get("links", []), budget - 1)
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

            # 4-5. fix → prove loop: the model patches, a brand-new sandbox re-measures, and anything
            # still measurably broken goes back to the model (at most MAX_ROUNDS rounds).
            css, source, after, residual = None, "deterministic", None, None
            fixable = [f for f in before if f["check"] not in SOURCE_ONLY]
            job["rounds"] = []
            candidates = []

            def prove(rnd, source, css):
                """Inject `css` into a brand-new sandbox, re-run every detector + OCR, record the measured result."""
                n = len(job["containment"]) + 1
                event(job, "prove", "running", f"Sandbox #{n}: re-render every page with the round-{rnd} ({source}) patch, re-run detectors + OCR")
                res3, ev3 = sandbox.dispatch(f"prove-r{rnd}", [pg["url"] for pg in pages], script, host, css_patch=css, internal_ok=internal_ok)
                job["containment"].append(ev3)
                if not res3:
                    event(job, "prove", "warn", f"Proof sandbox #{n} returned no result")
                    return None
                after_pages, bare_after = collect(jid, f"after_r{rnd}", res3)
                aft = [f for pg in after_pages for f in pg.get("findings", [])]
                job["net"].append(res3.get("net"))
                resid = residual_for_model(aft)
                cand = {"round": rnd, "source": source, "css": css, "after": aft, "residual": resid, "score": score(aft),
                        "after_pages": [{k: pg.get(k) for k in ("url", "image", "ocr")} for pg in after_pages],
                        "bare_after": bare_after}
                candidates.append(cand)
                job["rounds"].append({"round": rnd, "source": source, "css": css, "open_after": len(aft), "score": cand["score"],
                                      "css_fixable_open": len(resid), "bare_cer": mean_cer(bare_after)})
                event(job, "prove", "done", f"Sandbox #{n} destroyed={ev3['destroyed']} · round {rnd} ({source}): "
                      f"{len(aft)} findings left ({len(resid)} CSS-fixable) · score {cand['score']}")
                return cand
            for rnd in range(1, (MAX_ROUNDS if llm.enabled() else 1) + 1):
                if not fixable or (rnd > 1 and not residual):
                    break
                new_css = None
                if llm.enabled():
                    try:
                        fx = llm.fix(script, before, pages[0].get("fonts"), previous_css=css if rnd > 1 else None,
                                     residual=residual if rnd > 1 else None)
                        clean, problems = llm.sanitize_css(fx.get("css", ""))
                        if rnd == 1 or fx.get("translations"):
                            job["model"]["fix"] = {k: fx.get(k) for k in ("translations", "source_changes", "injection_attempts", "usage")}
                        job["model"].setdefault("sanitizer", []).append({"round": rnd, "problems": problems})
                        if clean:
                            new_css, source = clean, "model"
                        event(job, "fix", "done" if clean else "warn",
                              f"Round {rnd}: model wrote a {len(fx.get('css', ''))}-char CSS patch"
                              + (f" from {len(residual)} residual measurements" if rnd > 1 else "")
                              + f"; sanitizer: {', '.join(problems) or 'clean'}" + ("" if clean else " → rejected"))
                    except Exception as e:  # noqa: BLE001
                        event(job, "fix", "warn", f"Round {rnd}: model fix failed ({e})")
                if not new_css:
                    if rnd > 1:
                        break
                    new_css, source = llm.fallback_css(script, before), "deterministic"
                    event(job, "fix", "done", "Using the deterministic fixer's patch")
                css = new_css
                cand = prove(rnd, source, css)
                if not cand:
                    break
                residual = cand["residual"]
            # Candidate competition: nothing is trusted, everything is measured. When the model wrote the
            # patch, also prove the deterministic patch and deterministic+model, then keep the best score.
            model_css = next((c["css"] for c in reversed(candidates) if c["source"] == "model"), None)
            if fixable and model_css:
                det = llm.fallback_css(script, before)
                event(job, "fix", "done", "Candidate competition: also proving the deterministic patch and deterministic + model")
                prove(len(candidates) + 1, "deterministic", det)
                prove(len(candidates) + 1, "deterministic+model", det + "\n/* model */\n" + model_css)
            if candidates:
                best = max(candidates, key=lambda c: (c["score"], -len(c["after"])))
                css, source, after = best["css"], best["source"], best["after"]
                job.update(after=after, after_pages=best["after_pages"], bare_after=best["bare_after"])
                for r in job["rounds"]:
                    r["chosen"] = r["round"] == best["round"]
                if len(candidates) > 1:
                    event(job, "prove", "done", "Kept the best proven patch: " + " · ".join(
                        f"{c['source']} {c['score']}" + (" ✓" if c is best else "") for c in candidates))
            job["patch"] = {"css": css, "source": source}

            if after is not None:
                akeys = {f["key"] for f in after}
                for f in before:
                    f["fixed"] = f["key"] not in akeys
                # Font fixes are judged by pixels, not by our own font check: on the bare device
                # (no system font for the script) OCR must actually read the text after the patch.
                cb, ca = mean_cer(bare), mean_cer(job.get("bare_after"))
                job["ocr_proof"] = {"cer_before": cb, "cer_after": ca}
                if ca is not None:
                    for f in before:
                        if f["check"] == "font_fallback":
                            f["fixed"] = f["fixed"] and ca < 0.25
                            f["proof"] = f"bare-device OCR error {cb:.0%} → {ca:.0%}" if cb is not None else f"bare-device OCR error {ca:.0%}"

                # Vision check on the AFTER render: does the patched page look right to a reader?
                if llm.enabled() and job.get("after_pages") and job["after_pages"][0].get("image"):
                    try:
                        p0 = pages[0]["url"]
                        img = (DATA / jid / job["after_pages"][0]["image"]["src"].rsplit("/", 1)[1]).read_bytes()
                        fixed_boxes = [dict(f, check=f"{f['check']} (should now be FIXED)") for f in before
                                       if f["page"] == p0 and f.get("fixed") and f["bbox"]["w"] > 0]
                        va = llm.verify(script, fixed_boxes[:10], img)
                        job["model"]["verify_after"] = va
                        by_id = {x["id"]: x for x in va["verdicts"]}
                        for f in before:
                            if f["page"] == p0 and f["id"] in by_id:
                                f["vision_after"] = by_id[f["id"]]
                        still = sum(1 for x in va["verdicts"] if x["visible"] == "yes")
                        event(job, "verify", "done", f"Vision re-check of the patched page: {still}/{len(va['verdicts'])} "
                              "previously boxed problems still look visible")
                    except Exception as e:  # noqa: BLE001
                        event(job, "verify", "warn", f"Vision re-check skipped: {e}")

            job["score"] = {"before": score(before), "after": score(after if after is not None else before)}
            job["approval"] = {"state": "pending"}
            job["status"] = "done"
            event(job, "report", "done", f"Script readiness {job['score']['before']} → {job['score']['after']}")
            # Human in the loop: the agent never ships its own work. The proven patch stays locked
            # until a person reviews the before/after and approves it.
            event(job, "approve", "warn", "Waiting for human approval: review the before/after and the proven patch. "
                  "patch.css is only released after a person approves.")
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


MODEL_STATUS = {"status": "not checked"}


@app.on_event("startup")
def startup_models():
    MODEL_STATUS["status"] = llm.check_models()
    print(f"[glyphsweep] models: {MODEL_STATUS['status']}", flush=True)


@app.post("/api/jobs")
def create_job(body: JobIn, request: Request):
    if body.script not in llm.LANG_NAME:
        raise HTTPException(400, "script must be one of " + ", ".join(llm.LANG_NAME))
    # Caddy is the only ingress (control publishes no ports) and overwrites X-Forwarded-For with the
    # real peer address, so its last entry is trustworthy. Without Caddy, fall back to the socket peer.
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[-1].strip() if xff else (request.client.host if request.client else "?")
    now = time.time()
    with LOCK:
        RATE[ip] = [t for t in RATE.get(ip, []) if now - t < 3600]
        if len(RATE[ip]) >= RATE_LIMIT:
            raise HTTPException(429, f"Limit is {RATE_LIMIT} sweeps per hour per visitor. Try again later.")
        RATE[ip].append(now)
        for old in sorted(JOBS, key=lambda k: JOBS[k]["created"])[:-100]:  # keep memory bounded
            if JOBS[old]["status"] in ("done", "error"):
                JOBS.pop(old, None)
    url = demo_url(body.script) if body.demo else body.url.strip()
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
    for _ in range(5):  # the worker thread may be mutating the job; retry a consistent snapshot
        try:
            return JSONResponse(json.loads(json.dumps(job, ensure_ascii=False, default=str)))
        except RuntimeError:
            time.sleep(0.05)
    raise HTTPException(503, "busy, retry")


class ApprovalIn(BaseModel):
    decision: str


@app.post("/api/jobs/{jid}/approval")
def set_approval(jid: str, body: ApprovalIn):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "Only a sweep from this server session can be approved.")
    with LOCK:
        if job.get("status") != "done" or (job.get("approval") or {}).get("state") != "pending":
            raise HTTPException(409, "Nothing is waiting for approval on this sweep.")
        ok = body.decision == "approve"
        job["approval"] = {"state": "approved" if ok else "rejected", "at": time.time()}
    # event() takes LOCK itself, so log outside the block above
    if ok:
        event(job, "approve", "done", f"Approved by a human · patch.css released (proven score "
              f"{job['score']['before']} → {job['score']['after']}, source: {(job.get('patch') or {}).get('source', '?')})")
    else:
        event(job, "approve", "error", "Rejected by a human · patch.css stays locked, nothing is released")
    (DATA / jid / "report.json").write_text(json.dumps(job, ensure_ascii=False, default=str), encoding="utf-8")
    return get_job(jid)


@app.get("/api/jobs/{jid}/patch.css")
def get_patch(jid: str):
    job = get_job(jid)
    data = json.loads(job.body)
    # Sweeps from before the approval step have no "approval" field and stay downloadable.
    if (data.get("approval") or {}).get("state", "approved") != "approved":
        raise HTTPException(403, "This patch has not been approved by a human yet.")
    css = (data.get("patch") or {}).get("css") or "/* no patch */"
    head = f"/* GlyphSweep patch for {data.get('url')} ({data.get('script')}), proven in a fresh sandbox. */\n"
    return Response(head + css, media_type="text/css",
                    headers={"Content-Disposition": f'attachment; filename="glyphsweep-{jid}.css"'})


@app.get("/api/jobs/{jid}/report.json")
def get_report(jid: str):
    job = get_job(jid)
    return Response(job.body, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="glyphsweep-{jid}.json"'})


@app.get("/api/jobs/{jid}/img/{name}")
def get_img(jid: str, name: str):
    jid = re.sub(r"[^a-f0-9]", "", jid)
    name = re.sub(r"[^a-z0-9_.]", "", name)
    p = DATA / jid / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


RT_LATEST = DATA.parent / "redteam-latest.json"


def run_redteam(job):
    with SEM:
        try:
            job["status"] = "running"
            event(job, "plan", "done", "Red-team run: 5 fresh sandboxes attack themselves; verdicts come from the proxy log and Docker, "
                  "not from the sandbox's own word")
            rt = redteam.run(job, event, injection_findings, DEMO_HOST)
            event(job, "report", "done" if rt["contained"] == rt["total"] else "error",
                  f"Contained {rt['contained']}/{rt['total']} attacks · every sandbox destroyed")
            job["status"] = "done"
            RT_LATEST.write_text(json.dumps(job, ensure_ascii=False, default=str), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = str(e)
            event(job, "error", "error", str(e))
            traceback.print_exc()
        finally:
            (DATA / job["id"] / "report.json").write_text(json.dumps(job, ensure_ascii=False, default=str), encoding="utf-8")


@app.post("/api/redteam")
def create_redteam(request: Request):
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[-1].strip() if xff else (request.client.host if request.client else "?")
    now = time.time()
    with LOCK:
        RATE[ip] = [t for t in RATE.get(ip, []) if now - t < 3600]
        if len(RATE[ip]) >= RATE_LIMIT:
            raise HTTPException(429, f"Limit is {RATE_LIMIT} runs per hour per visitor. Try again later.")
        RATE[ip].append(now)
    jid = uuid.uuid4().hex[:12]
    (DATA / jid).mkdir(parents=True, exist_ok=True)
    job = {"id": jid, "kind": "redteam", "url": "red-team suite", "host": DEMO_HOST, "script": "lao", "demo": True,
           "status": "queued", "created": time.time(), "events": [], "containment": [], "model": {}, "net": []}
    JOBS[jid] = job
    threading.Thread(target=run_redteam, args=(job,), daemon=True).start()
    return {"id": jid}


@app.get("/api/redteam/latest")
def redteam_latest():
    if not RT_LATEST.exists():
        raise HTTPException(404, "No red-team run yet.")
    return JSONResponse(json.loads(RT_LATEST.read_text(encoding="utf-8")))


def _badge(label, value, color):
    """Shields-style flat badge, no external service."""
    from html import escape
    lw, vw = 7 * len(label) + 12, 7 * len(value) + 12
    return Response(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="20" role="img" aria-label="{escape(label)}: {escape(value)}">'
        f'<rect width="{lw}" height="20" fill="#14123A"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
        f'<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">'
        f'<text x="{lw / 2}" y="14">{escape(label)}</text><text x="{lw + vw / 2}" y="14">{escape(value)}</text></g></svg>',
        media_type="image/svg+xml", headers={"Cache-Control": "no-cache, max-age=0"})


@app.get("/api/jobs/{jid}/badge.svg")
def job_badge(jid: str):
    data = json.loads(get_job(jid).body)
    lang = llm.LANG_NAME.get(data.get("script"), "script")
    sc = data.get("score") or {}
    if data.get("status") != "done" or "after" not in sc:
        return _badge(f"{lang} readiness", data.get("status", "?"), "#6B6890")
    after = sc["after"]
    color = "#2F9E7E" if after >= 70 else "#C9922A" if after >= 40 else "#D9455F"
    return _badge(f"{lang} readiness", f"{sc.get('before')} → {after} (GlyphSweep)", color)


@app.get("/api/redteam/badge.svg")
def redteam_badge():
    if not RT_LATEST.exists():
        return _badge("red-team", "not run", "#6B6890")
    rt = json.loads(RT_LATEST.read_text(encoding="utf-8")).get("redteam") or {}
    ok = rt.get("contained") == rt.get("total")
    return _badge("red-team", f"{rt.get('contained')}/{rt.get('total')} attacks contained", "#2F9E7E" if ok else "#D9455F")


@app.get("/api/health")
def health():
    info = {"model": llm.MODEL, "vision_model": llm.VISION_MODEL, "model_configured": llm.enabled(),
            "model_check": MODEL_STATUS["status"]}
    try:
        info["runtime"] = "local-dev (not isolated)" if sandbox.LOCAL else sandbox.runtime()
    except Exception as e:  # noqa: BLE001
        info["runtime"] = f"unavailable: {e}"
    return info


app.mount("/demo", StaticFiles(directory=ROOT / "demo", html=True), name="demo")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
