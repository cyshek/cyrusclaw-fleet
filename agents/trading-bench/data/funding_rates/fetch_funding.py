#!/usr/bin/env python3
"""
Fetch historical funding rates from Binance USDT-M futures API.
Paginates backward from now to collect as much history as possible.
"""
import json
import time
import requests
import datetime
from pathlib import Path

BASE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
LIMIT = 1000

def fetch_all_funding_rates(symbol):
    all_records = []
    end_time = None
    print(f"\nFetching {symbol} funding rates...")
    request_count = 0
    while True:
        params = {"symbol": symbol, "limit": LIMIT}
        if end_time is not None:
            params["endTime"] = end_time
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            print("  Empty response -- done.")
            break
        request_count += 1
        batch_count = len(data)
        earliest_ts = data[0]["fundingTime"]
        latest_ts = data[-1]["fundingTime"]
        earliest_dt = datetime.datetime.utcfromtimestamp(earliest_ts / 1000)
        latest_dt = datetime.datetime.utcfromtimestamp(latest_ts / 1000)
        print(f"  Batch {request_count}: {batch_count} records | {earliest_dt.strftime('%Y-%m-%d')} -> {latest_dt.strftime('%Y-%m-%d')}")
        all_records = data + all_records
        if batch_count < LIMIT:
            print("  Reached beginning of history.")
            break
        end_time = earliest_ts - 1
        time.sleep(0.3)
        if request_count >= 60:
            print("  Hit safety limit of 60 requests.")
            break
    print(f"  Total records fetched: {len(all_records)}")
    return all_records

results = {}
for symbol in SYMBOLS:
    records = fetch_all_funding_rates(symbol)
    results[symbol] = records

out_path = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace/data/funding_rates/raw_funding_rates.json")
with open(out_path, "w") as f:\n    json.dump(results, f, indent=2)\n\nprint(f"\nSaved to {out_path}")
for sym, recs in results.items():
    print(f"  {sym}: {len(recs)} records")
