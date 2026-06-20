ABORT-BULLET-REWRITER — 2026-05-31T07:04:19+00:00

role_id: 1206
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): /applications/queued/ashby-coframe-8e95cc54/tailoring-notes.md
[bullet_rewriter] page-fill loop 1: Resume under-fills the single page (≈96% visual fill) — EXPAND existing bullets to fuller 2-line versions (~200–280 chars) with substantive JD-aligned detail (methodology, customer/team context, why the impact mattered). If still under-filled, ADD a bullet within each role's cap. Target ≥97% page fill, strictly 1 page.
Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 554, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 548, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 519, in run
    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
  File "/usr/lib/python3.10/pathlib.py", line 1154, in write_text
    with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
  File "/usr/lib/python3.10/pathlib.py", line 1119, in open
    return self._accessor.open(self, mode, buffering, encoding, errors,
FileNotFoundError: [Errno 2] No such file or directory: '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/ashby-coframe-8e95cc54/rewrites.json'

