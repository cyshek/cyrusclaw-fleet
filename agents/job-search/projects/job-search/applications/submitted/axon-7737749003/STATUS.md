ABORT-BULLET-REWRITER — 2026-06-27T00:14:28+00:00

role_id: 1942
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): e spilled page) — TIGHTEN: shorten phrasing across bullets, and DROP the weakest bullets within each role's [min, max] cap, until everything fits on ONE page. Keep every bullet ≤2 visual lines.
Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 881, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 875, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 768, in run
    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
  File "/usr/lib/python3.12/pathlib.py", line 1049, in write_text
    with self.open(mode='w', encoding=encoding, errors=errors, newline=newline) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/pathlib.py", line 1015, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/axon-7737749003/rewrites.json'

