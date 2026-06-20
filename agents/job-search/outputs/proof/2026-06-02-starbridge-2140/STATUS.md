ABORT-BULLET-REWRITER — 2026-06-02T07:44:08+00:00

role_id: 2120
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): ngle page (≈90% visual fill) — EXPAND existing bullets to fuller 2-line versions with substantive JD-aligned detail. If still under-filled, ADD a bullet within each role's cap. Fill the page but stay strictly 1 page — never spill to page 2.
[bullet_rewriter] page-fit sub-attempt 1 failed: ['role microsoft_ft bullet#1: 293 chars exceeds 290-char 2-line ceiling — shorten to ≤290 (it currently wraps to a 3rd line)']
Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 771, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 765, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 708, in run
    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
  File "/usr/lib/python3.10/pathlib.py", line 1154, in write_text
    with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
  File "/usr/lib/python3.10/pathlib.py", line 1119, in open
    return self._accessor.open(self, mode, buffering, encoding, errors,
FileNotFoundError: [Errno 2] No such file or directory: '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/ashby-starbridge-3b0bd418/rewrites.json'

