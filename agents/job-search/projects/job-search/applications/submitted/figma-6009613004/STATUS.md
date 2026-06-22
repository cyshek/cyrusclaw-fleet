ABORT-COVER-ANSWERS — 2026-06-22T07:31:50+00:00

role_id: 2344
phase: cover-answers
error:
RuntimeError: cover_answer_generator failed (rc=1): Traceback (most recent call last):
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 564, in <module>
    main()
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 559, in main
    result = run(args.slug, args.max_retries)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 522, in run
    prompt = build_prompt(jd_text, resume_text, personal_info, questions,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/cover_answer_generator.py", line 357, in build_prompt
    { "question": "<verbatim question text>", "answer": "<answer text>" },
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: Invalid format specifier ' "<verbatim question text>", "answer": "<answer text>" ' for object of type 'str'

