# adapters/_repair/

Scratch space for the auto-repair loop. **Nothing in prod imports from this directory.**

Conventions:
- `<name>.py.candidate` — proposed fix for adapter `<name>`. Never merged automatically.
- `_verify_<name>.py` — ad-hoc driver that imports the candidate via importlib and re-runs the smoke probe.

To promote a candidate to live (manual, Cyrus-approved):
```
cp adapters/_repair/<name>.py.candidate adapters/<name>.py
```

This directory is .gitignore-safe by convention — even when changes here go stale, prod is unaffected.
