import urllib.request, re, sys

url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
try:
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
except Exception as e:
    print("FETCH FAILED:", type(e).__name__, str(e)[:200])
    sys.exit(3)

print("page bytes:", len(html))
has_changes = "Selected changes" in html or "changes to the list" in html.lower()
print("has 'changes' section:", has_changes)
dates = re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', html)
print("date-like change rows found:", len(dates))
print("sample first:", dates[:5])
print("sample last:", dates[-3:] if len(dates) > 3 else dates)
# count current tickers in the constituents table (rough)
tickers = re.findall(r'rel="nofollow"[^>]*>([A-Z]{1,5}(?:\.[A-Z])?)</a>', html)
print("rough current-ticker hits:", len(set(tickers)))
