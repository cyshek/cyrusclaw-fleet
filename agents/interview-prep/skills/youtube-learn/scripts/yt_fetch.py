#!/usr/bin/env python3
"""Fetch a YouTube video's transcript + metadata from a bot-walled datacenter IP.

Usage:
    python yt_fetch.py <url-or-id> [--no-transcript] [--json]

Strategy (datacenter-IP-safe, verified 2026-06-03):
  - video id: parsed from any common URL form
  - title/author/thumbnail: youtube oembed (no auth, residential-clean)
  - description: watch page shortDescription regex (real UA + consent cookie)
  - transcript: kome.ai server-side API (fetches from residential IPs)
yt-dlp / innertube / direct timedtext are bot-walled from this VM -> not used.

Exit codes: 0 ok, 2 bad input, 3 transcript failed (metadata may still print).
"""
import json
import re
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def extract_id(s: str) -> str | None:
    s = s.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    try:
        u = urllib.parse.urlparse(s)
    except Exception:
        return None
    if u.hostname in ("youtu.be",):
        cand = u.path.lstrip("/").split("/")[0]
        return cand if re.fullmatch(r"[A-Za-z0-9_-]{11}", cand) else None
    if u.hostname and "youtube" in u.hostname:
        qs = urllib.parse.parse_qs(u.query)
        if "v" in qs and re.fullmatch(r"[A-Za-z0-9_-]{11}", qs["v"][0]):
            return qs["v"][0]
        m = re.search(r"/(shorts|embed|live|v)/([A-Za-z0-9_-]{11})", u.path)
        if m:
            return m.group(2)
    m = re.search(r"([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else None


def _get(url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 30) -> str:
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_meta(vid: str) -> dict:
    out = {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}
    try:
        o = json.loads(_get(
            "https://www.youtube.com/oembed?url="
            + urllib.parse.quote(out["url"], safe="") + "&format=json"))
        out["title"] = o.get("title")
        out["author"] = o.get("author_name")
        out["channel_url"] = o.get("author_url")
        out["thumbnail"] = o.get("thumbnail_url")
    except Exception as e:
        out["meta_error"] = str(e)
    try:
        page = _get(out["url"], headers={"User-Agent": UA, "Cookie": "CONSENT=YES+1; SOCS=CAI;"})
        m = re.search(r'"shortDescription":"(.*?)","isCrawlable"', page)
        if m:
            out["description"] = json.loads('"' + m.group(1) + '"')
        m = re.search(r'"lengthSeconds":"(\d+)"', page)
        if m:
            out["length_seconds"] = int(m.group(1))
        m = re.search(r'"viewCount":"(\d+)"', page)
        if m:
            out["view_count"] = int(m.group(1))
    except Exception as e:
        out.setdefault("meta_error", str(e))
    return out


def fetch_transcript(vid: str) -> str | None:
    body = json.dumps({"video_id": vid, "format": True}).encode()
    try:
        raw = _get("https://kome.ai/api/transcript",
                   headers={"User-Agent": UA, "Content-Type": "application/json"},
                   data=body, timeout=60)
        t = json.loads(raw).get("transcript")
        return t or None
    except Exception:
        return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print("usage: yt_fetch.py <url-or-id> [--no-transcript] [--json]", file=sys.stderr)
        return 2
    vid = extract_id(args[0])
    if not vid:
        print(f"could not extract video id from: {args[0]}", file=sys.stderr)
        return 2

    meta = fetch_meta(vid)
    transcript = None
    if "--no-transcript" not in flags:
        transcript = fetch_transcript(vid)

    if "--json" in flags:
        meta["transcript"] = transcript
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0 if (transcript or "--no-transcript" in flags) else 3

    print(f"# {meta.get('title','(no title)')}")
    print(f"Channel : {meta.get('author','?')}  {meta.get('channel_url','')}")
    if meta.get("length_seconds"):
        s = meta["length_seconds"]
        print(f"Length  : {s//60}m{s%60:02d}s")
    if meta.get("view_count"):
        print(f"Views   : {meta['view_count']:,}")
    print(f"URL     : {meta['url']}")
    if meta.get("description"):
        print("\n## Description\n" + meta["description"])
    if "--no-transcript" not in flags:
        if transcript:
            print("\n## Transcript\n" + transcript)
        else:
            print("\n## Transcript\n(unavailable — no captions, or kome.ai failed)")
    return 0 if (transcript or "--no-transcript" in flags) else 3


if __name__ == "__main__":
    sys.exit(main())
