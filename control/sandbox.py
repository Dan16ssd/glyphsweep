"""Dispatches one job stage into a fresh, isolated sandbox and tears it down.

Per stage:
  1. start a per-job egress proxy (allowlist = target host + Google Fonts)
  2. start the browser sandbox on an internal network whose only exit is that proxy:
     gVisor runtime (runsc) when installed, read-only rootfs, tmpfs /tmp, all caps
     dropped, no-new-privileges, memory/CPU/PID caps, non-root user, no secrets
  3. wait with a hard wall-clock timeout, collect stdout + proxy decisions
  4. force-remove both containers and confirm they are gone
Returns the runner's result plus an evidence record of all of the above.
"""

import base64
import json
import os
import time
import uuid

import docker
from docker.errors import NotFound

SANDBOX_IMAGE = os.environ.get("GS_SANDBOX_IMAGE", "glyphsweep-sandbox:latest")
PROXY_IMAGE = os.environ.get("GS_PROXY_IMAGE", "glyphsweep-proxy:latest")
NET_INTERNAL = os.environ.get("GS_NET_INTERNAL", "gs-internal")
NET_EGRESS = os.environ.get("GS_NET_EGRESS", "gs-egress")
TIMEOUT_S = int(os.environ.get("GS_SANDBOX_TIMEOUT", "240"))
MEM = os.environ.get("GS_SANDBOX_MEM", "1536m")
CPUS = float(os.environ.get("GS_SANDBOX_CPUS", "1.5"))
FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"]
# Common public CDNs real sites load CSS/JS/fonts from. Logged per request like everything else.
CDN_HOSTS = [".cloudflare.com", ".jsdelivr.net", "unpkg.com", "ajax.googleapis.com", ".cloudfront.net",
             ".akamaized.net", ".shopify.com", ".shopifycdn.com", ".wp.com", ".bootstrapcdn.com", ".fontawesome.com",
             ".gstatic.com", ".googleapis.com", ".fastly.net", ".wixstatic.com", ".squarespace-cdn.com"]
TWO_LEVEL_TLDS = {"co", "com", "net", "org", "gov", "edu", "ac", "or", "go", "in"}


def site_allowlist(host):
    """Target's registrable domain + all its subdomains (www., cdn., static.) + public CDNs."""
    parts = host.split(".")
    if host.replace(".", "").isdigit() or len(parts) < 2:
        base = host
    elif len(parts) >= 3 and parts[-2] in TWO_LEVEL_TLDS and len(parts[-1]) == 2:
        base = ".".join(parts[-3:])
    else:
        base = ".".join(parts[-2:])
    return [host, "." + base] + FONT_HOSTS + CDN_HOSTS
RESULT_MARK = "GLYPHSWEEP_RESULT "

_client = None


def client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


def runtime():
    forced = os.environ.get("GS_RUNTIME")
    if forced:
        return forced
    try:
        return "runsc" if "runsc" in client().info().get("Runtimes", {}) else "runc"
    except Exception:  # noqa: BLE001
        return "runc"


def ensure_networks():
    c = client()
    names = {n.name for n in c.networks.list()}
    if NET_INTERNAL not in names:
        c.networks.create(NET_INTERNAL, driver="bridge", internal=True)
    if NET_EGRESS not in names:
        c.networks.create(NET_EGRESS, driver="bridge")


def _gone(cid):
    try:
        client().containers.get(cid)
        return False
    except NotFound:
        return True


