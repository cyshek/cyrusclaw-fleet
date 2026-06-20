import requests, json
from youtube_transcript_api import YouTubeTranscriptApi

session = requests.Session()
session.cookies.set('YSC', 'INazEfQWlHI', domain='.youtube.com')
session.cookies.set('VISITOR_INFO1_LIVE', 'Jaqt404bkoY', domain='.youtube.com')
session.cookies.set('VISITOR_PRIVACY_METADATA', 'CgJVUxIEGgAgPA==', domain='.youtube.com')
session.cookies.set('GPS', '1', domain='.youtube.com')
session.cookies.set('PREF', 'tz=UTC', domain='.youtube.com')
session.cookies.set('__Secure-ROLLOUT_TOKEN', 'CKOOj63QjcqazAEQ0-v0yYn9lAMY5PSciMT9lAM=', domain='.youtube.com')

session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
})

try:
    api = YouTubeTranscriptApi(http_client=session)
    t = api.fetch('PEAjFkVu5G0')
    for seg in t:\n        print(f'{seg.start:.1f}s: {seg.text}')
except Exception as e:\n    print(f'Error: {type(e).__name__}: {e}')
