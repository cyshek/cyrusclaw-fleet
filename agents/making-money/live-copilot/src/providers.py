"""
Provider abstractions for the live-copilot loop.

Design goal: the whole pipeline runs with ZERO paid keys (mock providers),
and you swap in real STT/LLM by setting env vars + dropping in a key.
Nothing else in the app changes.

    STT:  MockSTT | DeepgramSTT (real, streaming)
    LLM:  MockLLM | OpenAILLM | GroqLLM (OpenAI-compatible)

Selection is driven by env:
    STT_PROVIDER = mock | deepgram      (default: mock)
    LLM_PROVIDER = mock | openai | groq (default: mock)
    DEEPGRAM_API_KEY, OPENAI_API_KEY, GROQ_API_KEY
"""

from __future__ import annotations
import os
import time
import json
import random
from dataclasses import dataclass
from typing import Iterator, List, Dict, Optional, Callable


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #
@dataclass
class Transcript:
    """A chunk of recognized speech."""
    text: str
    speaker: str          # "them" | "me" | "unknown"
    is_final: bool
    ts: float


@dataclass
class Suggestion:
    """An LLM-generated live suggestion."""
    text: str
    latency_ms: int
    kind: str = "answer"  # answer | objection | fact | next_question


# --------------------------------------------------------------------------- #
# STT providers
# --------------------------------------------------------------------------- #
class BaseSTT:
    name = "base"

    def stream(self, audio_source: Iterator[bytes]) -> Iterator[Transcript]:
        raise NotImplementedError


