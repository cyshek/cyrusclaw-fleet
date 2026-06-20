"""Unit tests for _ashby_runner.wait_autofill_settle (chain_p6, 2026-06-03).

Verifies the autofill-settle wait returns clean once the "parsing" banner is gone
AND the DOM signature stabilizes, and returns False (proceed-anyway) on timeout.
Uses a scripted FakePage that drives page.evaluate() return values per call — no
live browser. The helper must:
  - keep waiting while the parsing banner is present,
  - keep waiting while the input-value signature keeps changing,
  - return True after quiet_ms of (no banner + stable signature),
  - return False if the deadline passes without a clean settle.
"""
import _ashby_runner


class FakePage:
    def __init__(self, script):
        # script: list of (busy_bool, sig_str) tuples consumed per (busy, sig) pair.
        self._script = list(script)
        self._i = 0

    def evaluate(self, js, arg=None):
        # The helper calls evaluate twice per loop: first the busy regex check,
        # then the DOM signature. We serve from the script in (busy, sig) order.
        step = self._script[min(self._i // 2, len(self._script) - 1)]
        busy, sig = step
        is_busy_call = "parsing your resume" in js or "RegExp" in js
        self._i += 1
        return busy if is_busy_call else sig

    def wait_for_timeout(self, ms):
        # no real sleep; advance virtual time via monkeypatched time in tests
        pass


def test_settle_clean_after_stable(monkeypatch):
    # virtual clock
    t = {"now": 1000.0}
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: t["now"])

    # Banner clears immediately; signature stable from the start. Each loop the
    # wait_for_timeout would advance time; emulate by bumping the clock.
    page = FakePage([(False, "10:120")] * 50)
    orig_wait = page.wait_for_timeout
    def _wait(ms):
        t["now"] += ms / 1000.0
    page.wait_for_timeout = _wait

    assert _ashby_runner.wait_autofill_settle(page, max_ms=12000, quiet_ms=1500) is True


def test_settle_waits_through_busy_then_settles(monkeypatch):
    t = {"now": 2000.0}
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: t["now"])

    # First few polls: busy banner present (changing sig); then clean + stable.
    script = [(True, "10:50"), (True, "10:80")] + [(False, "10:120")] * 50
    page = FakePage(script)
    def _wait(ms):
        t["now"] += ms / 1000.0
    page.wait_for_timeout = _wait

    assert _ashby_runner.wait_autofill_settle(page, max_ms=20000, quiet_ms=1000) is True


def test_settle_timeout_when_never_quiet(monkeypatch):
    t = {"now": 3000.0}
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: t["now"])

    # Banner never clears -> never settles -> returns False on deadline.
    page = FakePage([(True, "10:50")] * 200)
    def _wait(ms):
        t["now"] += ms / 1000.0
    page.wait_for_timeout = _wait

    assert _ashby_runner.wait_autofill_settle(page, max_ms=3000, quiet_ms=1000) is False


def test_settle_never_raises_on_evaluate_error(monkeypatch):
    t = {"now": 4000.0}
    import time as _time
    monkeypatch.setattr(_time, "time", lambda: t["now"])

    class BrokenPage:
        def evaluate(self, js, arg=None):
            raise RuntimeError("boom")
        def wait_for_timeout(self, ms):
            t["now"] += ms / 1000.0

    # Must not raise; returns False on timeout.
    assert _ashby_runner.wait_autofill_settle(BrokenPage(), max_ms=1500, quiet_ms=500) is False
