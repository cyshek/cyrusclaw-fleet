#!/usr/bin/env python3
"""Fix literal \\n sequences in _icims_runner.py that should be real newlines."""

with open('projects/job-search/role-discovery/_icims_runner.py', 'r') as f:\n+    content = f.read()\n+\n+original_len = len(content)\n+\n+# These patterns have literal \n (backslash-n) in the file, but need real newlines.\n+replacements = [
    (
        'except Exception as e:\\n        hcap = {}\\n        log("Auth0 hCaptcha detect error:", e)',
        'except Exception as e:\n        hcap = {}\n        log("Auth0 hCaptcha detect error:", e)'
    ),
    (
        '                if m:\\n                    sitekey = m.group(1)\\n            except Exception:',
        '                if m:\n                    sitekey = m.group(1)\n            except Exception:'
    ),
    (
        '        except Exception as e:\\n            log("Auth0 hCaptcha inject error:", e)',
        '        except Exception as e:\n            log("Auth0 hCaptcha inject error:", e)'
    ),
    (
        '        except Exception as e:\\n            log("Auth0 email fill error:", e)',
        '        except Exception as e:\n            log("Auth0 email fill error:", e)'
    ),
    (
        '        except Exception as e:\\n            log("Auth0 continue click error:", e)',
        '        except Exception as e:\n            log("Auth0 continue click error:", e)'
    ),
    (
        '            except Exception as e:\\n                log("Auth0 pwd attempt %d error:", attempt, e)',
        '            except Exception as e:\n                log("Auth0 pwd attempt %d error:", attempt, e)'
    ),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {repr(old[:50])}")
    else:
        print(f"NOT FOUND: {repr(old[:50])}")

with open('projects/job-search/role-discovery/_icims_runner.py', 'w') as f:\n+    f.write(content)\n+\n+print(f"Done. Length: {original_len} -> {len(content)}")
