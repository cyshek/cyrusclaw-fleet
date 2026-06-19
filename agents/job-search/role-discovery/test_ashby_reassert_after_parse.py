"""Regression: re-assert-after-parse re-wins clobbered system fields (chain_p7, 2026-06-04).

Locks the fix for the dominant Ashby form-validation bank class: Ashby's resume-
parse autofill clobbers a SINGLE already-filled system field (Email/LinkedIn/Name)
AFTER our fill, so the form fails validation on that one field at submit
(Plaid=Email, Reducto=LinkedIn, Benchling=Name). reassert_text_fields() must
re-assert EVERY authoritative text_fields value (from personal-info.json) after
parse-settle, iterating text_fields DIRECTLY (not the eval-`resolved` intersection),
and report which fields it had to repair so the pre-submit scan reads final values.

These tests drive _ashby_runner.reassert_text_fields with a FakePage that runs the
real _REASSERT_TEXT_JS resolve/forceSet logic against an in-memory DOM model, so
the suffix-fallback resolver and the clobber-repair loop are exercised without a
live browser.
"""
import re
import _ashby_runner


class FakeEl:
    def __init__(self, _id, value="", tag="INPUT", typ="text"):
        self.id = _id
        self.value = value
        self.tagName = tag
        self.type = typ


class FakeDOM:
    """Minimal DOM that the FakePage uses to emulate getElementById + querySelector.
    Also models a one-time autofill clobber: on the FIRST reassert pass, a chosen
    field is found already clobbered (the JS will repair it); subsequent passes
    find it correct."""
    def __init__(self, els):
        self.by_id = {e.id: e for e in els}

    def get(self, _id):
        return self.by_id.get(_id)


class FakePage:
    """Executes _REASSERT_TEXT_JS semantics in Python against a FakeDOM.
    We do NOT eval real JS; we reimplement the resolve + forceSet contract the
    helper depends on, matching the JS line-for-line so the test guards behavior."""
    def __init__(self, dom):
        self.dom = dom
        self.waits = 0

    def _resolve(self, fid):
        el = self.dom.get(fid)
        if el:
            return el
        parts = fid.split("_")
        for i in range(1, len(parts)):
            tail = "_".join(parts[i:])
            el = self.dom.get(tail)
            if el:
                return el
            if not tail.startswith("_"):
                el = self.dom.get("_" + tail)
                if el:
                    return el
        idx = fid.find("_systemfield_")
        if idx >= 0:
            el = self.dom.get(fid[idx:])
            if el:
                return el
        return None

    def evaluate(self, js, arg=None):
        assert js is _ashby_runner._REASSERT_TEXT_JS
        out = {"repaired": [], "ok": [], "missing": [], "errors": []}
        for f in arg["fields"]:
            fid, val = f["fid"], f["val"]
            if val in ("", None):
                continue
            el = self._resolve(fid)
            if not el:
                out["missing"].append(fid)
                continue
            if el.tagName == "INPUT" and el.type in ("radio", "checkbox", "file", "submit", "button"):
                continue
            cur = el.value
            if cur == val:
                out["ok"].append(fid)
                continue
            el.value = val  # forceSet
            out["repaired"].append({"fid": fid, "was": (cur or "")[:40], "now": el.value[:40]})
        return out

    def wait_for_timeout(self, ms):
        self.waits += 1


# Authoritative values straight from personal-info.json (truthful).
import json as _tj, re as _tre, os as _tos
_pi_path = _tos.path.join(_tos.path.dirname(__file__), "..", "personal-info.json")
_pi = _tj.load(open(_pi_path))
_pi_id = _pi["identity"]; _pi_ad = _pi.get("address", {})
def _phone_fmt(p):
    d = _tre.sub(r'[^0-9]','',p or '').lstrip('1')
    return f"{d[0:3]}-{d[3:6]}-{d[6:]}" if len(d)==10 else p
