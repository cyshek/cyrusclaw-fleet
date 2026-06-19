#!/usr/bin/env python3
"""
siri-webhook.py — tiny hands-free voice loop for OpenClaw.

Listens on 127.0.0.1:18900. Cloudflared (or any reverse proxy) fronts it with
HTTPS. iOS Siri Shortcut POSTs `{"text": "..."}` and gets `{"reply": "..."}`
back, which the Shortcut then speaks.

Auth: require header `X-Siri-Token: <secret>` on every request. Secret lives in
SIRI_WEBHOOK_TOKEN (sourced from ~/.openclaw/.env). The gateway operator token
NEVER leaves the VM — this script proxies and adds it server-side.

Optional `session` field overrides the OpenAI `user` field so multiple
conversation threads can be kept separate. Default thread is "siri-default" so
follow-up turns share session state with the prior one.
"""
import json
import os
import sys
import time
import subprocess
import tempfile
import http.server
import socketserver
import urllib.request
import urllib.error

PORT = int(os.environ.get("SIRI_WEBHOOK_PORT", "18900"))
GATEWAY = os.environ.get("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18789")
ENV_FILE = "/home/azureuser/.openclaw/.env"


def load_env():
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

SIRI_TOKEN = os.environ.get("SIRI_WEBHOOK_TOKEN")
GW_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN")
if not SIRI_TOKEN:
    print("FATAL: SIRI_WEBHOOK_TOKEN missing", file=sys.stderr)
    sys.exit(2)
if not GW_TOKEN:
    print("FATAL: OPENCLAW_GATEWAY_TOKEN missing", file=sys.stderr)
    sys.exit(2)


