#!/usr/bin/env python3
"""Local no-auth HTTP/HTTPS CONNECT proxy that forwards all traffic to an
upstream AUTHENTICATED residential proxy.

Why: Chrome's --proxy-server does NOT support inline user:pass credentials, but
our residential proxy (Webshare) requires them. Chrome points at this relay
(http://127.0.0.1:<port>, no auth); the relay opens a CONNECT tunnel to the
upstream proxy WITH a Proxy-Authorization header, then blind-pipes bytes.

This makes the SUBMITTING BROWSER egress from the same residential IP that
2Captcha used to solve the hCaptcha — required because hCaptcha tokens are
IP-bound and Lever validates them server-side (2026-06-03 finding: token solved
on residential IP but submitted from Azure IP => "error verifying application").

Usage:
  _proxy_relay.py --listen 127.0.0.1:18901 --upstream user:pass@host:port
Env fallback: RESIDENTIAL_PROXY / PROXY_2CAPTCHA (host:port:user:pass or
user:pass@host:port forms accepted).
"""
import argparse, base64, os, re, select, socket, sys, threading


def parse_upstream(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^https?://", "", raw)
    if not raw:
        return None
    # user:pass@host:port
    if "@" in raw:
        creds, hostport = raw.rsplit("@", 1)
        user, _, pw = creds.partition(":")
        host, _, port = hostport.partition(":")
        return host, int(port), user, pw
    parts = raw.split(":")
    if len(parts) == 4:  # host:port:user:pass
        host, port, user, pw = parts
        return host, int(port), user, pw
    if len(parts) == 2:  # host:port (no auth)
        host, port = parts
        return host, int(port), None, None
    raise ValueError(f"unparseable upstream proxy: {raw!r}")


def _pipe(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 60)
            if not r:
                break
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try: s.close()
            except Exception: pass


def handle(client, upstream):
    host, port, user, pw = upstream
    try:
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = client.recv(4096)
            if not chunk:
                client.close(); return
            req += chunk
        line = req.split(b"\r\n", 1)[0].decode("latin1")
        method, target, _ = line.split(" ", 2)

        up = socket.create_connection((host, port), timeout=30)
        auth = b""
        if user is not None:
            tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
            auth = f"Proxy-Authorization: Basic {tok}\r\n".encode()

        if method.upper() == "CONNECT":
            # target = host:port ; open tunnel via upstream, then 200 to client
            up.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n".encode() + auth + b"\r\n")
            resp = b""
            while b"\r\n\r\n" not in resp:
                d = up.recv(4096)
                if not d:
                    break
                resp += d
            if b" 200 " in resp.split(b"\r\n", 1)[0]:
                client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                _pipe(client, up)
            else:
                client.sendall(resp or b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                up.close(); client.close()
        else:
            # plain HTTP: inject auth header, forward original request + body
            if auth:
                head, _, rest = req.partition(b"\r\n")
                req = head + b"\r\n" + auth + rest
            up.sendall(req)
            _pipe(client, up)
    except Exception:
        try: client.close()
        except Exception: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default="127.0.0.1:18901")
    ap.add_argument("--upstream", default=os.environ.get("RESIDENTIAL_PROXY") or os.environ.get("PROXY_2CAPTCHA"))
    a = ap.parse_args()
    upstream = parse_upstream(a.upstream)
    if not upstream:
        print("no upstream proxy configured", file=sys.stderr); sys.exit(2)
    lhost, lport = a.listen.split(":")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((lhost, int(lport)))
    srv.listen(128)
    print(f"relay listening {a.listen} -> {upstream[0]}:{upstream[1]} (auth={'yes' if upstream[2] else 'no'})", flush=True)
    while True:
        cli, _ = srv.accept()
        threading.Thread(target=handle, args=(cli, upstream), daemon=True).start()


if __name__ == "__main__":
    main()
