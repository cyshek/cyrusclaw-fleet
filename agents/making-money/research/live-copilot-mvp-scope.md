# live-copilot — MVP scope, latency budget & cost-per-call-hour

_Built 2026-06-04 by `making-money`. Pricing pulled live from deepgram.com/pricing
and groq.com/pricing the same day; verify before quoting to anyone._

## 1. What the MVP actually is

A desktop app (Electron or native) that, during a live call:
1. captures **system audio** (the other party) + optionally **mic** (you),
2. streams to a **real-time STT** provider,
3. maintains a **rolling transcript + your context docs**,
4. fires an **LLM suggestion** only when the other party asks/objects,
5. renders it on a **discreet, screen-share-invisible overlay**.

The working proof-of-concept of steps 2–4 is in `../live-copilot/` and runs today
with mock providers. Steps 1 and 5 need a real desktop OS (this build box is a
headless VM).

## 2. Build vs. wrap

| Layer | Decision | Why |
|---|---|---|
| STT | **Wrap** (Deepgram / AssemblyAI) | Real-time diarized STT is a solved, cheap commodity. Building your own is insane. |
| LLM | **Wrap** (Groq for speed, OpenAI/Anthropic for quality) | Obvious. |
| Audio capture | **Build thin native layer** | This is the actual hard part + where most wrappers are janky. Cross-platform loopback is the moat-ish skill. |
| Overlay / screen-share hiding | **Build native** | `SetWindowDisplayAffinity` (Win), `sharingType=.none` (mac). Small but differentiating. |
| Context/RAG + trigger logic | **Build (it's the product)** | This is where vertical value lives. Don't outsource it. |

Verdict: **wrap the AI, build the desktop plumbing + the context brain.** ~80% of
the work is steps 1 and 5, *not* the AI.

## 3. Latency budget — target <2s "they stop talking → suggestion on screen"

| Stage | Budget | Notes |
|---|---|---|
| STT finalization (endpointing) | 200–400 ms | Deepgram `endpointing=200` |
| Trigger decision | <5 ms | local keyword/heuristic gate |
| LLM time-to-first-token | 300–600 ms | Groq is the unlock here (394–1000 TPS) |
| LLM generation (≤120 tokens) | 150–400 ms | short answers only; cap max_tokens |
| Render | <50 ms | |
| **Total** | **~0.8–1.5 s** | Feels live. OpenAI gpt-4o-mini pushes p90 toward ~2.5s — fine for meetings, borderline for fast sales banter. **Groq is the right default.** |

Measured in the mock loop today: p50 **533 ms**, p90 **587 ms** (mock LLM think
time only — real STT+LLM adds the budget above, but the orchestration overhead is
negligible).

## 4. Cost per call-hour (the number that decides the business)

**Assumptions per 1 hour of live call:**
- STT: 60 min of streaming audio.
- LLM: a suggestion fires roughly **every ~30s of "their" talk** → ~40–60 calls/hr.
  Each call: ~1.5k input tokens (system + context docs + rolling window) + ~120 output.
  → ~60–90k input + ~7k output tokens/hr.

### STT (Deepgram, live pay-as-you-go rates 2026-06-04)
- Nova-3 Monolingual streaming: **$0.0048/min** → **$0.29/hr**
- Nova-3 Multilingual: $0.0058/min → $0.35/hr
- (Flux English $0.0065/min → $0.39/hr)

### LLM (live Groq rates 2026-06-04)
| Model | In $/M | Out $/M | ~Cost/hr (75k in + 7k out) |
|---|---|---|---|
| **GPT-OSS-120B** | $0.15 | $0.60 | **~$0.015/hr** |
| Llama 4 Scout | $0.11 | $0.34 | ~$0.011/hr |
| Llama 3.3 70B | $0.59 | $0.79 | ~$0.050/hr |

*(OpenAI gpt-4o-mini ~$0.15/$0.60 per M lands near GPT-OSS-120B; gpt-4o ~10–20×.)*

### All-in COGS per call-hour
**STT (~$0.30) + LLM (~$0.02–0.05) ≈ $0.32–0.35 / call-hour.**

STT dominates — the LLM is rounding error. To cut COGS, the lever is STT
(self-host Whisper-turbo on a GPU at scale, or batch/cheaper tiers), not the LLM.

### Margin math
- A sales rep on calls ~4 hrs/day × 20 days = **80 call-hrs/mo** → COGS **~$26/user/mo**.
- Sell at **$40–80/user/mo** (in line with Gong/Cluely-tier per-seat) → **60–67% gross margin** even before volume STT discounts. Healthy SaaS.
- Light users (meetings only, ~20 hrs/mo) → COGS ~$7 → fat margin.

**Conclusion: the unit economics work.** It's a real SaaS, not a money-loser.

## 5. Smallest shippable MVP (what I'd build first)

1. macOS-first desktop app (single OS keeps audio/overlay tractable; BlackHole or
   CoreAudio tap for loopback).
2. Deepgram streaming STT + Groq GPT-OSS-120B.
3. One vertical's context pack baked in (pick ONE: e.g. B2B SaaS AE objection
   handling) — not a generic empty box.
4. Screen-share-invisible overlay.
5. Manual context-doc upload (drag in your product sheet / playbook). RAG later.

Explicitly **defer**: multi-OS, CRM integrations, team analytics, auto-meeting-join
bots. Those are v2 once a wedge user loves v1.

## 6. Honest risk read

- **Crowded top end.** Cluely (huge funding, "everything" copilot) + Gong own the
  generic and enterprise ends. A solo build can't win "general live AI assistant."
- **The wedge is verticalization + the desktop craft.** Win one narrow ICP whose
  context is specific and whose reps live on calls (insurance, SDR teams,
  technical pre-sales, CS renewals). Generic loses; specific can sneak in.
- **Platform/ToS risk** is low for meetings/sales (vs. interview cheating, which
  invites pushback). This is the clean side of the category.
- **Distribution, not tech, is the hard part.** The build is a few weeks; getting
  10 reps in one vertical to live in it daily is the real game.

See `live-copilot-landscape.md` for the competitive/pricing teardown.
