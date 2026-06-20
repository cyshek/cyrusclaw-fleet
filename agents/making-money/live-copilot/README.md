# live-copilot

A real-time AI copilot for **live conversations** — sales calls, work meetings,
customer-success calls. It listens, transcribes, and surfaces tight
"what to say / what to know next" suggestions on a discreet overlay in
near-real-time.

This is the **legit-use cousin** of interview-cheat tools like Parakeet.ai:
same core loop (audio → STT → LLM → overlay), pointed at meetings & sales
instead of interviews — where there's no ethical baggage and companies actually
pay for it.

> Built 2026-06-04 by the `making-money` agent as a working proof-of-concept of
> the architecture. Runs end-to-end with **$0 and no API keys** via mock
> providers, so you can feel the UX and measure latency before paying for
> anything real.

## The loop

```
 ┌─────────┐   ┌──────┐   ┌──────────────────────────┐   ┌─────┐   ┌─────────┐
 │ audio   │──▶│ STT  │──▶│ ContextEngine            │──▶│ LLM │──▶│ overlay │
 │ (mic +  │   │      │   │  • rolling transcript win │   │     │   │ (discreet│
 │  system)│   │      │   │  • your domain docs       │   │     │   │  topmost)│
 └─────────┘   └──────┘   │  • trigger gating         │   └─────┘   └─────────┘
                          └──────────────────────────┘
```

The actual product value lives in the **ContextEngine**, not the LLM call:
*relevant context docs + a tight rolling window + smart trigger gating* = fast,
on-point suggestions that don't spam you on every sentence.

## Quickstart (zero keys, mock everything)

```bash
cd live-copilot
python3 src/main.py            # scripted demo call, suggestions print to terminal
python3 src/main.py --bench    # same, but prints latency JSON at the end
```

You'll watch a simulated B2B SaaS discovery call and see the copilot fire a
suggestion exactly when the prospect raises an objection or question.

## Go real (swap providers via env)

```bash
# Streaming STT via Deepgram + fast LLM via Groq:
export STT_PROVIDER=deepgram DEEPGRAM_API_KEY=...
export LLM_PROVIDER=groq      GROQ_API_KEY=...
python3 src/main.py

# or OpenAI:
export LLM_PROVIDER=openai OPENAI_API_KEY=... OPENAI_MODEL=gpt-4o-mini
```

Nothing else changes — the providers are behind a clean interface
(`src/providers.py`). Missing key → automatic graceful fallback to mock.

## Files

| file | role |
|---|---|
| `src/main.py` | orchestration loop, CLI, latency stats |
| `src/providers.py` | STT + LLM providers (mock / Deepgram / OpenAI / Groq) |
| `src/context_engine.py` | rolling window, doc loading, trigger gating |
| `src/overlay.py` | tkinter always-on-top overlay (+ notes on screen-share hiding) |
| `context/*.md` | YOUR domain docs (product sheet, objection playbook, etc.) |
| `context/demo_call.txt` | scripted call that drives MockSTT |

## What's real vs. stubbed

**Real & working now:** the full pipeline wiring, context loading, trigger
logic, latency measurement, provider abstraction, the OpenAI/Groq LLM client,
the Deepgram websocket scaffold.

**Stubbed (needs a real environment, not just a key):**
- **Live audio capture** — needs a real machine with mic + system-audio loopback
  (e.g. BlackHole on macOS, WASAPI loopback on Windows, PulseAudio monitor on
  Linux). The VM this was built on is headless, so MockSTT replays a script.
- **Screen-share-invisible overlay** — the OS calls are noted in `overlay.py`
  (`SetWindowDisplayAffinity` on Windows, `sharingType=.none` on macOS) but
  aren't wired since this box has no display.

See `../research/live-copilot-mvp-scope.md` for the build-vs-wrap decision,
latency budget, and cost-per-call-hour math.
