# Contributing

Thanks for your interest! This repo started as a personal fleet but the job-search pipeline is designed to be forkable and extensible. PRs welcome.

---

## Adding a New ATS Runner

Each ATS platform has its own runner module in `agents/job-search/role-discovery/`. The naming convention is `<ats_name>_filler.py` or `_<ats_name>_runner.py`.

### Reference implementations

- **Ashby** → `ashby_filler.py` — well-documented, handles most form patterns
- **Greenhouse** → `greenhouse_filler.py` — good example of multi-step forms + file upload
- **Lever** → `lever_filler.py` — simpler, good starter reference

### What a runner needs to implement

At minimum, a runner should:

1. **Accept a `Role` object and `personal_info` dict** as inputs (see `core.py` for types)
2. **Launch a Playwright browser** (headless by default, headed for debugging)
3. **Navigate to the application URL** from `role.apply_url`
4. **Fill all required fields** from `personal_info`
5. **Upload the resume PDF** from `personal_info["files"]["resume_pdf"]`
6. **Submit the form** and capture any confirmation
7. **Update the tracker DB** via `tracker_db.py` — mark as `applied` or `blocked` with a reason
8. **Return a result dict** with at minimum `{"status": "applied" | "blocked" | "error", "reason": "..."}`

### Registering the runner

Add your ATS to `companies.yaml` with the relevant metadata:

```yaml
- slug: your-company
  name: Your Company
  ats: your_ats_name
  apply_url: https://yourcompany.com/careers/apply
```

Then wire it into the dispatch logic in `build_submit_plan.py` or the relevant driver script.

### Testing your runner

Write a dry-run test in `role-discovery/test_<ats_name>_*.py`. Dry runs should:
- Load a fixture plan (JSON) instead of hitting a live form
- Assert field mappings are correct
- Not actually submit anything

Run existing tests with:

```bash
cd role-discovery
python3 -m pytest test_*.py -v
```

---

## Code Style

- Python 3.11+, no type-annotation requirement but encouraged
- `personal_info` is always a plain dict loaded from `personal-info.json` — don't add new global constants for user data; read from the dict
- Playwright: use `async` Playwright (`async_playwright`) for new runners — the older runners use sync but async is preferred going forward
- Log verbosely during runs (print statements are fine; this is a CLI tool)

---

## Submitting a PR

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-ats-runner`
3. Make your changes
4. Test against a real job posting (dry-run mode first, then a live test)
5. Open a PR with a brief description of what ATS you added and any quirks worth noting

Please don't commit `personal-info.json`, `tracker.db`, `.env`, or any credentials.

---

## Reporting Issues

Open a GitHub Issue. Include:
- Which ATS / company
- What the form looks like (screenshot or URL if public)
- What error or block you hit
- Your Python + Playwright versions

---
\n*Questions? Open an issue or start a discussion.*
