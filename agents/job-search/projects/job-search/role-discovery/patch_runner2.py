fname = '_icims_runner.py'
with open(fname) as f:
    lines = f.readlines()
start = None
end = None
for i, ln in enumerate(lines):
    if ln.strip().startswith('def try_solve_hcaptcha'):
        start = i
    elif start is not None and i > start + 2 and ln.strip().startswith('def ') and 'try_solve' not in ln:
        end = i
        break
repl = []
repl.append('def try_solve_hcaptcha(sitekey, page_url, max_attempts=3):\n')
repl.append('    """Attempt to solve hCaptcha (proxyless only — HCaptchaTask+proxy times out).\n')
repl.append('    PROXY_2CAPTCHA temporarily unset: proxyless ~26s proved 2026-07-01.\n')
repl.append('    """\n')
repl.append('    try:\n')
repl.append('        from captcha_solver import CaptchaSolver, SolverNotConfigured, SolverError\n')
repl.append('    except Exception as e:\n')
repl.append('        return None, f"captcha-solver-import-fail:{e}"\n')
repl.append('    _proxy_backup = os.environ.pop("PROXY_2CAPTCHA", None)\n')
repl.append('    try:\n')
repl.append('        for attempt in range(1, max_attempts + 1):\n')
repl.append('            if attempt > 1:\n')
repl.append('                log(f"hCaptcha retry attempt {attempt}/{max_attempts}")\n')
repl.append('                time.sleep(5)\n')
repl.append('            for vendor in ("twocaptcha", "nopecha"):  # capsolver dropped hCaptcha\n')
repl.append('                try:\n')
repl.append('                    solver = CaptchaSolver(vendor=vendor)\n')
repl.append('                except (SolverNotConfigured, SolverError):\n')
repl.append('                    continue\n')
repl.append('                try:\n')
repl.append('                    token = solver.solve_hcaptcha(sitekey, page_url)\n')
repl.append('                    if token:\n')
repl.append('                        return token, f"solved-via-{vendor}-attempt{attempt}"\n')
repl.append('                except Exception as e:\n')
repl.append('                    err_str = str(e)\n')
repl.append('                    log(f"hcaptcha solve via {vendor} attempt {attempt} failed:", e)\n')
repl.append('                    if "UNSOLVABLE" in err_str or "unsolvable" in err_str:\n')
repl.append('                        break\n')
repl.append('                    continue\n')
repl.append('    finally:\n')
repl.append('        if _proxy_backup is not None:\n')
repl.append('            os.environ["PROXY_2CAPTCHA"] = _proxy_backup\n')
repl.append('    return None, "icims-hcaptcha-no-vendor"\n')
new_lines = lines[:start] + repl + lines[end:]
with open(fname, 'w') as f:
    f.writelines(new_lines)
print(f'Wrote {len(new_lines)} lines (was {len(lines)})')
