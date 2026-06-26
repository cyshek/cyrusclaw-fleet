"""Patch _gh_submit.py to add education date filling after remix_recover."""
import re

path = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/_gh_submit.py'
with open(path, 'r') as f:\n    content = f.read()\n\n# Find the insertion point - right before "# GH-REMIX WORK-HISTORY repeater fill"
target = '    # GH-REMIX WORK-HISTORY repeater fill (Zuora 2755 cohort, 2026-06-09). Some'
if target not in content:
    print("ERROR: Target not found!")
    exit(1)

edu_fill_code = '''    # GH-REMIX EDUCATION DATE fill (Natera-class, 2026-06-25).
    # Some GH Remix tenants require education start/end dates in the POST body
    # (start-month--0, start-year--0, end-month--0, end-year--0). The remix_recover
    # fills end-month--0 (December) but skips start dates. The Greenhouse backend
    # returns 422 {"message":"educations","code":"invalid-attributes"} when
    # start_date.month is null. Truth source: personal-info.json education dates.
    # Education: Aug 2021 - Dec 2024 (University of Houston).
    try:
        try:
            _personal  # reuse if already loaded
        except NameError:
            from greenhouse_dryrun import PERSONAL_INFO_PATH as _PIP
            _personal = json.loads(_PIP.read_text())
        _pedu = (_personal or {}).get('education') or {}
        # Attendance: start_month (1-12 or name), start_year, end_month, end_year
        _edu_sm = _pedu.get('attendance_start_month') or _pedu.get('start_month') or 8
        _edu_sy = str(_pedu.get('attendance_start_year') or _pedu.get('start_year') or '2021').strip()
        _edu_em = _pedu.get('attendance_end_month') or _pedu.get('end_month') or 12
        _edu_ey = str(_pedu.get('attendance_end_year') or _pedu.get('end_year') or '2024').strip()
        # Normalize month number to name
        _MNAMES_EDU = ('January','February','March','April','May','June','July',
                       'August','September','October','November','December')
        def _mo_name_edu(m):
            try:
                mi = int(m)
                return _MNAMES_EDU[mi-1] if 1 <= mi <= 12 else str(m)
            except (ValueError, TypeError):
                return str(m)
        _edu_sm_name = _mo_name_edu(_edu_sm)
        _edu_em_name = _mo_name_edu(_edu_em)
        # Fill education month selects (start-month--0, end-month--0) via SEL_PICK
        _edu_month_specs = []
        for _efid, _elabel in [('start-month--0', _edu_sm_name), ('end-month--0', _edu_em_name)]:
            _echk = page.evaluate(f'() => {{ const e = document.getElementById({_efid!r}); return e ? e.id : null; }}')
            if _echk:
                _edu_month_specs.append({'id': _efid, 'label': _elabel})
        _edu_month_res = page.evaluate(SEL_PICK, _edu_month_specs) if _edu_month_specs else []
        # Fill education year text inputs (start-year--0, end-year--0)
        _EDU_YEAR_JS = """({sy, ey}) => {
            const setN = (el, v) => {
                const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                d.set.call(el, v);
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                el.dispatchEvent(new Event('blur', {bubbles:true}));
            };
            const r = {};
            const sy_el = document.getElementById('start-year--0');
            if (sy_el && sy) { setN(sy_el, sy); r['start-year--0'] = sy_el.value; }
            const ey_el = document.getElementById('end-year--0');
            if (ey_el && ey) { setN(ey_el, ey); r['end-year--0'] = ey_el.value; }
            return r;
        }"""
        _edu_year_res = page.evaluate(_EDU_YEAR_JS, {'sy': _edu_sy, 'ey': _edu_ey})
        result['steps']['edu_date_fill'] = {
            'months': _edu_month_res, 'years': _edu_year_res,
            'sm': _edu_sm_name, 'sy': _edu_sy, 'em': _edu_em_name, 'ey': _edu_ey
        }
        print(f'[edu] dates filled: start={_edu_sm_name}/{_edu_sy} end={_edu_em_name}/{_edu_ey}', flush=True)
    except Exception as _edu_err:
        result['steps']['edu_date_fill'] = {'err': str(_edu_err)}
        print(f'[edu] date fill error: {_edu_err}', flush=True)

'''

content = content.replace(target, edu_fill_code + target)

with open(path, 'w') as f:\n    f.write(content)\nprint("Patch applied successfully")
