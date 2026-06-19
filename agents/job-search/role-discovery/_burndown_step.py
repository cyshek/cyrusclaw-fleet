#!/usr/bin/env python3
"""Read a plan, emit the i-th step as JSON the agent can dispatch.

Usage:
    _burndown_step.py <plan_path> <step_idx>
    _burndown_step.py <plan_path> count
    _burndown_step.py <plan_path> dump   # all steps brief

For browser.act.evaluate: produces an `inlined_fn` field where the
original `fn` is wrapped to immediately call with its embedded `arg`,
since the OpenClaw browser tool doesn't accept a separate arg.

For `ashby.maybe_solve_recaptcha_v3` (FIX 5 strict-Ashby reCAPTCHA v3):
emit a structured macro the chain worker dispatches as 3 calls:
    1. browser.act.evaluate(detect_fn)  -> {sitekey, page_url, enterprise}
    2. shell out: solver_cmd <<< <step-1 result JSON>  -> {ok, token, ...}
    3. browser.act.evaluate(inject_fn) with `arg` = token  -> {injected_into}
If ENABLE_CAPSOLVER != 1 (computed at dispatch time, with .env fallback),
emit kind='captcha_skip' so the worker just skips to the next step.
"""
import json, os, sys

# Resolve HERE from THIS module's own location (__file__), not sys.argv[0].
# sys.argv[0] is the *invoking* program's path, so under pytest (or any
# `import _burndown_step`) it pointed at the pytest/site-packages dir, which
# made sys.path.insert + _venv_python() look in the wrong place (venv python
# not found -> wrong interpreter for the solver subprocess). __file__ is
# correct regardless of how the module is run; fall back to argv0/cwd only if
# __file__ is somehow unavailable (frozen/exec contexts).
try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # pragma: no cover - __file__ missing (exec/frozen)
    HERE = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else os.getcwd()
sys.path.insert(0, HERE)

# Import the canonical JS payloads so we don't drift from
# captcha_presubmit.solve_and_inject_recaptcha_v3.
try:
    from captcha_presubmit import (
        JS_DETECT_RECAPTCHA_V3,
        JS_INJECT_RECAPTCHA_V3,
    )
except Exception:  # pragma: no cover
    # If the import fails the captcha macro becomes a clean skip rather than
    # crashing the dispatcher — the chain worker can keep going.
    JS_DETECT_RECAPTCHA_V3 = None
    JS_INJECT_RECAPTCHA_V3 = None

try:
    from capsolver_client import is_enabled as _capsolver_is_enabled
except Exception:  # pragma: no cover
    _capsolver_is_enabled = lambda: False  # noqa: E731


def _venv_python() -> str:
    """Best-effort path to the role-discovery venv python (matches what the
    chain worker should invoke for the solver subprocess)."""
    cand = os.path.join(HERE, ".venv", "bin", "python")
    return cand if os.path.exists(cand) else sys.executable


