import json
m = json.load(open('output/20260504-1140-meta.json'))
new_companies = ['xAI','Roku','The Trade Desk','Replit','Palantir','Jane Street','Harvey','Sierra','Decagon','Smartsheet','ElevenLabs','LaunchDarkly','Mixpanel','Amplitude','Algolia','Fivetran','Cockroach Labs','Tanium','Faire','Flexport','Suno','Lovable','Runway','Pika','Render','Supabase','PlanetScale','Neon','CircleCI','Akuna Capital','IMC Trading','Jump Trading','Gemini','Pendo']
total_fetched = 0
total_kept = 0
for c in m.get('successes', []):
    if c.get('company') in new_companies:
        f = c.get('fetched', 0)
        k = c.get('kept', 0)
        total_fetched += f
        total_kept += k
        print(f"{c['company']:20s} fetched={f:5d} kept={k:3d}")
print(f"\n{'TOTAL NEW':20s} fetched={total_fetched:5d} kept={total_kept:3d}")

