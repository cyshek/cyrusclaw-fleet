# ElevenLabs 938 — ALREADY-APPLIED (Ashby 90-day dedup) -> marked applied

- **Role:** Enterprise Solutions Engineer - North America
- **Company:** ElevenLabs (Ashby)
- **Apply URL:** https://jobs.ashbyhq.com/elevenlabs/275f43d0-b62d-401d-830c-7c1ac0e688
- **Status:** applied (auto-residential, 2026-06-11)

## Confirmation
- Ashby server returned: "you have applied for this position in the last 90 days, you cannot submit" — a DUPLICATE-BLOCK at the dedup gate, NOT a location bounce.
- This row PASSED the location step (chain_p14) all the way to dedup => a prior submit was real => correctly counted as applied.

## Note
STATUS.md backfilled by parent. The earlier (prior) submit was genuine; this retry confirmed it server-side via the 90-day dedup message.
