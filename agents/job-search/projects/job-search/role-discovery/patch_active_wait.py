import subprocess

fname = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/_ashby_runner.py'
content = open(fname).read()

# Fix 1: In the YESNO reassert (_yn_fixed loop), increase wait from 200ms to 500ms before checking _active_
# The check is right after the synthetic event dispatch
old1 = '''                                        page.wait_for_timeout(400)
                                        try:
                                            _ok = page.evaluate(
                                                "(el)=>{const b=[...el.querySelectorAll('button')].find(x=>/_active_|_selected_/.test(x.className));const cb=el.querySelector('input[type=checkbox]');return (b&&/_active_|_selected_/.test(b.className))||(cb&&cb.checked);}",
                                                _cont)
                                        except Exception:
                                            _ok = True
                                        if _ok:
                                            _yn_fixed += 1
                                            break
                                        log(f"yesno not active after click {_dfp[-12:]}, retry {_attempt+1}")'''

new1 = '''                                        # chain_snowflake_active_wait (2026-06-23):
                                        # _active_ class appears with ~300ms React
                                        # render delay. Poll up to 600ms before
                                        # declaring failure (to avoid double-clicking).
                                        _ok = False
                                        for _wpoll in range(3):  # 3 x 200ms = 600ms max
                                            page.wait_for_timeout(200)
                                            try:
                                                _ok = page.evaluate(
                                                    "(el)=>{const b=[...el.querySelectorAll('button')].find(x=>/_active_|_selected_/.test(x.className));const cb=el.querySelector('input[type=checkbox]');return (b&&/_active_|_selected_/.test(b.className))||(cb&&cb.checked);}",
                                                    _cont)
                                            except Exception:
                                                _ok = True
                                            if _ok:
                                                break
                                        if _ok:
                                            _yn_fixed += 1
                                            break
                                        log(f"yesno not active after click {_dfp[-12:]}, retry {_attempt+1}")'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Fix 1 applied (YESNO reassert wait)")
else:
    print("Fix 1 NOT FOUND")
    idx = content.find('page.wait_for_timeout(400)')
    print(f"  Found timeout(400) at char {idx}")

open(fname, 'w').write(content)
r = subprocess.run(['python3', '-m', 'py_compile', fname], capture_output=True, text=True)
print("Syntax:", "OK" if r.returncode == 0 else "ERROR: " + r.stderr[:300])
