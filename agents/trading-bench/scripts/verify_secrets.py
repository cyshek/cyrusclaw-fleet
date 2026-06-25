#!/usr/bin/env python3
"""verify_secrets.py — post-rotation sanity checks. Prints NO secret values.

Checks:
  * Alpaca .env parses, paper-host enforced, key/secret non-empty (lengths only).
  * FRED_API_KEY present + plausible length.
Exit 0 if all parse; non-zero if Alpaca config fails to load.
Run from the workspace root:  python3 scripts/verify_secrets.py
"""
import os
import pathlib
import sys

WS = pathlib.Path(__file__).resolve().parent.parent


def _read_env(path: pathlib.Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    sys.path.insert(0, str(WS))
    rc = 0
    print("=== Post-rotation verification (no secret values printed) ===")

    try:
        from runner.broker_alpaca import AlpacaConfig
        cfg = AlpacaConfig.from_env()
        host_ok = "paper-api.alpaca.markets" in cfg.trade_base
        print(
            "Alpaca .env parse OK"
            " | paper_host=" + str(host_ok)
            + " | key_id_len=" + str(len(cfg.key_id))
            + " | secret_len=" + str(len(cfg.secret))
        )
        print("  (run `python3 -m runner.broker_alpaca` for a live auth ping)")
        if not host_ok:
            print("  WARNING: trade_base is NOT the paper host — broker will refuse.")
            rc = 1
    except Exception as exc:
        print("Alpaca config load FAILED: " + repr(exc))
        rc = 1

    keys = _read_env(WS / ".env")
    fk = keys.get("FRED_API_KEY", "")
    print(
        "FRED_API_KEY present=" + str(bool(fk))
        + " | len=" + str(len(fk)) + " (expect 32 lowercase hex)"
    )

    names = sorted(keys.keys())
    print("Keys present in .env (names only): " + ", ".join(names))
    print("Verify complete.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
