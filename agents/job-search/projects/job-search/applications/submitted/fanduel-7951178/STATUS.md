ABORT-BULLET-REWRITER — 2026-06-23T17:26:29+00:00

role_id: 2849
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): line ceiling — shorten to ≤290 (it currently wraps to a 3rd line)', 'role pro_painters bullet#3: 295 chars exceeds 290-char 2-line ceiling — shorten to ≤290 (it currently wraps to a 3rd line)']
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
FileNotFoundError: [Errno 2] No such file or directory: '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/fanduel-7951178/rewrites.json'