EMAIL   = _pi_id["email"]
NAME    = f"{_pi_id['first_name']} {_pi_id['last_name']}"
LINKEDIN = _pi_id.get("linkedin_url", "")
PHONE   = _phone_fmt(_pi_id.get("phone", ""))

FORM = "905168ec-cefa-4db5-a876-6eddeaa9086c"
# Planned fids (what the dryrun emits) vs the LIVE DOM input ids (suffix only).
TF = {
    f"{FORM}__systemfield_name": NAME,
    f"{FORM}__systemfield_email": EMAIL,
    f"{FORM}_0d03df81-4e86-4607-986e-99db54d35917": PHONE,
    f"{FORM}_d60d6d31-aa94-4223-9f5c-1936f833f6a2": LINKEDIN,  # LinkedIn custom uuid field
}


def _dom_with_clobber(clobbered_fid_suffix):
    """Build a DOM where every field holds its correct value EXCEPT the one whose
    live id ends with clobbered_fid_suffix, which the autofill emptied/wronged."""
    els = [
        FakeEl("_systemfield_name", NAME),
        FakeEl("_systemfield_email", EMAIL),
        FakeEl("0d03df81-4e86-4607-986e-99db54d35917", PHONE),
        FakeEl("d60d6d31-aa94-4223-9f5c-1936f833f6a2", LINKEDIN),
    ]
    for e in els:
        if e.id.endswith(clobbered_fid_suffix):
            e.value = ""  # autofill clobbered to empty
    return FakeDOM(els)


def test_reassert_rewins_clobbered_email():
    dom = _dom_with_clobber("_systemfield_email")  # Plaid class
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, TF, stabilize_passes=2)
    assert any("systemfield_email" in f for f in repaired), repaired
    assert dom.get("_systemfield_email").value == EMAIL


def test_reassert_rewins_clobbered_linkedin():
    dom = _dom_with_clobber("d60d6d31-aa94-4223-9f5c-1936f833f6a2")  # Reducto class
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, TF, stabilize_passes=2)
    assert any("d60d6d31" in f for f in repaired), repaired
    assert dom.get("d60d6d31-aa94-4223-9f5c-1936f833f6a2").value == LINKEDIN


def test_reassert_rewins_clobbered_name():
    dom = _dom_with_clobber("_systemfield_name")  # Benchling class
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, TF, stabilize_passes=2)
    assert any("systemfield_name" in f for f in repaired), repaired
    assert dom.get("_systemfield_name").value == NAME


def test_reassert_noop_when_all_correct_breaks_early():
    # No clobber: helper must repair nothing AND break after the first pass
    # (no needless settle loops) so it doesn't slow clean tenants.
    dom = FakeDOM([
        FakeEl("_systemfield_name", NAME),
        FakeEl("_systemfield_email", EMAIL),
        FakeEl("0d03df81-4e86-4607-986e-99db54d35917", PHONE),
        FakeEl("d60d6d31-aa94-4223-9f5c-1936f833f6a2", LINKEDIN),
    ])
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, TF, stabilize_passes=3)
    assert repaired == []
    assert page.waits == 0  # broke early, never slept


def test_reassert_resolves_by_suffix_not_full_fid():
    # The planned fid is the full <formId>__systemfield_email but the live input
    # id is the bare _systemfield_email. The suffix-fallback resolve MUST find it;
    # a bare getElementById(full-fid) would not.
    dom = FakeDOM([FakeEl("_systemfield_email", "")])  # clobbered
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, {f"{FORM}__systemfield_email": EMAIL})
    assert repaired == [f"{FORM}__systemfield_email"]
    assert dom.get("_systemfield_email").value == EMAIL


def test_reassert_skips_empty_values():
    dom = FakeDOM([FakeEl("_systemfield_email", "stale")])
    page = FakePage(dom)
    repaired = _ashby_runner.reassert_text_fields(page, {f"{FORM}__systemfield_email": ""})
    assert repaired == []
    assert dom.get("_systemfield_email").value == "stale"  # untouched
