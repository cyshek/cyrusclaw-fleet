---
name: youtube-learn
description: "Consume any YouTube video from a datacenter/bot-walled IP: pull transcript + metadata, then study it to answer a question or extract what's taught."
metadata:
  {
    "openclaw":
      {
        "emoji": "🎓",
        "requires": { "bins": ["python3", "curl"] }
      }
  }
---

# YouTube Learn

Turn a YouTube link (or id) into something you can actually learn from — as a human would. Covers **what's said** (transcript), **what's shown on the cover** (thumbnail via vision), and **what's shown on screen** (frame extraction for visual-heavy content like coding demos, charts, trading setups).

Use when asked to watch, summarize, learn from, fact-check, or extract info from a video.

## Why a script
yt-dlp, innertube, and direct `timedtext` all return LOGIN_REQUIRED / Cloudflare from this datacenter IP. The script routes around that:
- **transcript** → kome.ai server-side API (fetches from residential IPs)
- **title/author/thumbnail** → YouTube oembed (no auth)
- **description/length/views** → watch-page regex with real UA + consent cookie

---

## Tier 1 — Transcript + Metadata (always works)

```bash
python3 skills/youtube-learn/scripts/yt_fetch.py "<url-or-id>"
```

Accepts `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`, `/live/`, bare 11-char id, and URLs with `?si=`/extra params.

Flags:
- `--json` — structured output for piping/saving
- `--no-transcript` — metadata only, faster

For long videos, save and work from file:
```bash
python3 skills/youtube-learn/scripts/yt_fetch.py "<url>" --json > /tmp/vid.json
```

**Read the transcript end to end** — don't skim. Auto-captions have no speaker labels/punctuation quirks; infer structure from context.

---

## Tier 2 — Thumbnail Vision (free, always works, run it by default)

The thumbnail often contains key text (titles, stats, on-screen labels) that's never spoken. **Run this for every video where visual info might matter.**

```bash
# Save thumbnail to workspace (image tool needs a workspace path, not /tmp)
VIDEO_ID="<11-char-id>"
curl -s "https://img.youtube.com/vi/${VIDEO_ID}/maxresdefault.jpg" \
  -o /home/azureuser/.openclaw/workspace/tmp_thumb_${VIDEO_ID}.jpg \
  || curl -s "https://img.youtube.com/vi/${VIDEO_ID}/hqdefault.jpg" \
  -o /home/azureuser/.openclaw/workspace/tmp_thumb_${VIDEO_ID}.jpg
```

Then pass to the `image` tool:
```
image(image="/home/azureuser/.openclaw/workspace/tmp_thumb_<ID>.jpg",
      prompt="What text and visual elements are shown? What is this video about?")
```

Clean up after:
```bash
rm /home/azureuser/.openclaw/workspace/tmp_thumb_${VIDEO_ID}.jpg
```

**Vision model is configured fleet-wide:** `imageModel = github-copilot/claude-opus-4.8` (with sonnet fallback). In long-lived sessions that cached "no image model", pass `model="github-copilot/claude-opus-4.8"` explicitly to the image tool.

---

## Tier 3 — Frame Extraction (for visual-heavy content: code demos, charts, trading setups)

When a video's real value is **what's shown on screen** (not just said), and the transcript + thumbnail aren't enough:

**Option A — Cookies (preferred, free):**
```bash
# Requires a cookies.txt export from a logged-in YouTube session (Cyrus's browser)
yt-dlp --cookies /path/to/cookies.txt \
  -f "worst[ext=mp4]" \
  -o /tmp/yt_video.%(ext)s \
  "https://www.youtube.com/watch?v=<ID>"

# Extract 1 frame every 5 seconds
ffmpeg -i /tmp/yt_video.* -vf fps=1/5 \
  /home/azureuser/.openclaw/workspace/tmp_frame_%03d.jpg -y

# Analyze frames with image tool — batch up to 20 at a time
# image(images=["/path/frame_001.jpg", "..."], prompt="What is shown?")

# Clean up
rm /tmp/yt_video.* /home/azureuser/.openclaw/workspace/tmp_frame_*.jpg
```

**Option B — Residential proxy (spend decision, money ≠ blocker):**
```bash
yt-dlp --proxy <residential-proxy-url> \
  -f "worst[ext=mp4]" \
  -o /tmp/yt_video.%(ext)s \
  "https://www.youtube.com/watch?v=<ID>"
# Then same ffmpeg + image tool flow as Option A
```

**When to escalate to Tier 3:**
- The video is a screen-recording, trading chart walkthrough, coding tutorial, or demo where visuals are the primary content
- The transcript refers to things being shown ("as you can see here", "look at this chart") without describing them
- You need to verify specific numbers, code, or patterns that appear on screen

---

## Workflow: Match Output to the Ask

| Ask | Approach |
|-----|----------|
| Summarize | Tier 1 → thesis, key points in order, caveats |
| Learn a method/tactic | Tier 1 + Tier 2 → concrete steps, specific numbers/tools/names, realistic outcomes demonstrated (not claimed) |
| What's shown on screen | Tier 2 (thumbnail) → if insufficient, Tier 3 (frames) |
| Fact-check / evaluate | Tier 1 → separate what's shown vs asserted; flag unverifiable hype; cross-check numbers with `web_search` before relying on them |
| Find specific info | Tier 1 → quote relevant lines; note rough position if timestamps matter |

**Key mindset:** Separate mechanism from marketing. A creator's profit claim may be inflated, but a real technique in the same video is still worth extracting. Match scrutiny to the claim's shape — cross-check numbers/code before acting on them, but don't flatten every video to "this is all bullshit" before actually looking.

---

## Notes

- **No captions** → transcript section says unavailable; metadata + thumbnail still return. Try the channel's other uploads or `web_search` for a written version.
- **kome.ai is the single point of failure for transcripts.** If it 4xx/5xx persistently, re-test the curl and consider a residential proxy for transcript too; don't silently fall back to bot-walled yt-dlp.
- **Respect the source:** attribute the creator; don't present their material as your own original research.
- **Exit codes:** 0 ok · 2 bad input · 3 transcript failed (metadata may still have printed).