LOCAL = os.environ.get("GS_LOCAL") == "1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dispatch(stage, pages, script, target_host, css_patch=None, bare_profile=True, internal_ok=None, sentinels=None):
    if LOCAL:
        return _dispatch_local(stage, pages, script, target_host, css_patch, internal_ok)
    c = client()
    rid = uuid.uuid4().hex[:10]
    rt = runtime()
    ev = {"stage": stage, "run_id": rid, "runtime": rt, "pages": pages, "started": time.time()}
    allow = [target_host] + FONT_HOSTS if internal_ok else site_allowlist(target_host)
    proxy = sbx = None
    try:
        proxy = c.containers.run(
            PROXY_IMAGE, detach=True, name=f"gs-proxy-{rid}",
            environment={"ALLOW_HOSTS": ",".join(allow), "INTERNAL_OK": internal_ok or ""},
            network=NET_EGRESS, mem_limit="128m", nano_cpus=int(0.5e9), pids_limit=64,
            read_only=True, cap_drop=["ALL"], security_opt=["no-new-privileges"], user="65534:65534",
            labels={"glyphsweep": "proxy", "run": rid},
        )
        c.networks.get(NET_INTERNAL).connect(proxy)
        proxy.reload()
        # Address the proxy by IP: no dependence on Docker's embedded DNS inside the sandbox.
        proxy_ip = proxy.attrs["NetworkSettings"]["Networks"][NET_INTERNAL]["IPAddress"]

        spec = {
            "pages": pages, "script": script, "css_patch": css_patch, "bare_profile": bare_profile,
            "proxy": f"http://{proxy_ip}:8888", "max_pages": 4,
            "sentinels": sentinels or SENTINELS[script],
        }
        host_config = dict(
            network=NET_INTERNAL, read_only=True,
            tmpfs={"/tmp": "rw,size=768m,mode=1777"}, shm_size="512m",
            mem_limit=MEM, memswap_limit=MEM, nano_cpus=int(CPUS * 1e9), pids_limit=512,
            cap_drop=["ALL"], security_opt=["no-new-privileges"], runtime=rt,
        )
        sbx = c.containers.create(
            SANDBOX_IMAGE, name=f"gs-sbx-{rid}",
            environment={"JOB_SPEC": base64.b64encode(json.dumps(spec).encode()).decode()},
            labels={"glyphsweep": "sandbox", "run": rid}, **host_config,
        )
        sbx.start()
        ev["limits"] = {"memory": MEM, "cpus": CPUS, "pids": 512, "read_only_rootfs": True, "tmpfs": "/tmp 768m",
                        "cap_drop": "ALL", "no_new_privileges": True, "network": f"{NET_INTERNAL} (internal, no route out)",
                        "egress": f"only via proxy {proxy_ip}:8888; allowlist = {', '.join(allow[:4])} + {max(0, len(allow) - 4)} CDN/font hosts",
                        "timeout_s": TIMEOUT_S, "secrets_passed": 0}
        timed_out = False
        try:
            st = sbx.wait(timeout=TIMEOUT_S)
            ev["exit_code"] = st.get("StatusCode")
        except Exception:  # noqa: BLE001  (requests ReadTimeout)
            timed_out = True
            sbx.kill()
            ev["exit_code"] = "killed"
        ev["timed_out"] = timed_out
        sbx.reload()
        ev["oom_killed"] = sbx.attrs.get("State", {}).get("OOMKilled", False)
        out = sbx.logs(stdout=True, stderr=False).decode("utf-8", "replace")
        err = sbx.logs(stdout=False, stderr=True).decode("utf-8", "replace")
        ev["stderr_tail"] = err[-1500:]
        result = None
        for line in out.splitlines():
            if line.startswith(RESULT_MARK):
                result = json.loads(line[len(RESULT_MARK):])
        if result:
            ev["self_probe"] = result.get("probe")
        proxy_log = []
        for line in proxy.logs().decode("utf-8", "replace").splitlines():
            try:
                proxy_log.append(json.loads(line))
            except ValueError:
                pass
        ev["egress"] = {
            "allowed": sorted({f"{p['host']}:{p['port']}" for p in proxy_log if p.get("action") == "allow"}),
            "denied": [{"host": p.get("host"), "port": p.get("port"), "reason": p.get("reason")}
                       for p in proxy_log if p.get("action") == "deny"][:50],
        }
        return result, ev
    finally:
        for ctr in (sbx, proxy):
            if ctr is not None:
                try:
                    ctr.remove(force=True)
                except Exception:  # noqa: BLE001
                    pass
        ev["destroyed"] = all(_gone(x.id) for x in (sbx, proxy) if x is not None)
        ev["finished"] = time.time()
        ev["seconds"] = round(ev["finished"] - ev["started"], 1)