def call_openclaw(text, session_key):
    payload = {
        "model": "openclaw/main",
        "messages": [
            {"role": "system", "content": "VOICE MODE: This reply will be spoken aloud via Siri. HARD LIMITS: max 3 sentences, max 200 characters total, no markdown, no emojis, no lists, no code, no URLs. Plain conversational speech only. If the user's question genuinely needs detail, give a one-sentence voice answer and end with: 'Full details posted to Discord.' These limits are non-negotiable."},
            {"role": "user", "content": text},
        ],
        "user": session_key,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GATEWAY}/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {GW_TOKEN}",
            "Content-Type": "application/json",
            "x-openclaw-message-channel": "siri",
            "x-openclaw-session-key": session_key,
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        sys.stderr.write(f"[{ts}] {self.address_string()} {fmt % args}\n")
        sys.stderr.flush()

    def do_GET(self):
        if self.path == "/health":
            return self._send_json(200, {"ok": True})
        return self._send_json(404, {"error": "not_found"})

    def _log_to_discord(self, user_text, reply_text):
        channel = os.environ.get("SIRI_DISCORD_LOG_CHANNEL")
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if not channel or not token:
            return
        try:
            content = f"\U0001f399\ufe0f **You (Siri):** {user_text}\n\U0001f916 {reply_text}"
            if len(content) > 1900:
                content = content[:1900] + "\u2026"
            req = urllib.request.Request(
                f"https://discord.com/api/v10/channels/{channel}/messages",
                data=json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "DiscordBot (https://github.com/openclaw/openclaw, 1.0) siri-webhook",
                },
            )
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            sys.stderr.write(f"[siri] discord log failed: {e}\n")
            sys.stderr.flush()

    def _synthesize_chunk(self, text, voice, lang, rate, out_path):
        """Run node-edge-tts for a single chunk.

        node-edge-tts sometimes exits non-zero with an UnhandledPromiseRejection
        on the WebSocket close handshake AFTER writing the file successfully.
        Treat 'file exists and non-empty' as success regardless of exit code.
        """
        safe = ("\u200b" + text) if text.startswith("-") else text
        try:
            subprocess.run(
                [
                    "node",
                    "/usr/lib/node_modules/openclaw/node_modules/node-edge-tts/bin.js",
                    "-t", safe,
                    "-f", out_path,
                    "-v", voice,
                    "-l", lang,
                    "-r", rate,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            pass
        if not (os.path.exists(out_path) and os.path.getsize(out_path) > 1024):
            raise RuntimeError(f"edge-tts produced no audio for chunk ({len(text)} chars)")

    def _split_text(self, text, max_chars=600):
        """Split text into chunks <= max_chars at sentence boundaries."""
        import re
        sentences = re.split(r'(?<=[.!?\n])\s+', text.strip())
        chunks = []
        cur = ""
        for s in sentences:
            if not s:
                continue
            if len(cur) + len(s) + 1 <= max_chars:
                cur = (cur + " " + s).strip() if cur else s
            else:
                if cur:
                    chunks.append(cur)
                # If a single sentence is still too long, hard-split it.
                while len(s) > max_chars:
                    chunks.append(s[:max_chars])
                    s = s[max_chars:]
                cur = s
        if cur:
            chunks.append(cur)
        return chunks

    def _synthesize_mp3(self, text, voice=None, rate=None):
        """Run node-edge-tts -> mp3 bytes. Mirrors voice-note.sh.

        Splits long text at sentence boundaries to avoid edge-tts timeouts,
        then concatenates+remuxes the parts into a single MP3.
        """
        v = voice or os.environ.get("SIRI_TTS_VOICE") or "en-US-AriaNeural"
        r = rate or os.environ.get("SIRI_TTS_RATE") or "+0%"
        r = r.strip()
        if r and not r.endswith("%"):
            r = r + "%"
        if r and not (r.startswith("+") or r.startswith("-")):
            r = "+" + r
        lang = "-".join(v.split("-")[:2]) if "-" in v else "en-US"
        text = text[:6000]  # absolute cap; ~5 min of audio
        chunks = self._split_text(text)
        if not chunks:
            chunks = [text]

        tmpdir = tempfile.mkdtemp(prefix="siri-tts-")
        part_paths = []
        try:
            for i, chunk in enumerate(chunks):
                p = os.path.join(tmpdir, f"part_{i:03d}.mp3")
                self._synthesize_chunk(chunk, v, lang, r, p)
                part_paths.append(p)

            fixed_path = os.path.join(tmpdir, "out.wav")
            if len(part_paths) == 1:
                src = part_paths[0]
                concat_args = ["-i", src]
            else:
                listfile = os.path.join(tmpdir, "list.txt")
                with open(listfile, "w") as f:
                    for p in part_paths:
                        f.write(f"file '{p}'\n")
                concat_args = ["-f", "concat", "-safe", "0", "-i", listfile]

            subprocess.run(
                ["ffmpeg", "-y", *concat_args,
                 "-c:a", "pcm_s16le", "-ac", "1", "-ar", "24000",
                 fixed_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=120,
            )
            with open(fixed_path, "rb") as f:
                return f.read()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def do_POST(self):
        if self.path not in ("/", "/talk", "/talk-audio"):
            return self._send_json(404, {"error": "not_found"})

        # Accept token in header OR query string (Shortcuts is happier with headers,
        # but query lets you smoke-test from a browser bar in a pinch).
        token = self.headers.get("X-Siri-Token") or ""
        if token != SIRI_TOKEN:
            return self._send_json(401, {"error": "unauthorized"})

        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:
            return self._send_json(400, {"error": f"bad_json: {e}"})

        text = (body.get("text") or "").strip()
        if not text:
            return self._send_json(400, {"error": "missing_text"})

        session_key = body.get("session") or os.environ.get("SIRI_SESSION_KEY") or "siri-default"

        try:
            reply = call_openclaw(text, session_key)
        except urllib.error.HTTPError as e:
            return self._send_json(502, {
                "error": "gateway_http_error",
                "status": e.code,
                "detail": e.read().decode("utf-8", "replace")[:500],
            })
        except Exception as e:
            return self._send_json(502, {"error": f"gateway_error: {e}"})

        if self.path == "/talk-audio":
            voice = body.get("voice")
            rate = body.get("rate")
            try:
                mp3 = self._synthesize_mp3(reply, voice=voice, rate=rate)
            except subprocess.CalledProcessError as e:
                return self._send_json(502, {
                    "error": "tts_failed",
                    "detail": (e.stderr or b"").decode("utf-8", "replace")[:500],
                })
            except Exception as e:
                return self._send_json(502, {"error": f"tts_error: {e}"})
            # Best-effort: log this turn to the user's Discord DM channel
            self._log_to_discord(text, reply)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(mp3)))
            self.send_header("X-Reply-Text", reply.replace("\n", " ")[:500].encode("ascii", "replace").decode("ascii"))
            self.end_headers()
            self.wfile.write(mp3)
            return

        return self._send_json(200, {"reply": reply})


class TCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    print(f"siri-webhook: listening on 127.0.0.1:{PORT}, gateway={GATEWAY}", flush=True)
    with TCPServer(("127.0.0.1", PORT), Handler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