def _emit_captcha_step(idx: int, args: dict) -> dict:
    """Build the macro for `ashby.maybe_solve_recaptcha_v3`.

    The chain worker should:
      - If `kind == 'captcha_skip'`: skip to the next step (no work).
      - Else (`kind == 'captcha_recaptcha_v3'`):
          A. browser.act.evaluate(fn=detect_fn) -> save result as DETECT
          B. exec `solver_cmd` with DETECT piped to stdin, parse JSON ->
             save token as TOKEN. If ok=false, log + skip C and proceed
             to the next step (worker MUST still attempt Submit per
             per-role doctrine).
          C. browser.act.evaluate(fn=inject_fn, arg=TOKEN) -> verify
             injected_into includes at least one id.
    """
    drv = args.get("driver_exec") or {}
    kwargs = drv.get("kwargs") or {}
    fallback_sitekey = (
        kwargs.get("fallback_sitekey")
        or args.get("known_strict_sitekey")
        or "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"
    )
    page_url = kwargs.get("page_url") or args.get("page_url") or ""
    action = kwargs.get("action") or args.get("page_action") or "submit"
    min_score = kwargs.get("min_score", args.get("min_score", 0.7))
    enterprise = bool(kwargs.get("enterprise", args.get("enterprise", False)))

    enabled = bool(_capsolver_is_enabled())

    out = {
        "step_idx": idx,
        "tool": "ashby.maybe_solve_recaptcha_v3",
        "comment": (args.get("comment") or "")[:240],
    }

    if not enabled:
        out["kind"] = "captcha_skip"
        out["reason"] = (
            "ENABLE_CAPSOLVER!=1 or CAPSOLVER_API_KEY unset (after .env "
            "fallback). Worker should skip this step and proceed."
        )
        return out

    if not JS_DETECT_RECAPTCHA_V3 or not JS_INJECT_RECAPTCHA_V3:
        out["kind"] = "captcha_skip"
        out["reason"] = (
            "captcha_presubmit JS payloads unavailable at dispatch time; "
            "falling back to no-op skip to avoid crashing the chain."
        )
        return out

    py = _venv_python()
    script = os.path.join(HERE, "solve_recaptcha_v3.py")
    solver_cmd = [
        py, script,
        "--stdin",
        "--fallback-sitekey", fallback_sitekey,
        "--page-url", page_url,
        "--action", action,
        "--min-score", str(min_score),
    ]
    if enterprise:
        solver_cmd.append("--enterprise")

    # Wrap the canonical detect/inject JS into immediately-invokable form
    # for the OpenClaw browser tool's `fn` field (matches what the
    # browser.act.evaluate path already does for other steps).
    detect_fn = f"({JS_DETECT_RECAPTCHA_V3.strip()})()"
    # Inject takes a token arg; the worker calls browser.act.evaluate with
    # `fn` already wrapped: (FN)(<JSON-quoted-token>). We expose the raw
    # inject FN here and let the worker construct the inlined call so the
    # token (returned from the solver subprocess) is plugged in dynamically.
    inject_fn = JS_INJECT_RECAPTCHA_V3.strip()

    out.update({
        "kind": "captcha_recaptcha_v3",
        "enabled": True,
        "sitekey_fallback": fallback_sitekey,
        "page_url": page_url,
        "action": action,
        "min_score": min_score,
        "enterprise": enterprise,
        # Step A: detect.
        "detect_fn": detect_fn,
        # Step B: solve.
        "solver_cmd": solver_cmd,
        "solver_cwd": HERE,
        # Step C: inject. Worker should call:
        #   browser.act.evaluate(fn=f"({inject_fn})({json.dumps(token)})")
        "inject_fn": inject_fn,
        "inject_fn_template": "(" + inject_fn + ")(__TOKEN_JSON__)",
        # Doctrine: if solver fails, log + continue to Submit anyway.
        "on_solver_failure": "continue_to_submit",
    })
    return out


def main():
    plan_path = sys.argv[1]
    mode = sys.argv[2]
    d = json.load(open(plan_path))
    steps = d['steps']
    if mode == 'count':
        print(len(steps)); return
    if mode == 'dump':
        for i, s in enumerate(steps):
            tool = s.get('tool')
            args = s.get('args', {})
            cmt = (args.get('comment') or '')[:60]
            print(f"{i:2d} {tool} | {cmt}")
        return
    idx = int(mode)
    s = steps[idx]
    tool = s['tool']
    args = s.get('args', {}).copy()
    out = {"step_idx": idx, "tool": tool}
    if tool == 'browser.open':
        out['url'] = args['url']
    elif tool == 'sleep':
        out['ms'] = args.get('ms', 500)
    elif tool == 'browser.upload':
        # 2026-05-25 (upload regression FIX): emit `element` (or `ref`/`inputRef`)
        # so the dispatching agent calls browser.upload with the correct arg.
        # Plain `selector=` silently no-ops in OpenClaw's upload handler.
        # Accept either key from the plan for back-compat, but always emit `element`.
        if 'element' in args:
            out['element'] = args['element']
        elif 'inputRef' in args:
            out['inputRef'] = args['inputRef']
        elif 'ref' in args:
            out['ref'] = args['ref']
        elif 'selector' in args:
            # Legacy plan: promote selector -> element so the upload actually fires.
            out['element'] = args['selector']
        out['paths'] = args['paths']
    elif tool == 'browser.act.evaluate':
        fn = args['fn']
        if 'arg' in args:
            arg_json = json.dumps(args['arg'])
            # Inline: (FN)(ARG)
            inlined = f"({fn.strip()})({arg_json})"
        else:
            inlined = f"({fn.strip()})()"
        out['fn'] = inlined
        out['comment'] = args.get('comment','')
        if 'meta' in args:
            out['meta'] = args['meta']
    elif tool == 'ashby.maybe_solve_recaptcha_v3':
        # FIX 5 (strict-Ashby reCAPTCHA v3). Expand into a structured macro
        # the chain worker dispatches as detect + solve-shellout + inject.
        # When the env gate is off (default), emit a clean skip.
        out = _emit_captcha_step(idx, args)
    print(json.dumps(out))

if __name__ == '__main__':
    main()