SENTINELS = {
    "lao": ["Noto Sans Lao", "Noto Serif Lao"],
    "thai": ["Noto Sans Thai", "Noto Serif Thai"],
    "khmer": ["Noto Sans Khmer", "Noto Serif Khmer"],
    "myanmar": ["Noto Sans Myanmar", "Noto Serif Myanmar"],
}


def sweep_orphans():
    """Remove any sandbox/proxy left behind by a crash (lifecycle discipline)."""
    n = 0
    for ctr in client().containers.list(all=True, filters={"label": "glyphsweep"}):
        try:
            ctr.remove(force=True)
            n += 1
        except Exception:  # noqa: BLE001
            pass
    return n


def _dispatch_local(stage, pages, script, target_host, css_patch, internal_ok):
    """DEV ONLY: same runner + proxy as subprocesses on this machine. Not isolated; labelled as such."""
    import socket
    import subprocess
    import sys

    rid = uuid.uuid4().hex[:10]
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    allow = [target_host] + FONT_HOSTS if internal_ok else site_allowlist(target_host)
    env = dict(os.environ, ALLOW_HOSTS=",".join(allow), INTERNAL_OK=internal_ok or "", PORT=str(port), BIND="127.0.0.1",
               PYTHONIOENCODING="utf-8")
    proxy = subprocess.Popen([sys.executable, "-u", os.path.join(REPO, "proxy", "proxy.py")], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    ev = {"stage": stage, "run_id": rid, "runtime": "local-dev (NOT isolated)", "pages": pages, "started": time.time(),
          "limits": {"note": "GS_LOCAL=1 dev mode: no container, no limits"}}
    spec = {"pages": pages, "script": script, "css_patch": css_patch, "bare_profile": False,
            "proxy": f"http://127.0.0.1:{port}", "max_pages": 4,
            "sentinels": os.environ.get("GS_LOCAL_SENTINELS", "Lao UI,Leelawadee UI").split(",")}
    renv = {k: v for k, v in os.environ.items() if not any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET"))}
    renv["JOB_SPEC"] = base64.b64encode(json.dumps(spec).encode()).decode()
    renv["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([sys.executable, os.path.join(REPO, "sandbox", "runner.py")], env=renv,
                           capture_output=True, timeout=TIMEOUT_S)
        ev["exit_code"], ev["timed_out"] = r.returncode, False
        out = r.stdout.decode("utf-8", "replace")
        ev["stderr_tail"] = r.stderr.decode("utf-8", "replace")[-1500:]
    except subprocess.TimeoutExpired:
        out, ev["exit_code"], ev["timed_out"] = "", "killed", True
    finally:
        proxy.terminate()
        plog = proxy.communicate(timeout=5)[0].decode("utf-8", "replace")
    result = None
    for line in out.splitlines():
        if line.startswith(RESULT_MARK):
            result = json.loads(line[len(RESULT_MARK):])
    pl = []
    for line in plog.splitlines():
        try:
            pl.append(json.loads(line))
        except ValueError:
            pass
    if result:
        ev["self_probe"] = result.get("probe")
    ev["egress"] = {"allowed": sorted({f"{p['host']}:{p['port']}" for p in pl if p.get("action") == "allow"}),
                    "denied": [{"host": p.get("host"), "port": p.get("port"), "reason": p.get("reason")} for p in pl if p.get("action") == "deny"][:50]}
    ev["destroyed"] = True
    ev["finished"] = time.time()
    ev["seconds"] = round(ev["finished"] - ev["started"], 1)
    return result, ev
