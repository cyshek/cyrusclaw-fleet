#!/usr/bin/env python3
"""Probe CBOE CDN for P/C ratio data files."""
import requests

urls = [
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/PCALL_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/PCPUT_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/PC_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/CPC_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
]

hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

for url in urls:
    fname = url.split('/')[-1]
    try:
        r = requests.get(url, headers=hdrs, timeout=15)
        if r.status_code == 200:
            lines = r.text.strip().split('\n')
            print(f"OK  {r.status_code}  {len(lines):>5} rows  {fname}")
            print(f"   hdr: {lines[0]}")
            print(f"   r2:  {lines[1]}")
            print(f"   end: {lines[-1]}")
        else:
            print(f"ERR {r.status_code}  {fname}")
    except Exception as e:\n        print(f"EXC {fname}: {e}")
