ABORT-BULLET-REWRITER — 2026-06-24T02:00:40+00:00

role_id: 3468
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): 3rd line)']
[bullet_rewriter] page-fill loop 3: Resume overflows onto page 2 (fill≈54% on the spilled page) — TIGHTEN: shorten phrasing across bullets, and DROP the weakest bullets within each role's [min, max] cap, until everything fits on ONE page. Keep every bullet ≤2 visual lines.
Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 881, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 875, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 770, in run
    pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 590, in render_resume
    raise RuntimeError(f"expected pdf not produced: {pdf_path}")
RuntimeError: expected pdf not produced: /home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/esri-5151710007/Cyrus_Shekari_Resume_esri_5151710007_v2.pdf

