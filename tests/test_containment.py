"""Fast checks of the containment-critical pieces. Run: python -m pytest tests -q"""

import asyncio
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "control"))

import llm  # noqa: E402
import sandbox  # noqa: E402

GOOGLE = "@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Lao:wght@400;700&display=swap');"


def test_sanitizer_allows_plain_css_and_google_fonts():
    css, problems = llm.sanitize_css(GOOGLE + "\nh1 { line-height: 1.8 !important; }")
    assert css and not problems
    assert css.startswith("@import url('https://fonts.googleapis.com/")


def test_sanitizer_rejects_every_fetch_or_exec_primitive():
    attacks = [
        "a{background:url(https://evil.example/x)}",
        "a{background:image-set(\"https://evil.example/x\" 1x)}",
        "a{background:-webkit-image-set('//evil.example/x' 1x)}",
        "@import url('https://evil.example/a.css');",
        "@import 'https://fonts.googleapis.com.evil.example/css2?family=x';",
        "@font-face{font-family:x;src:url(//evil.example/f.woff)}",
        "a{color:red}</style><script>alert(1)</script>",
        "a{behavior:url(x.htc)}",
        "a{width:expression(alert(1))}",
        "a{content:'\\75 rl(x)'}",
        "a{background:src('https://evil.example')}",
        "a{color:red",
    ]
    for a in attacks:
        css, problems = llm.sanitize_css(a)
        assert css is None, f"not rejected: {a!r}"


def test_planner_output_cannot_add_urls(monkeypatch):
    links = [{"href": "https://shop.la/checkout", "text": "x"}]
    monkeypatch.setattr(llm, "KEY", "k")
    monkeypatch.setattr(llm, "chat", lambda *a, **k: ('{"pages": ["https://shop.la/checkout", "https://evil.example/"]}', {}))
    out = llm.plan_pages("https://shop.la/", "lao", links, 2)
    assert out["pages"] == ["https://shop.la/checkout"]
    assert out["rejected"] == ["https://evil.example/"]


def test_allowlist_scopes_to_registrable_domain():
    assert sandbox.site_allowlist("www.bcel.com.la")[:2] == ["www.bcel.com.la", ".bcel.com.la"]
    assert sandbox.site_allowlist("news.kpl.gov.la")[:2] == ["news.kpl.gov.la", ".kpl.gov.la"]
    assert sandbox.site_allowlist("shop.example.com")[:2] == ["shop.example.com", ".example.com"]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_proxy_denies_unlisted_metadata_and_private_hosts():
    port = _free_port()
    env = dict(os.environ, ALLOW_HOSTS="example.com", PORT=str(port), BIND="127.0.0.1")
    p = subprocess.Popen([sys.executable, "-u", os.path.join(ROOT, "proxy", "proxy.py")], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{port}"}))
        for url in ["http://169.254.169.254/v1.json", "http://10.0.0.1/", "http://evil.example/", "http://localhost:1/"]:
            try:
                opener.open(url, timeout=5)
                raise AssertionError(f"proxy let {url} through")
            except urllib.error.HTTPError as e:
                assert e.code == 403, (url, e.code)
    finally:
        p.terminate()
        log = p.communicate(timeout=5)[0].decode()
    assert log.count('"action": "deny"') >= 4


def test_proxy_refuses_private_ip_even_when_dns_name_is_allowed():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gsproxy", os.path.join(ROOT, "proxy", "proxy.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ips, why = asyncio.run(mod.resolve_public("localhost", 80))
    assert ips is None and "non-public" in why
