ABORT-BULLET-REWRITER — 2026-06-23T04:46:03+00:00

role_id: 3429
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1): .max_loops,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 770, in run
    pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 586, in render_resume
    raise RuntimeError(
RuntimeError: tailor_resume.py failed (rc=1)
STDOUT:
STDERR:Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1142, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1133, in main
    report = run_pipeline(
             ^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 965, in run_pipeline
    convert_to_pdf(target_docx, pdf_path)
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py", line 1071, in convert_to_pdf
    raise RuntimeError(
RuntimeError: soffice conversion failed (rc=1)
STDOUT:
STDERR:Warning: failed to launch javaldx - java may not function correctly



