#!/usr/bin/env python3
"""GO/NO-GO feasibility probe: is a FREE delisting-inclusive (survivorship-clean)
historical equity universe buildable from THIS VM?

Three things must ALL be reachable for a YES:
  (A) Price history for DELISTED tickers (so a delisted name contributes returns
      up to its delisting, not silently dropped).
  (B) A complete, point-in-time MEMBERSHIP signal that INCLUDES names that later
      delisted (EDGAR filing streams are the natural candidate — a delisted
      registrant's 10-K/10-Q stream survives in the archive and simply stops).
  (C) A way to MAP a historical ticker <-> CIK for delisted names (the join key
      between price and membership). This is the suspected weak link, because
      company_tickers.json is current-registrant-only.

Prints a structured verdict. No writes outside /tmp. Free sources only.
"""
import json
import sys
import time
import urllib.request
import urllib.error
import datetime as dt

SEC_UA = "trading-bench-research contact: research@example.invalid"
YF_UA = "Mozilla/5.0"


def _get(url, ua, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def yahoo_chart(sym, timeout=20):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1=0&period2=9999999999&interval=1d")
    try:
        d = json.loads(_get(url, YF_UA, timeout))
    except urllib.error.HTTPError as e:
        return {"sym": sym, "ok": False, "err": f"HTTP {e.code}"}
    except Exception as e:
        return {"sym": sym, "ok": False, "err": repr(e)[:80]}
    chart = d.get("chart") or {}
    res = chart.get("result")
    err = chart.get("error")
    if err:
        return {"sym": sym, "ok": False, "err": (err or {}).get("code", "err")}
    if res and res[0].get("timestamp"):
        ts = res[0]["timestamp"]
        return {"sym": sym, "ok": True, "bars": len(ts),
                "first": str(dt.date.fromtimestamp(ts[0])),
                "last": str(dt.date.fromtimestamp(ts[-1]))}
    return {"sym": sym, "ok": False, "err": "no_data"}


def main():
    out = {}

    # ---- (A) delisted price history via Yahoo ------------------------------
    # Mix of bankrupt/acquired/delisted across eras. .Q/.PK suffixes vary.
    delisted = ["LEH", "WCOM", "ENRNQ", "BSC", "GM", "WAMUQ", "SHLDQ",
                "FRCB", "SIVBQ", "BBBYQ", "MNKKQ", "SUNEQ"]
    a = []
    for s in delisted:
        a.append(yahoo_chart(s))
        time.sleep(0.4)
    out["A_delisted_price"] = a
    out["A_hit_rate"] = f"{sum(1 for x in a if x['ok'])}/{len(a)}"

    # ---- (C) ticker<->CIK for delisted names -------------------------------
    # The current map (company_tickers.json) — confirm it's active-only.
    try:
        ct = json.loads(_get("https://www.sec.gov/files/company_tickers.json", SEC_UA))
        cur_tickers = {v["ticker"].upper() for v in ct.values()}
        out["C_current_map_n"] = len(ct)
        out["C_delisted_in_current_map"] = {
            s: (s in cur_tickers) for s in delisted}
    except Exception as e:
        out["C_current_map_err"] = repr(e)[:120]

    # Is there a fuller historical ticker file? EDGAR also publishes
    # company_tickers_exchange.json (also current). The HISTORICAL ticker for a
    # CIK lives inside each submissions JSON under formerNames / tickers, but
    # there is NO free reverse index from an OLD ticker to a CIK. Probe whether
    # full-text search can recover a CIK from a delisted ticker string.
    fts = {}
    for s in ["WCOM", "ENRON", "LEHMAN BROTHERS"]:
        try:
            q = urllib.parse.quote(s)
            d = json.loads(_get(
                f"https://efts.sec.gov/LATEST/search-index?q=%22{q}%22", SEC_UA, 20))
            fts[s] = "reachable"
        except Exception as e:
            fts[s] = f"err {repr(e)[:50]}"
        time.sleep(0.3)
    out["C_fts_probe"] = fts

    # ---- (B) membership: does a delisted CIK's filing stream survive? ------
    # Lehman CIK 806085 already shown to survive; generalize to a few.
    b = {}
    for name, cik in [("LEHMAN", "0000806085"),
                      ("ENRON", "0001024401"),
                      ("WORLDCOM", "0000723527")]:
        try:
            d = json.loads(_get(
                f"https://data.sec.gov/submissions/CIK{cik}.json", SEC_UA, 25))
            f = (d.get("filings") or {}).get("recent") or {}
            forms = f.get("form", [])
            dates = f.get("filingDate", [])
            last10k = next((dt_ for fm, dt_ in zip(forms, dates) if fm == "10-K"), None)
            b[name] = {"ok": True, "name": d.get("name"),
                       "n_recent": len(forms),
                       "newest": dates[0] if dates else None,
                       "oldest_recent": dates[-1] if dates else None,
                       "last_10K": last10k,
                       "former_names": [fn.get("name") for fn in (d.get("formerNames") or [])][:3]}
        except Exception as e:
            b[name] = {"ok": False, "err": repr(e)[:80]}
        time.sleep(0.3)
    out["B_delisted_filing_streams"] = b

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    import urllib.parse  # noqa
    main()
