#!/usr/bin/env python3
"""Patch _ashby_runner.py: add chain_p11c yesno-button trusted fallback in final_clobber_guard."""
import shutil, sys

SRC = '_ashby_runner.py'
BAK = '_ashby_runner.py.bak_p11c'

shutil.copy2(SRC, BAK)

with open(SRC, 'r') as f:\n    lines = f.readlines()\n\n# Find the exact line with the append\ntarget_line = "            status['reasserted_workauth'].append({'name': name[-24:], 'target': tgt, 'clicked': clicked, 'committed': committed})\n"
idx = None
for i, line in enumerate(lines):
    if line == target_line:
        idx = i
        break

if idx is None:
    print("ERROR: target line not found", file=sys.stderr)
    sys.exit(1)

print(f"Found target at line {idx+1}")

# The new block to insert BEFORE the append line
insert_lines = [
    "            # chain_p11c (2026-06-23): YESNO-BUTTON trusted fallback.\n",
    "            # Ashby yesno_button style uses <button class=\"_active_\"> with a\n",
    "            # hidden checkbox; _RADIO_FORCE_COMMIT_IN_CONTAINER_JS only fires\n",
    "            # synthetic JS events that set DOM .checked but leave React\n",
    "            # savedValue=null -> POST banks \"Missing entry\". If the force-commit\n",
    "            # didn't confirm .checked, fall back to a REAL Playwright trusted\n",
    "            # button click which generates a CDP input event React honours.\n",
    "            if not (isinstance(committed, dict) and committed.get('checked')):\n",
    "                try:\n",
    "                    for _fp in _field_path_candidates(name):\n",
    "                        _cont_el = None\n",
    "                        try:\n",
    "                            _cont_el = page.query_selector(f'[data-field-path=\"{_fp}\"]')\n",
    "                        except Exception:\n",
    "                            pass\n",
    "                        if not _cont_el:\n",
    "                            continue\n",
    "                        _found_btn = False\n",
    "                        for _btn in _cont_el.query_selector_all('button'):\n",
    "                            _btxt = (_btn.inner_text() or '').strip().lower()\n",
    "                            if _btxt == tl or (len(tl) > 2 and tl in _btxt):\n",
    "                                try:\n",
    "                                    _btn.scroll_into_view_if_needed(timeout=1500)\n",
    "                                    _btn.click(timeout=3000)\n",
    "                                    page.wait_for_timeout(200)\n",
    "                                    _is_active = page.evaluate(\n",
    "                                        \"(b)=>/_active_|_selected_/.test(b.className||'')\",\n",
    "                                        _btn)\n",
    "                                    committed = {'ok': True, 'checked': bool(_is_active),\n",
    "                                                 'picked': (_btn.inner_text() or '').strip(),\n",
    "                                                 'via': 'yesno-trusted-btn'}\n",
    "                                    if _is_active:\n",
    "                                        clicked = True\n",
    "                                except Exception as _be:\n",
    "                                    log(f\"final-guard yesno-btn click {_fp[-16:]}: {_be}\")\n",
    "                                _found_btn = True\n",
    "                                break\n",
    "                        if _found_btn:\n",
    "                            break\n",
    "                except Exception as _yb:\n",
    "                    log(f\"final-guard yesno-btn fallback {name[-20:]}: {_yb}\")\n",
]

new_lines = lines[:idx] + insert_lines + lines[idx:]

with open(SRC, 'w') as f:\n    f.writelines(new_lines)\n\nprint(f"Inserted {len(insert_lines)} lines before line {idx+1}")
print("Patch applied successfully!")
print(f"Backup: {BAK}")
