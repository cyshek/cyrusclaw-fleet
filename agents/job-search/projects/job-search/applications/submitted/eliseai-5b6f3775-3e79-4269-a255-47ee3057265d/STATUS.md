ABORT-BULLET-REWRITER — 2026-06-04T07:21:33+00:00

role_id: 2724
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): .py", line 771, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 765, in main
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 731, in run
    pdf_path = render_resume(org, job_id)
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 552, in render_resume
    raise RuntimeError(
RuntimeError: tailor_resume.py failed (rc=1)
STDOUT:
STDERR:Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1119, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1110, in main
    report = run_pipeline(
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 951, in run_pipeline
    convert_to_pdf(target_docx, pdf_path)
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1057, in convert_to_pdf
    raise RuntimeError(
RuntimeError: soffice conversion failed (rc=1)
STDOUT:
STDERR:Warning: failed to launch javaldx - java may not function correctly