class MockSTT(BaseSTT):
    """
    Emits a scripted conversation so the rest of the pipeline can be exercised
    end-to-end with no microphone and no API key. Reads a script file of lines:
        them: <text>
        me: <text>
    and yields them with realistic pacing.
    """
    name = "mock"

    def __init__(self, script_path: str, realtime: bool = True, speed: float = 1.0):
        self.script_path = script_path
        self.realtime = realtime
        self.speed = speed

    def stream(self, audio_source=None) -> Iterator[Transcript]:
        with open(self.script_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
        for ln in lines:
            if ":" not in ln:
                continue
            spk, text = ln.split(":", 1)
            spk = spk.strip().lower()
            text = text.strip()
            speaker = "them" if spk in ("them", "client", "interviewer", "prospect") else "me"
            # Simulate speaking time: ~3 words/sec
            words = max(1, len(text.split()))
            speak_secs = (words / 3.0) / self.speed
            if self.realtime:
                # emit a couple interim partials then final
                partial_words = words // 2 or 1
                interim = " ".join(text.split()[:partial_words])
                time.sleep(min(speak_secs * 0.5, 1.2))
                yield Transcript(interim, speaker, is_final=False, ts=time.time())
                time.sleep(min(speak_secs * 0.5, 1.2))
            yield Transcript(text, speaker, is_final=True, ts=time.time())


class DeepgramSTT(BaseSTT):
    """
    Real streaming STT via Deepgram's websocket API.
    Requires DEEPGRAM_API_KEY and the `websocket-client` package (already present).
    audio_source must yield raw linear16 PCM @ 16kHz mono.

    This is wired but only activates when STT_PROVIDER=deepgram + key set,
    so it's safe to ship on a keyless box.
    """
    name = "deepgram"

    def __init__(self, api_key: str, model: str = "nova-2", sample_rate: int = 16000):
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate

    def stream(self, audio_source: Iterator[bytes]) -> Iterator[Transcript]:
        import threading
        import queue
        import websocket  # websocket-client

        url = (
            "wss://api.deepgram.com/v1/listen"
            f"?model={self.model}&encoding=linear16&sample_rate={self.sample_rate}"
            "&channels=1&interim_results=true&punctuate=true&endpointing=200"
        )
        out: "queue.Queue[Optional[Transcript]]" = queue.Queue()

        def on_message(ws, message):
            data = json.loads(message)
            try:
                alt = data["channel"]["alternatives"][0]
            except (KeyError, IndexError):
                return
            text = alt.get("transcript", "").strip()
            if not text:
                return
            out.put(Transcript(text, "them", bool(data.get("is_final")), time.time()))

        def on_error(ws, err):
            out.put(None)

        def on_close(ws, *a):
            out.put(None)

        ws = websocket.WebSocketApp(
            url,
            header={"Authorization": f"Token {self.api_key}"},
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        def pump_audio():
            ws.run_forever()  # placeholder; real impl interleaves sends

        threading.Thread(target=lambda: ws.run_forever(), daemon=True).start()
        # Feed audio
        def feeder():
            for chunk in audio_source:
                try:
                    ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
                except Exception:
                    break
            try:
                ws.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                pass
        threading.Thread(target=feeder, daemon=True).start()

        while True:
            item = out.get()
            if item is None:
                break
            yield item


def get_stt() -> BaseSTT:
    provider = os.getenv("STT_PROVIDER", "mock").lower()
    if provider == "deepgram":
        key = os.getenv("DEEPGRAM_API_KEY")
        if not key:
            print("[providers] DEEPGRAM_API_KEY missing -> falling back to MockSTT")
        else:
            return DeepgramSTT(key)
    script = os.getenv("MOCK_SCRIPT", os.path.join(os.path.dirname(__file__), "..", "context", "demo_call.txt"))
    return MockSTT(os.path.abspath(script))


# --------------------------------------------------------------------------- #
# LLM providers
# --------------------------------------------------------------------------- #
class BaseLLM:
    name = "base"

    def suggest(self, system: str, context: str, transcript: str) -> Suggestion:
        raise NotImplementedError


class MockLLM(BaseLLM):
    """
    Deterministic-ish canned reasoning so you can SEE the loop work and judge
    latency/UX without burning tokens. It pattern-matches the last prospect line.
    """
    name = "mock"

    # (trigger keywords...) -> (response, kind). First match wins; order matters.
    CANNED = [
        (("price", "pricing", "budget", "cost", "expensive", "tight"),
         ("Reframe to ROI: \"Totally fair on budget. A 40-seat team usually sees payback "
          "in ~6 weeks because it kills 2 manual handoffs per ticket — want me to walk the math?\" "
          "Then anchor Growth at $24/user.",
          "objection")),
        (("zapier", "competitor", "already use", "why would we switch", "switch"),
         ("Differentiate on the axis you win: \"Zapier is one-direction polling with per-task "
          "pricing that balloons. We do native two-way write-back, sub-second, field-level mapping "
          "UI — no zaps to maintain.\"",
          "objection")),
        (("native", "middleware", "integrat"),
         ("Yes — native two-way sync with Salesforce + HubSpot, no middleware, no Zapier. "
          "Offer to show the field-mapping screen live.", "fact")),
        (("security", "pii", "compliance", "soc"),
         ("SOC 2 Type II, AES-256 at rest + TLS 1.3 in transit, no training on customer data, "
          "plus field-level PII redaction. Offer the trust-center link.", "fact")),
        (("think about it", "think about", "talk to my team", "need to think"),
         ("Soft-close: \"Makes total sense. What's the one thing that, if it were answered, "
          "would make this a clear yes for you and the team?\"", "next_question")),
        (("different", "others", "how are you"),
         ("Lead with the wedge: \"One line — we're the only one doing native two-way sync "
          "with no middleware. Everyone else is one-way or needs Zapier glue.\" Then ask which "
          "CRM + help desk they run.", "answer")),
    ]

    def suggest(self, system: str, context: str, transcript: str) -> Suggestion:
        t0 = time.time()
        last = transcript.strip().splitlines()[-1].lower() if transcript.strip() else ""
        out = None
        kind = "answer"
        for keys, (resp, k) in self.CANNED:
            if any(key in last for key in keys):
                out, kind = resp, k
                break
        if out is None:
            out = ("Mirror their last point, then ask a discovery question to keep them talking. "
                   "(No canned match — a real LLM would answer from your context docs here.)")
            kind = "next_question"
        # simulate model think time
        time.sleep(random.uniform(0.25, 0.6))
        return Suggestion(out, int((time.time() - t0) * 1000), kind)


class OpenAICompatLLM(BaseLLM):
    """
    Works with any OpenAI-compatible chat endpoint (OpenAI, Groq, etc.).
    Activates only when a key is present.
    """
    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def suggest(self, system: str, context: str, transcript: str) -> Suggestion:
        import urllib.request
        t0 = time.time()
        body = {
            "model": self.model,
            "temperature": 0.3,
            "max_tokens": 120,
            "messages": [
                {"role": "system", "content": system + "\n\n# YOUR CONTEXT DOCS\n" + context},
                {"role": "user", "content":
                    "LIVE TRANSCRIPT (most recent last):\n" + transcript +
                    "\n\nGive me ONE tight, immediately-usable suggestion for what to say next. "
                    "No preamble."},
            ],
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        text = data["choices"][0]["message"]["content"].strip()
        return Suggestion(text, int((time.time() - t0) * 1000))


def get_llm() -> BaseLLM:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return OpenAICompatLLM("openai", "https://api.openai.com/v1", key,
                                   os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        print("[providers] OPENAI_API_KEY missing -> falling back to MockLLM")
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY")
        if key:
            return OpenAICompatLLM("groq", "https://api.groq.com/openai/v1", key,
                                   os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        print("[providers] GROQ_API_KEY missing -> falling back to MockLLM")
    return MockLLM()
