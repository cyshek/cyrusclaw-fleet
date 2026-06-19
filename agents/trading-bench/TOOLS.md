# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

### YouTube (youtube-learn skill)

Local skill at `skills/youtube-learn/` (copied from making-money 2026-06-03, now self-hosted — no cross-agent dependency). This VM's datacenter IP is bot-walled by Google (yt-dlp / innertube / timedtext all return LOGIN_REQUIRED), so use this script, not curl-the-captions.

```bash
python3 skills/youtube-learn/scripts/yt_fetch.py "<url-or-id>" [--json] [--no-transcript]
```
- transcript → kome.ai server-side API · title/meta → oembed + watch-page regex
- Smoke-tested 2026-06-03: pulled 42,946-char transcript clean on `6MC1XqZSltw`. exit 0.
- Exit codes: 0 ok · 2 bad input · 3 transcript failed (metadata may still print).

**kome.ai fallback curl** (documented escape hatch — kome.ai is the single point of failure for transcripts; if the script breaks, this is the raw call it makes):
```bash
curl -s -X POST https://kome.ai/api/transcript \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: Mozilla/5.0' \
  -d '{"video_id":"<11-char-id>","format":true}' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("transcript",""))'
```
If kome.ai 4xx/5xx persistently: re-test this curl, consider a residential proxy. Do NOT silently fall back to bot-walled yt-dlp. Auto-captions garble proper nouns/version numbers — sanity-check names.

---

Add whatever helps you do your job. This is your cheat sheet.

---

### Free market-data endpoints (verified from THIS VM, 2026-06-08)

This VM is a datacenter IP. Bot-walling is **source- and symbol-specific**, not blanket — TEST, don't assume:

- **Daily price history (stocks/ETFs/indices) → Yahoo v8 chart API. WORKS from our IP.** `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?period1=0&period2=9999999999&interval=1d&events=div,split` with a **browser User-Agent**. Returns JSON: `timestamp[]`, `indicators.quote[0]` (OHLCV), `indicators.adjclose[0].adjclose[]` (split+div-adjusted — USE THIS; leveraged ETFs split constantly so raw close is garbage), `events.splits`. Re-confirmed 200 on TQQQ/UPRO/SOXL/^GSPC. Earliest: ^GSPC 1970, ^NDX 1985, SPY 1993, QQQ 1999, leveraged ETFs from inception (UPRO 2009-06, TQQQ/SOXL 2010, SSO/QLD real-2x 2006-06, SPXL/TECL 2008-11/12). Personal/research use only — don't redistribute. Cache to disk once; be polite; back off to `query2` if 429s appear.
  - **Caveat:** the `^VIX` symbol specifically has 429'd here before (transient/symbol-rate-limited). For the VIX-complex use **CBOE CDN** (`cdn.cboe.com/api/global/us_indices/daily_prices/<IDX>_History.csv`) — strictly better, keyless, VIX/SKEW→1990, VVIX→2006, VIX3M→2009-09. (Already wrapped in `runner/cboe_cache.py`.)
  - Keyed fallbacks if Yahoo degrades: Tiingo (free token, ~50 sym/hr), Alpha Vantage (free key, 25 req/day). Stooq is now CAPTCHA/apikey-gated → not headless-automatable.
- **Fundamentals / earnings (point-in-time) → SEC EDGAR `data.sec.gov`. WORKS, but 403 without a declared `User-Agent` header (200 with one).** `companyconcept` / `companyfacts` / `xbrl/frames` JSON. Every datapoint carries a `filed` date + `accn` → native PIT (anti-lookahead rule: per (concept,fy,fp) take the latest-`filed` row ≤ as-of date; restatements are new later-filed rows). Earliest ~mid-2009 (XBRL mandate). Public domain.
- **FRED → use the KEYED API** `api.stlouisfed.org/fred/series/observations` (free instant key). `fredgraph.csv` is Akamai-bot-protected + flaky from this VM (returns stale cached data) — do NOT use it. Wrapped in `runner/fred_cache.py`.
- **Confirmed-paid (no free tier reaches backtest depth):** analyst estimate-REVISION *history* (Finnhub/Tiingo/SimFin gated, Zacks/IBES commercial) — the one genuine funded-upgrade. Free workaround: Nasdaq `earnings-forecast` exposes a current 4-week-revision snapshot to self-collect forward, or pivot to PEAD (earnings-surprise drift, free via EDGAR×Nasdaq).

