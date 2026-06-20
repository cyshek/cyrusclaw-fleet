_RADIO_FORCE_COMMIT_IN_CONTAINER_JS = """(args) => {
  // chain_p11b (2026-06-08): force-commit a radio/select option INSIDE a known
  // field container (by data-field-path candidates) to its target label. Some
  // Ashby tenants ignore a plain label.click() for radios (click lands, React
  // onChange never fires) so the option reads UNCHECKED at submit and the POST
  // banks "Missing entry for required field". This locates the container, finds
  // the option whose label matches `target`, then commits via a TRUSTED pointer
  // sequence + native checked-setter + input/change events. Idempotent.
  const {field_paths, target} = args;
  const tnorm = (target || '').trim().toLowerCase();
  let cont = null;
  for (const fp of (field_paths || [])) {
    cont = document.querySelector(`[data-field-path="${fp}"]`);
    if (cont) break;
  }
  if (!cont) {
    // fallback: a fieldset/div whose label text leads with the question is hard
    // to key here; bail so caller can log no-container.
    return {ok:false, reason:'no-container'};
  }
  // Gather candidate option rows: a real radio input + its visible label text.
  const rows = [];
  cont.querySelectorAll('label').forEach(lab => {
    const t = (lab.innerText || '').trim();
    if (!t) return;
    let inp = null;
    const forId = lab.getAttribute('for');
    if (forId) inp = document.getElementById(forId);
    if (!inp) inp = lab.querySelector('input[type=radio], input[type=checkbox]');
    if (!inp) {
      // input may be a sibling within the same row container
      const row = lab.closest('div');
      if (row) inp = row.querySelector('input[type=radio], input[type=checkbox]');
    }
    rows.push({lab, t, inp});
  });
  // Choose the row matching target (exact, then contains, then startswith).
  let pick = rows.find(r => r.t.toLowerCase() === tnorm)
          || rows.find(r => r.t.toLowerCase().includes(tnorm) && tnorm.length > 2)
          || rows.find(r => tnorm.includes(r.t.toLowerCase()) && r.t.length > 2);
  if (!pick) return {ok:false, reason:'no-option-match', target, opts: rows.map(r => r.t)};
  const {lab, inp} = pick;
  const fire = (el) => {
    try { el.scrollIntoView({block:'center', behavior:'instant'}); } catch(e){}
    const r = el.getBoundingClientRect();
    const ev = {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,pointerType:'mouse',button:0,pointerId:1,isPrimary:true};
    el.dispatchEvent(new PointerEvent('pointerdown', ev));
    el.dispatchEvent(new MouseEvent('mousedown', ev));
    el.dispatchEvent(new PointerEvent('pointerup', ev));
    el.dispatchEvent(new MouseEvent('mouseup', ev));
    el.dispatchEvent(new MouseEvent('click', ev));
  };
  // 1) trusted-click the label (registers in React for most tenants)
  fire(lab);
  // 2) if we have the input, trusted-click it too + force-set checked
  if (inp) {
    if (!inp.checked) fire(inp);
    if (!inp.checked) { try { inp.click(); } catch(e){} }
    if (!inp.checked) {
      try {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked').set;
        setter.call(inp, true);
      } catch(e){}
      inp.dispatchEvent(new Event('input', {bubbles:true}));
      inp.dispatchEvent(new Event('change', {bubbles:true}));
    }
    return {ok:true, checked: !!inp.checked, picked: pick.t};
  }
  // No input handle: the label click is our best effort.
  return {ok:true, checked: null, picked: pick.t, note:'no-input-handle'};
}"""
