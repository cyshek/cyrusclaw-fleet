ABORT-BULLET-REWRITER — 2026-06-27T01:29:10+00:00

role_id: 1601
phase: bullet-rewriter
error:
RuntimeError: bullet_rewriter failed (rc=1):      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/bullet_rewriter.py", line 584, in render_resume
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/subprocess.py", line 550, in run
    stdout, stderr = process.communicate(input, timeout=timeout)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/subprocess.py", line 1209, in communicate
    stdout, stderr = self._communicate(input, endtime, timeout)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/subprocess.py", line 2116, in _communicate
    self._check_timeout(endtime, orig_timeout, stdout, stderr)
  File "/usr/lib/python3.12/subprocess.py", line 1253, in _check_timeout
    raise TimeoutExpired(
subprocess.TimeoutExpired: Command '['/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/.venv/bin/python', '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/tailor_resume.py', '--org', 'schrdinger', '--job-id', '4318632003', '--out-dir', '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued/schrdinger-4318632003', '--suffix', '_v2', '--family', 'se']' timed out after 180 seconds

