"""Per-job egress proxy: the sandbox's ONLY route out.

One proxy container is started per job, attached to both the internal (no-egress)
sandbox network and the outside network. It allows only the job's target host
(plus Google Fonts, so font fixes can be proven) and refuses anything that resolves
to a private, loopback, link-local or metadata address. Every decision is logged as
one JSON line on stdout; the control plane reads those as containment evidence.
"""

import asyncio
import ipaddress
import json
import os
import socket
import time

ALLOW = [h.strip().lower() for h in os.environ.get("ALLOW_HOSTS", "").split(",") if h.strip()]
# Exact hostnames allowed to resolve privately: only the bundled demo site (served by
# the control plane on the Docker network). Never user-supplied.
INTERNAL_OK = {h.strip().lower() for h in os.environ.get("INTERNAL_OK", "").split(",") if h.strip()}
ALLOWED_PORTS = {80, 443, 8080, 8000}
BYTE_CAP = int(os.environ.get("BYTE_CAP", str(150 * 1024 * 1024)))
transferred = 0


def log(**kw):
    kw["t"] = round(time.time(), 3)
    print(json.dumps(kw), flush=True)


def host_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    for a in ALLOW:
        if a.startswith("."):
            if host.endswith(a) or host == a[1:]:
                return True
        elif host == a:
            return True
    return False


def ip_is_public(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return not (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast
                or a.is_reserved or a.is_unspecified)


async def resolve_public(host: str, port: int):
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    ips = [i[4][0] for i in infos]
    bad = [ip for ip in ips if not ip_is_public(ip)]
    if bad:
        return None, f"resolves to non-public address {bad[0]}"
    return ips, None


async def pipe(r, w):
    global transferred
    try:
        while True:
            data = await r.read(65536)
            if not data:
                break
            transferred += len(data)
            if transferred > BYTE_CAP:
                log(action="deny", reason="byte cap reached")
                break
            w.write(data)
            await w.drain()
    except Exception:  # noqa: BLE001
        pass
    finally:
        try:
            w.close()
        except Exception:  # noqa: BLE001
            pass


async def deny(writer, host, port, reason, code=403):
    log(action="deny", host=host, port=port, reason=reason)
    writer.write(f"HTTP/1.1 {code} Blocked by GlyphSweep egress policy\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    writer.close()


async def handle(reader, writer):
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
    except Exception:  # noqa: BLE001
        writer.close()
        return
    first = head.split(b"\r\n", 1)[0].decode("latin-1")
    try:
        method, target, _ = first.split(" ", 2)
    except ValueError:
        writer.close()
        return

    if method.upper() == "CONNECT":
        host, _, port = target.rpartition(":")
        port = int(port or 443)
        rest = b""
        path = ""
    else:
        # absolute-form: http://host[:port]/path
        if not target.startswith("http://"):
            return await deny(writer, "?", 0, "non-proxy request", 400)
        hp = target[7:].split("/", 1)[0]
        host, _, port = hp.partition(":")
        port = int(port or 80)
        path = "/" + target[7:].split("/", 1)[1] if "/" in target[7:] else "/"
        # One request per upstream connection, so EVERY request is checked and logged
        # (no keep-alive piggy-backing past the policy).
        lines = head.decode("latin-1").split("\r\n")
        lines[0] = f"{method} {path} HTTP/1.1"
        lines = [l for l in lines if l and not l.lower().startswith(("connection:", "proxy-connection:", "keep-alive:", "proxy-authorization:"))]
        rest = ("\r\n".join(lines) + "\r\nConnection: close\r\n\r\n").encode("latin-1")

    host = host.strip("[]")
    if port not in ALLOWED_PORTS:
        return await deny(writer, host, port, "port not allowed")
    if not host_allowed(host):
        return await deny(writer, host, port, "host not on job allowlist")
    try:
        ip, why = await resolve_public(host, port)
    except Exception as e:  # noqa: BLE001
        return await deny(writer, host, port, f"dns failure {e}", 502)
    if not ip and host.lower() in INTERNAL_OK:
        # The bundled demo lives on the control plane: only its static /demo/ files, GET only.
        if method.upper() != "GET" or not path.startswith("/demo/"):
            return await deny(writer, host, port, f"internal host: only GET /demo/* allowed (got {method} {path[:40]})")
        ip = [i[4][0] for i in await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    elif not ip:
        return await deny(writer, host, port, why)

    ur = uw = None
    last = None
    for addr in dict.fromkeys(ip):  # try every resolved (already vetted) address
        try:
            ur, uw = await asyncio.wait_for(asyncio.open_connection(addr, port), timeout=10)
            ip = addr
            break
        except Exception as e:  # noqa: BLE001
            last = e
    if uw is None:
        return await deny(writer, host, port, f"upstream connect failed {last}", 502)
    log(action="allow", host=host, port=port, ip=ip, method=method)
    if method.upper() == "CONNECT":
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
    else:
        uw.write(rest)
        await uw.drain()
    await asyncio.gather(pipe(reader, uw), pipe(ur, writer))


async def main():
    server = await asyncio.start_server(handle, os.environ.get("BIND", "0.0.0.0"), int(os.environ.get("PORT", "8888")))
    log(action="start", allow=ALLOW)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
