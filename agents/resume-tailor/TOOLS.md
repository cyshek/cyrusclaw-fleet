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

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)

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
