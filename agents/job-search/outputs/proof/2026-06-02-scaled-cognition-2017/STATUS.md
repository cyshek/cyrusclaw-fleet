ABORT-BULLET-REWRITER — 2026-06-02T07:37:48+00:00

role_id: 2017
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): [bullet_rewriter] model attempt 1 (prompt 11813 chars)
Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 771, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 765, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 628, in run
    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
  File "/usr/lib/python3.10/pathlib.py", line 1154, in write_text
    with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
  File "/usr/lib/python3.10/pathlib.py", line 1119, in open
    return self._accessor.open(self, mode, buffering, encoding, errors,
FileNotFoundError: [Errno 2] No such file or directory: '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/ashby-scaled-cognition-d8aa1291/rewrites.json'