## Related

- [Agent workspace](/concepts/agent-workspace)

---

### Consuming what's SHOWN in a video (not just the transcript) — frame/visual access

Default youtube-learn = transcript + metadata (the **spoken** content, end-to-end). For videos whose value is **visual** (screen-recordings, charts, on-screen text/UI, demos), two tiers:

**TIER 1 — thumbnail + vision (WORKS NOW, no auth, no proxy).** The cover frame is always fetchable and often carries text the transcript lacks (e.g. shZwbIRtObE's title card "This Claude Skill makes $1500/day while you sleep" — "while you sleep" was ONLY in the visual, never spoken):
```bash
curl -s -o /tmp/thumb.jpg "https://i.ytimg.com/vi/<VIDEO_ID>/maxresdefault.jpg"   # 1280x720; falls back to hqdefault.jpg (480x360) for shorts
# then copy into an ALLOWED dir (the image tool refuses /tmp) and run the image tool:
cp /tmp/thumb.jpg ./_f.jpg && # image tool on ./_f.jpg  (vision now configured fleet-wide → agents.defaults.imageModel = github-copilot/claude-opus-4.8)
```
- **Image tool gotchas (learned 2026-06-13):** (1) only reads paths under an ALLOWED dir — workspace is fine, `/tmp` is NOT; copy in first. (2) `github-copilot/gpt-4o` is NOT supported via Copilot's Responses API (400) — use `claude-opus-4.8` (native vision, works). (3) If a bare `image` call says "No image model is configured" inside a long-lived session, that session cached its config at spawn — pass `model="github-copilot/claude-opus-4.8"` explicitly, or it resolves fine in any fresh session.

**TIER 2 — actual video frames (BLOCKED from this datacenter IP; needs a residential path).** `yt-dlp` from this VM returns "Sign in to confirm you're not a bot" (verified 2026-06-13) — the download path is bot-walled like everything else. To pull real frames when a video genuinely needs it:
- **(a) cookies:** `yt-dlp --cookies <cookies.txt> -f worst -o /tmp/v.%(ext)s "<url>"` using a logged-in YouTube cookie export (Cyrus's, when present), then `ffmpeg -i /tmp/v.* -vf fps=1/5 /tmp/frame_%03d.jpg` → image-tool the frames.
- **(b) residential proxy:** `yt-dlp --proxy <residential-proxy-url> ...` (same downstream ffmpeg→vision). Proxy is a spend DECISION, not a Cyrus-gate (money≠blocker rule) — wire it if a video's visual content is worth it.
- Don't silently fall back to bot-walled yt-dlp and report failure; pick (a) or (b).

## YouTube Video Consumption

### Transcript
```bash
python3 skills/youtube-learn/scripts/yt_fetch.py "<youtube_url_or_id>"
```
Returns title + full transcript. Works from datacenter IP via kome.ai residential proxy.

### Consuming what's SHOWN in a video
Vision is configured fleet-wide (imageModel = github-copilot/claude-opus-4.8). The thumbnail of any YouTube video is fetchable + readable via the image tool — it sometimes carries text/info the transcript never mentions.

Route:
1. Fetch thumbnail: `https://img.youtube.com/vi/<VIDEO_ID>/maxresdefault.jpg` (fall back to `hqdefault.jpg`)
2. Pass to image tool for analysis

Gotchas:
- image tool requires a workspace path (not /tmp) — save the thumbnail to workspace first if needed
- In a long-lived session that cached "no image model" at spawn, pass model="github-copilot/claude-opus-4.8" explicitly; fresh sessions resolve the default correctly
