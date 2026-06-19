import urllib.request, json

markets = [
    ('616902', 'No Fed cuts 2026 - we bet NO'),
    ('908713', 'Fed rate hike 2026 - we bet YES'),
    ('1654958', 'No change July FOMC - we bet NO'),
    ('1654959', 'Fed +25bps July - we bet YES'),
    ('616903', '1 cut 2026 - we bet YES'),
    ('616904', '2 cuts 2026 - we bet YES'),
    ('1654960', 'Fed +50bps July - we bet YES'),
    ('609655', 'US recession 2026 - we bet NO'),
]

for mid, label in markets:
    try:
        req = urllib.request.Request(
            f'https://gamma-api.polymarket.com/markets/{mid}',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())
        price = data.get('outcomePrices', data.get('lastTradePrice', '?'))
        end = str(data.get('endDate','?'))[:10]
        closed = data.get('closed', False)
        resolved = data.get('resolved', False)
        outcomes = data.get('outcomes', '?')
        print(f"{label}")
        print(f"  closed={closed} resolved={resolved} end={end}")
        print(f"  outcomes={outcomes} prices={price}")
    except Exception as e:\n        print(f"{label} -> ERROR: {e}")
