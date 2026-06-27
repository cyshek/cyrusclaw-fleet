import yaml
with open("companies.yaml") as f:
    data = yaml.safe_load(f)
companies = data.get("companies", [])
counts = {}
for c in companies:
    if c.get("skip"):
        continue
    adapter = c.get("adapter", "unknown")
    counts[adapter] = counts.get(adapter, 0) + 1
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print(f"  TOTAL active: {sum(counts.values())}")
