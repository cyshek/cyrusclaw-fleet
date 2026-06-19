#!/usr/bin/env python3
"""
live-copilot — a real-time AI copilot for live conversations (sales calls,
meetings, CS calls). Listens to the conversation, transcribes it, and surfaces
tight "what to say next" suggestions on a discreet overlay — in near-real-time.

This is the LEGIT-use cousin of interview-cheat tools like Parakeet.ai:
same core loop, pointed at meetings/sales instead.

    audio --> STT --> ContextEngine (rolling window + your docs) --> LLM --> Overlay

Runs end-to-end with ZERO paid keys via mock providers (scripted call + canned
reasoning), so you can feel the UX + measure latency before paying for anything.
Swap in real STT/LLM with env vars (see providers.py).

USAGE
    python3 src/main.py                 # mock everything, prints to terminal
    python3 src/main.py --overlay       # tkinter floating overlay (needs display)
    python3 src/main.py --bench         # latency benchmark mode, JSON out
    STT_PROVIDER=deepgram LLM_PROVIDER=groq python3 src/main.py   # real

The overlay is rendered in a separate always-on-top window. In a real deploy
you'd make it click-through + excluded from screen-share capture (OS-specific:
SetWindowDisplayAffinity on Windows, sharingType on macOS).
"""

from __future__ import annotations
import os
import sys
import time
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import get_stt, get_llm, Transcript, Suggestion  # noqa: E402
from context_engine import ContextEngine  # noqa: E402

SYSTEM_PROMPT = """You are a live conversation copilot for a {role}.
You hear a real-time transcript of a call. When the other party says something
that needs a response, you output ONE concise, immediately-speakable suggestion
(1-3 sentences max). Ground every answer in the user's context docs. Never invent
facts about their product/pricing. If you don't know, suggest a discovery question
instead. No preamble, no markdown — just the words they should say or know."""


class Stats:
    def __init__(self):
        self.latencies = []
        self.suggestions = 0
        self.start = time.time()

    def record(self, s: Suggestion):
        self.latencies.append(s.latency_ms)
        self.suggestions += 1

    def summary(self) -> dict:
        lat = sorted(self.latencies)
        def pct(p):
            if not lat:
                return 0
            return lat[min(len(lat) - 1, int(len(lat) * p))]
        return {
            "suggestions": self.suggestions,
            "wall_secs": round(time.time() - self.start, 1),
            "latency_ms_p50": pct(0.5),
            "latency_ms_p90": pct(0.9),
            "latency_ms_max": max(lat) if lat else 0,
        }


def run(overlay=False, bench=False, role="B2B SaaS sales rep"):
    here = os.path.dirname(os.path.abspath(__file__))
    ctx_dir = os.path.join(here, "..", "context")

    stt = get_stt()
    llm = get_llm()
    ctx = ContextEngine(os.path.abspath(ctx_dir))
    stats = Stats()
    system = SYSTEM_PROMPT.format(role=role)

    sink = None
    if overlay:
        try:
            from overlay import Overlay
            sink = Overlay()
            sink.start()
        except Exception as e:
            print(f"[overlay] unavailable ({e}); falling back to terminal")
            overlay = False

    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║  live-copilot  —  STT:{stt.name:<9} LLM:{llm.name:<9}            ║
║  role: {role:<52}║
║  (mock providers run with $0 + no keys; see providers.py)     ║
╚══════════════════════════════════════════════════════════════╝"""
    print(banner)

    def emit_suggestion(text_window: str):
        s = llm.suggest(system, ctx.docs, text_window)
        stats.record(s)
        if sink:
            sink.show(s)
        else:
            print(f"\n  💡 [{s.kind}] ({s.latency_ms}ms)\n     {s.text}\n")

    try:
        for t in stt.stream(None):
            if not t.is_final:
                # interim — show live transcription feel
                print(f"  …{t.speaker}: {t.text}", end="\r")
                continue
            tag = "THEM" if t.speaker == "them" else "ME  "
            print(f"  {tag}> {t.text}")
            ctx.add(t)
            if ctx.should_trigger(t):
                emit_suggestion(ctx.transcript_window())
    except KeyboardInterrupt:
        pass
    finally:
        if sink:
            sink.stop()

    summ = stats.summary()
    if bench:
        print("\nBENCH " + json.dumps(summ))
    else:
        print("\n" + "─" * 60)
        print(f"  session: {summ['suggestions']} suggestions in {summ['wall_secs']}s")
        print(f"  latency p50={summ['latency_ms_p50']}ms  "
              f"p90={summ['latency_ms_p90']}ms  max={summ['latency_ms_max']}ms")
        print("─" * 60)
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", action="store_true", help="floating tkinter overlay")
    ap.add_argument("--bench", action="store_true", help="benchmark mode, JSON output")
    ap.add_argument("--role", default="B2B SaaS sales rep")
    args = ap.parse_args()
    run(overlay=args.overlay, bench=args.bench, role=args.role)


if __name__ == "__main__":
    main()
