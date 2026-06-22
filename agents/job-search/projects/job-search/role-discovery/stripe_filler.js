// Generic Stripe v2 filler. Inputs all driven by LABEL matching, not field id.
// Persona is hardcoded for now; production version will read from prefill.json.
// TODO: PII — replace hardcoded values below with prefill.json lookup before use.
// To decouple: call page.evaluate(`const PI=${JSON.stringify(pi)}; ${script}`) from Python
async () => {
  // PII constants — should be injected from personal-info.json by the Python caller
  const FILL_FIRST = window.__PI_FIRST || 'REPLACE_FIRST';
  const FILL_LAST  = window.__PI_LAST  || 'REPLACE_LAST';
  const FILL_EMAIL = window.__PI_EMAIL || 'REPLACE_EMAIL';
  const FILL_PHONE = window.__PI_PHONE || 'REPLACE_PHONE';
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, button: 0, clientX: x||0, clientY: y||0}));
  const setNative = (el, val) => {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  };

  // Find an input element by surrounding label text (case-insensitive regex match)
  const findByLabel = re => {
    const labels = [...document.querySelectorAll('label')];
    for (const l of labels) {
      if (re.test((l.textContent || '').trim())) {
        const fid = l.getAttribute('for');
        if (fid) {
          const el = document.getElementById(fid);
          if (el) return el;
        }
      }
    }
    return null;
  };

  async function pickRSByLabel(labelRe, want) {
    const inp = findByLabel(labelRe);
    if (!inp) return {err: 'no inp', re: labelRe.source};
    if (!inp.classList.contains('select__input')) return {err: 'not select', id: inp.id};
    const ctrl = inp.closest('.select__control');
    if (ctrl.querySelector('.select__single-value')) return {id: inp.id, already: ctrl.querySelector('.select__single-value').textContent};
    ctrl.scrollIntoView({block: 'center'});
    await sleep(150);
    const r = ctrl.getBoundingClientRect();
    fire(ctrl, 'mousedown', r.left+5, r.top+5);
    fire(ctrl, 'mouseup', r.left+5, r.top+5);
    fire(ctrl, 'click', r.left+5, r.top+5);
    await sleep(450);
    const opts = [...document.querySelectorAll(`[id^=react-select-${CSS.escape(inp.id)}-option]`)];
    const wants = Array.isArray(want) ? want : [want];
    let target = null;
    for (const w of wants) {
      const wlc = String(w).toLowerCase();
      target = opts.find(o => o.textContent.trim().toLowerCase() === wlc);
      if (target) break;
      target = opts.find(o => o.textContent.trim().toLowerCase().startsWith(wlc));
      if (target) break;
      target = opts.find(o => o.textContent.toLowerCase().includes(wlc));
      if (target) break;
    }
    if (!target) { fire(document.body, 'mousedown', 0, 0); return {id: inp.id, err: 'no opt', want: wants, opts: opts.map(o => o.textContent.trim()).slice(0,10)}; }
    const tr = target.getBoundingClientRect();
    fire(target, 'mousedown', tr.left+5, tr.top+5);
    fire(target, 'mouseup', tr.left+5, tr.top+5);
    fire(target, 'click', tr.left+5, tr.top+5);
    await sleep(250);
    return {id: inp.id, chip: ctrl.querySelector('.select__single-value')?.textContent};
  }

  async function setTextByLabel(labelRe, val) {
    const el = findByLabel(labelRe);
    if (!el) return {err: 'no inp', re: labelRe.source};
    setNative(el, val);
    return {id: el.id, val: el.value};
  }

  const out = {};
  out.first = await setTextByLabel(/^First Name/, FILL_FIRST);
  out.last = await setTextByLabel(/^Last Name/, FILL_LAST);
  out.email = await setTextByLabel(/^Email/, FILL_EMAIL);
  out.phone = await setTextByLabel(/^Phone\*?$/, FILL_PHONE);
  // Reformat phone (iti formats on second setNative)
  const ph = document.getElementById('phone');
  if (ph) { setNative(ph, ''); setNative(ph, FILL_PHONE); }
  out.employer = await setTextByLabel(/current or previous employer/i, 'Microsoft');
  out.title = await setTextByLabel(/current or previous job title/i, 'Technical Program Manager');
  out.school = await setTextByLabel(/most recent school/i, 'University of Houston');
  out.degree = await setTextByLabel(/most recent degree/i, 'Bachelor of Science');
  out.cityState = await setTextByLabel(/located in the US.*city and state/i, 'Kirkland, WA');

  // Country picker (full names + dial code)
  out.country = await pickRSByLabel(/^Country\*?$/, ['United States +1', 'United States']);
  out.countryReside = await pickRSByLabel(/country where you currently reside/i, ['US', 'United States']);
  out.auth = await pickRSByLabel(/authorized to work in the location/i, 'Yes');
  out.sponsor = await pickRSByLabel(/sponsor you for a work permit/i, 'No');
  out.remote = await pickRSByLabel(/plan to work remotely/i, ['Yes, I intend', 'Yes']);
  out.prevStripe = await pickRSByLabel(/ever been employed by Stripe/i, 'No');
  out.whatsapp = await pickRSByLabel(/WhatsApp messages from Stripe/i, 'No');
  out.nycHybrid = await pickRSByLabel(/requires the candidate to be based in New York/i, 'No');

  // Multi-checkbox fieldset (Stripe ships question_xxx[] as native checkboxes)
  const fieldsets = [...document.querySelectorAll('fieldset.checkbox')];
  out.mselects = [];
  for (const fs of fieldsets) {
    const legend = (fs.querySelector('legend')?.textContent || '').trim().toLowerCase();
    if (/countries you anticipate working|select the countries/i.test(legend)) {
      const labels = [...fs.querySelectorAll('label')];
      const usLbl = labels.find(l => /^(US|USA|United States)$/i.test(l.textContent.trim()));
      if (usLbl) {
        const fid = usLbl.getAttribute('for');
        const cb = document.getElementById(fid);
        if (cb && !cb.checked) cb.click();
        out.mselects.push({fid, checked: cb?.checked, legend: legend.slice(0,60)});
      }
    }
  }

  // candidate-location typeahead
  const cl = document.getElementById('candidate-location');
  if (cl) {
    const clCtrl = cl.closest('.select__control');
    if (!clCtrl.querySelector('.select__single-value')) {
      const r = clCtrl.getBoundingClientRect();
      fire(clCtrl, 'mousedown', r.left+5, r.top+5);
      fire(clCtrl, 'mouseup', r.left+5, r.top+5);
      fire(clCtrl, 'click', r.left+5, r.top+5);
      await sleep(300);
      setNative(cl, 'Kirkland');
      await sleep(900);
      const opts = [...document.querySelectorAll("[id^='react-select-candidate-location-option']")];
      if (opts.length) {
        const tr = opts[0].getBoundingClientRect();
        fire(opts[0], 'mousedown', tr.left+5, tr.top+5);
        fire(opts[0], 'mouseup', tr.left+5, tr.top+5);
        fire(opts[0], 'click', tr.left+5, tr.top+5);
        await sleep(250);
      }
    }
    out.candLoc = clCtrl.querySelector('.select__single-value')?.textContent;
  }

  // Demographics decline
  fire(document.body, 'mousedown', 5, 5); await sleep(200);
  const demos = ['gender', 'hispanic_ethnicity', 'veteran_status', 'disability_status'];
  out.demos = {};
  for (const id of demos) {
    const inp = document.getElementById(id);
    if (!inp) { out.demos[id] = 'missing'; continue; }
    const ctrl = inp.closest('.select__control');
    if (ctrl.querySelector('.select__single-value')) { out.demos[id] = 'already'; continue; }
    ctrl.scrollIntoView({block: 'center'});
    await sleep(150);
    const r = ctrl.getBoundingClientRect();
    fire(ctrl, 'mousedown', r.left+5, r.top+5);
    fire(ctrl, 'mouseup', r.left+5, r.top+5);
    fire(ctrl, 'click', r.left+5, r.top+5);
    await sleep(400);
    const opts = [...document.querySelectorAll(`[id^=react-select-${id}-option]`)];
    let target = opts.find(o => /decline|prefer not|don'?t wish|do not want|do not wish/i.test(o.textContent));
    if (!target) target = opts[opts.length - 1];
    if (target) {
      const tr = target.getBoundingClientRect();
      fire(target, 'mousedown', tr.left+5, tr.top+5);
      fire(target, 'mouseup', tr.left+5, tr.top+5);
      fire(target, 'click', tr.left+5, tr.top+5);
      await sleep(250);
    }
    out.demos[id] = ctrl.querySelector('.select__single-value')?.textContent;
    fire(document.body, 'mousedown', 5, 5); await sleep(150);
  }
  return out;
};
