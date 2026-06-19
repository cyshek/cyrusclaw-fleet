#!/usr/bin/env python3
"""Tests for FRESH-ACCOUNT APPLY as the default Workday path
(workday-fresh-account-fix 2026-06-08, Cyrus option A).

STANDING RULE BEING LOCKED
--------------------------
"Workday ALWAYS applies with FRESH information from the customized resume; NEVER
autofill/reuse saved-profile data because it is likely outdated." (Cyrus, 2026-06-08)

WHY THIS EXISTS
---------------
Prior failed runs polluted the persistent per-tenant Workday accounts with duplicate,
read-only, UNCOMMITTABLE work-experience blocks. Those accounts then auto-prefilled My
Experience -> EXIT 9 (_WE_PREFILL_UNCOMMITTABLE), and work-history NEVER came from the
tailored resume. 6 rows were blocked this way: Philips 1466, RBI/Popeyes 2010 (18 dup
blocks), Nordstrom 2049, EXFO 2121 (5 dup), Nvidia 2829, HPE 2830.

THE FIX (locked here):
  * resolve_account_for_tenant() makes the create-vs-signin decision EXPLICIT + logged
    (no cold-start form-render heuristic). Dupe-class / polluted tenants default to
    CREATE-FRESH: a brand-new gmail '+' alias (so verify emails still land in the inbox
    gmail_imap reads) + strong random password, persisted to .workday-creds.json so a
    later run signs into the SAME fresh account. A known-good fresh alias is reused
    ('signin_fresh'); only mint a new one when needed.
  * ensure_signed_in() branches straight to _create_fresh_account() in create_fresh mode
    and NEVER touches the polluted saved-profile sign-in form.
  * populate_work_history() asserts/logs the work-history starts EMPTY on a fresh account
    and suppresses EXIT-9 there (a fresh account has no legit saved profile).
  * A NEW failure mode -> EXIT 10 ('workday-create-account-email-verify-timeout') when
    Workday's create-account verification code never arrives, instead of silently passing
    or falling back to the polluted account.

These mix SOURCE-LEVEL CONTRACT tests (guard the wiring stays in place) with BEHAVIORAL
tests that exercise the alias generator + branch decision + persistence against a TEMP
creds file (the real .workday-creds.json is never touched). NO live browser is used.
"""
import importlib.util
import json
import pathlib
import re
import string
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_workday_runner", HERE / "_workday_runner.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

# ---- Personal info (test fixtures derive aliases from real email) ----------
_PI = json.loads((HERE.parent / "personal-info.json").read_text())
_BASE_EMAIL = _PI["identity"]["email"]
_EMAIL_USER = _BASE_EMAIL.split("@")[0] if "@" in _BASE_EMAIL else _BASE_EMAIL
_EMAIL_DOM  = _BASE_EMAIL.split("@")[1] if "@" in _BASE_EMAIL else "gmail.com"
def _alias(tag): return f"{_EMAIL_USER}+{tag}@{_EMAIL_DOM}"

SRC = (HERE / "_workday_runner.py").read_text()


def _func_body(name):
    start = SRC.index(f"def {name}(")
    nxt = SRC.index("\ndef ", start + 1)
    return SRC[start:nxt]


def _temp_creds(tenants):
    """Write a synthetic creds file into a temp dir and point wd.ROOT at it. Returns the
    temp Path. The real .workday-creds.json is NEVER touched."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    creds = {
        "shared_email": _BASE_EMAIL,
        "shared_password": "SharedPW123!",
        "tenants": tenants,
    }
    (tmp / ".workday-creds.json").write_text(json.dumps(creds))
    wd.ROOT = tmp  # redirect all creds reads/writes to the temp file
    return tmp


# ===========================================================================
# 1. STRONG PASSWORD GENERATOR — unique + meets Workday complexity.
# ===========================================================================

def test_strong_password_unique_and_complex():
    pws = {wd._gen_strong_password() for _ in range(40)}
    assert len(pws) == 40, "passwords must be unique across calls"
    for pw in pws:
        assert len(pw) >= 12, "password too short"
        assert any(c.islower() for c in pw), f"needs lowercase: {pw}"
        assert any(c.isupper() for c in pw), f"needs uppercase: {pw}"
        assert any(c.isdigit() for c in pw), f"needs digit: {pw}"
        assert any(c in "!@#$%*?-_" for c in pw), f"needs symbol: {pw}"


# ===========================================================================
# 2. FRESH ALIAS GENERATOR — gmail '+' format off the base inbox, unique per
#    attempt (datestamp), idempotent within a run, tenant sanitized.
# ===========================================================================

def test_base_inbox_collapses_plus_tag():
    _temp_creds({})
    base = wd._gmail_base_inbox()
    assert "@" in base
    assert "+" not in base.split("@")[0], "base inbox local-part must not carry a +tag"


def test_alias_is_gmail_plus_format_off_base():
    _temp_creds({})
    a = wd._gen_fresh_alias("exfo", now=1_000_000_000)
    base_local = wd._gmail_base_inbox().split("@")[0]
    assert a.endswith("@gmail.com"), f"alias must keep the base domain: {a}"
    assert a.split("@")[0].startswith(base_local + "+wd-exfo-"), (
        f"alias must be <base>+wd-<tenant>-<stamp>: {a}"
    )


def test_alias_idempotent_same_now_unique_across_time():
    _temp_creds({})
    a1 = wd._gen_fresh_alias("exfo", now=1_000_000_000)
    a2 = wd._gen_fresh_alias("exfo", now=1_000_000_000)
    a3 = wd._gen_fresh_alias("exfo", now=1_000_000_060)  # +60s -> next minute
    assert a1 == a2, "same timestamp must produce the same alias (idempotent within a run)"
    assert a1 != a3, "a later attempt (different minute) must mint a NEW alias (no collision)"


def test_alias_tenant_is_sanitized():
    _temp_creds({})
    a = wd._gen_fresh_alias("RBI/Popeyes!", now=1_000_000_000)
    assert "+wd-rbipopeyes-" in a, f"tenant must be sanitized to gmail-safe chars: {a}"


# ===========================================================================
# 3. CREATE-FRESH is the GLOBAL DEFAULT for ALL tenants (Cyrus directive
#    2026-06-08); alias is PERSISTED. (dupe-class no longer gates the decision.)
# ===========================================================================

def test_dupe_class_set_covers_the_six_blocked_tenants():
    assert wd.DUPE_CLASS_TENANTS == {"philips", "rbi", "nordstrom", "exfo", "nvidia", "hpe"}, (
        "the dupe-class set must be exactly the 6 polluted-profile tenants"
    )


def test_dupe_class_defaults_create_fresh_and_persists_alias():
    tmp = _temp_creds({"exfo": {"email": _alias("exfo"), "account_created": True}})
    email, pw, mode = wd.resolve_account_for_tenant("exfo")
    assert mode == "create_fresh", "a polluted dupe-class tenant must default to create_fresh"
    assert "+wd-exfo-" in email, "create_fresh must use a freshly-minted wd-<tenant> alias"
    # persisted so a later run can sign into the SAME fresh account (never stranded)
    saved = json.load(open(tmp / ".workday-creds.json"))["tenants"]["exfo"]
    assert saved.get("fresh_alias") == email, "fresh alias must be persisted to creds"
    assert saved.get("fresh_password") == pw, "fresh password must be persisted to creds"
    assert saved.get("fresh_polluted") is False, "freshly-minted alias starts not-polluted"


def test_known_good_fresh_alias_is_reused_not_reminted():
    _temp_creds({"hpe": {"fresh_alias": _alias("wd-hpe-202606080000"),
                          "fresh_password": "FreshPW9!", "fresh_created": True}})
    email, pw, mode = wd.resolve_account_for_tenant("hpe")
    assert mode == "signin_fresh", "a known-good fresh alias must be SIGNED INTO, not re-minted"
    assert email == _alias("wd-hpe-202606080000")
    assert pw == "FreshPW9!"


def test_polluted_fresh_alias_is_reminted():
    _temp_creds({"nordstrom": {"fresh_alias": _alias("wd-nordstrom-old"),
                               "fresh_password": "X1!", "fresh_polluted": True}})
    email, _pw, mode = wd.resolve_account_for_tenant("nordstrom")
    assert mode == "create_fresh", "a fresh alias flagged polluted must be re-minted, not reused"
    assert email != _alias("wd-nordstrom-old")
    assert "+wd-nordstrom-" in email


def test_clean_tenant_defaults_create_fresh():
    """GLOBAL FRESH DEFAULT (Cyrus directive 2026-06-08): a clean, non-dupe tenant with NO
    pre-existing fresh alias must now DEFAULT to create_fresh -- NOT legacy sign-in. The
    runner must fill every field from the tailored resume and never trust Workday's saved-
    profile autofill, so fresh-account is the default for ALL tenants. (Supersedes the old
    test_clean_tenant_keeps_legacy_signin contract.)"""
    tmp = _temp_creds({"salesforce": {"email": _alias("salesforce"), "account_created": True}})
    email, pw, mode = wd.resolve_account_for_tenant("salesforce")
    assert mode == "create_fresh", "a clean tenant must DEFAULT to create_fresh (global fresh default)"
    assert "+wd-salesforce-" in email, "create_fresh must use a freshly-minted wd-<tenant> alias"
    # persisted so a later run signs into the SAME fresh account (never stranded)
    saved = json.load(open(tmp / ".workday-creds.json"))["tenants"]["salesforce"]
    assert saved.get("fresh_alias") == email, "fresh alias must be persisted to creds"
    assert saved.get("fresh_password") == pw, "fresh password must be persisted to creds"
    assert saved.get("fresh_polluted") is False, "freshly-minted alias starts not-polluted"


def test_force_fresh_and_force_legacy_overrides():
    """NEW anti-pollution contract (workday-no-legacy-fallback 2026-06-09, Cyrus):
    force_fresh=False NO LONGER silently signs into a legacy profile in normal operation.
    It is REFUSED (forced to create_fresh) UNLESS the loud env override
    WORKDAY_ALLOW_LEGACY_PROFILE=1 is set. This closes the duplicate-WE-block pollution risk
    completely -- there is no production code path that signs into a legacy profile."""
    import os as _os
    _saved = _os.environ.pop("WORKDAY_ALLOW_LEGACY_PROFILE", None)
    try:
        _temp_creds({"salesforce": {"email": _alias("salesforce")},
                     "exfo": {"email": _alias("exfo")},
                     "workday": {"email": _alias("workday")}})
        # force_fresh=True on a clean tenant -> create_fresh (unchanged)
        _e, _p, m1 = wd.resolve_account_for_tenant("salesforce", force_fresh=True)
        assert m1 == "create_fresh", "force_fresh must mint fresh even for a clean tenant"
        # force_fresh=False WITHOUT the env override is now REFUSED -> create_fresh (NOT
        # signin_legacy). Anti-pollution policy: no silent legacy fallback in production.
        _temp_creds({"exfo": {"email": _alias("exfo")}})
        _e2, _p2, m2 = wd.resolve_account_for_tenant("exfo", force_fresh=False)
        assert m2 == "create_fresh", (
            "force_fresh=False without WORKDAY_ALLOW_LEGACY_PROFILE=1 must REFUSE legacy and "
            "force a FRESH account (dupe tenant)")
        _temp_creds({"workday": {"email": _alias("workday")}})
        _e3, _p3, m3 = wd.resolve_account_for_tenant("workday", force_fresh=False)
        assert m3 == "create_fresh", (
            "force_fresh=False without the env override must REFUSE legacy on a CLEAN tenant too")
    finally:
        if _saved is None:
            _os.environ.pop("WORKDAY_ALLOW_LEGACY_PROFILE", None)
        else:
            _os.environ["WORKDAY_ALLOW_LEGACY_PROFILE"] = _saved


def test_legacy_profile_refused_without_env_override():
    """FIX 1 (workday-no-legacy-fallback 2026-06-09): explicit assertion that the ONLY way to
    reach signin_legacy is force_fresh=False AND WORKDAY_ALLOW_LEGACY_PROFILE=1. Every other
    combination keeps the apply on a fresh/clean account so no legacy saved-profile autofill
    (the duplicate-uncommittable-WE-block / EXIT-9 pollution source) can ever occur."""
    import os as _os
    _saved = _os.environ.pop("WORKDAY_ALLOW_LEGACY_PROFILE", None)
    try:
        # (a) override UNSET + force_fresh=False -> refused -> create_fresh
        _temp_creds({"exfo": {"email": _alias("exfo")}})
        _e, _p, m = wd.resolve_account_for_tenant("exfo", force_fresh=False)
        assert m == "create_fresh", "legacy must be refused (create_fresh) when env override is unset"

        # (b) override SET=1 + force_fresh=False -> legacy explicitly allowed -> signin_legacy
        _os.environ["WORKDAY_ALLOW_LEGACY_PROFILE"] = "1"
        _temp_creds({"exfo": {"email": _alias("exfo")}})
        _e2, _p2, m2 = wd.resolve_account_for_tenant("exfo", force_fresh=False)
        assert m2 == "signin_legacy", (
            "signin_legacy must be reachable ONLY with force_fresh=False AND "
            "WORKDAY_ALLOW_LEGACY_PROFILE=1")

        # (c) override SET=1 but force_fresh=True -> fresh still wins (override only un-gates
        # legacy, it never forces it)
        _temp_creds({"workday": {"email": _alias("workday")}})
        _e3, _p3, m3 = wd.resolve_account_for_tenant("workday", force_fresh=True)
        assert m3 == "create_fresh", "force_fresh=True must mint fresh even with the legacy override set"

        # (d) override SET=1 but DEFAULT (force_fresh=None) -> still create_fresh (override only
        # matters when legacy is explicitly requested via force_fresh=False)
        _temp_creds({"salesforce": {"email": _alias("salesforce")}})
        _e4, _p4, m4 = wd.resolve_account_for_tenant("salesforce")
        assert m4 == "create_fresh", "default must stay create_fresh even with the legacy override set"
    finally:
        if _saved is None:
            _os.environ.pop("WORKDAY_ALLOW_LEGACY_PROFILE", None)
        else:
            _os.environ["WORKDAY_ALLOW_LEGACY_PROFILE"] = _saved


def test_no_production_codepath_signs_into_legacy_source():
    """SOURCE-CONTRACT (FIX 1): guard that resolve_account_for_tenant() gates signin_legacy
    behind the WORKDAY_ALLOW_LEGACY_PROFILE env flag and that a bare force_fresh=False is
    refused in-source. If a future edit removes the env gate this test fails loudly."""
    body = _func_body("resolve_account_for_tenant")
    assert 'WORKDAY_ALLOW_LEGACY_PROFILE' in body, (
        "legacy sign-in must be gated behind the WORKDAY_ALLOW_LEGACY_PROFILE env flag")
    assert 'REFUSED' in body or 'REFUSE' in body.upper(), (
        "a bare force_fresh=False must be explicitly REFUSED (anti-pollution) in-source")
    # The refuse-branch must force want_fresh True when legacy is requested but not allowed.
    assert 'force_fresh is False and not _allow_legacy' in body, (
        "the refuse condition (force_fresh is False AND not allow_legacy) must be present")


# ===========================================================================
# 4. WIRING CONTRACT — run() sets the mode globals; ensure_signed_in() branches
#    to create-fresh; the EXIT-10 reset + bank are present.
# ===========================================================================

def test_run_resolves_account_and_sets_mode_globals():
    body = _func_body("run")
    assert "resolve_account_for_tenant(tenant" in body, "run() must use resolve_account_for_tenant"
    assert "global EMAIL, PW, _ACCOUNT_MODE, _FRESH_VERIFY_PW" in body, (
        "run() must declare the account-mode globals"
    )
    assert "_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL = None" in body, (
        "run() must reset the email-verify-timeout flag per row"
    )


def test_ensure_signed_in_branches_to_create_fresh():
    body = _func_body("ensure_signed_in")
    assert 'globals().get("_ACCOUNT_MODE") == "create_fresh"' in body, (
        "ensure_signed_in must branch on create_fresh mode"
    )
    assert "_create_fresh_account(page, tenant" in body, (
        "create_fresh mode must call _create_fresh_account and NOT sign into the saved profile"
    )


def test_create_fresh_helper_exists_and_is_robust():
    body = _func_body("_create_fresh_account")
    assert "createAccountSubmitButton" in body, "must drive Workday's create-account submit"
    assert "wait_for_verification_code" in body, "must wait for the email verification code"
    assert "_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL" in body, (
        "must set the email-verify-timeout flag on a hard verify failure"
    )
    assert "WD_CREATE_VERIFY_TIMEOUT_S" in body, "must use a bounded verify timeout (no gmail thrash)"


# ===========================================================================
# 5. EXIT 10 — distinct new code for create-account email-verify timeout. NOT
#    confused with the generic sign-in block (EXIT 2), and evaluated BEFORE it.
# ===========================================================================

def test_exit10_banked_for_email_verify_timeout():
    body = _func_body("run")
    assert 'globals().get("_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL")' in body, (
        "run() must read the email-verify-timeout flag"
    )
    idx = body.find('globals().get("_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL")')
    window = body[idx: idx + 400]
    assert "return 10" in window, "the email-verify-timeout fast-fail must return EXIT 10"
    assert "workday-create-account-email-verify-timeout" in window, (
        "the fast-fail must log the distinct bank reason"
    )


def test_exit10_is_checked_before_generic_exit2():
    """Within run()'s ensure_signed_in failure handler, the EXIT-10 check must precede the
    generic EXIT-2 sign-in block so a verify timeout is never mislabeled as a sign-in block."""
    body = _func_body("run")
    ff = body.find('globals().get("_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL")')
    e2 = body.find("RESULT: BLOCKED at sign-in/account-create")
    assert ff != -1 and e2 != -1, "expected both the EXIT-10 check and the EXIT-2 bank in run()"
    assert ff < e2, "EXIT-10 (email-verify timeout) must be checked BEFORE the generic EXIT-2"


def test_exit10_is_distinct_only_for_verify_timeout():
    body = _func_body("run")
    for m in re.finditer(r"return 10\b", body):
        ctx = body[max(0, m.start() - 500): m.start()]
        assert "_CREATE_ACCOUNT_EMAIL_VERIFY_FAIL" in ctx or "email-verify-timeout" in ctx, (
            "every `return 10` in run() must be the create-account email-verify-timeout fast-fail"
        )


# ===========================================================================
# 6. FRESH-FILL GUARANTEE — populate_work_history asserts EMPTY start on a fresh
#    account and SUPPRESSES EXIT-9 there (no saved profile => no profile-prefill bank).
# ===========================================================================

def test_populate_asserts_fresh_empty_and_marks_source():
    body = _func_body("populate_work_history")
    assert '_ACCOUNT_MODE") in ("create_fresh", "signin_fresh")' in body, (
        "populate_work_history must detect a fresh-account run"
    )
    assert "FRESH-ACCOUNT ASSERT OK" in body, "must assert/log the empty-start contract on fresh accounts"
    assert "FRESH-FILL SOURCE" in body, "must log that the fill source is the tailored resume, not autofill"


def test_exit9_suppressed_on_fresh_account():
    body = _func_body("populate_work_history")
    # The EXIT-9 assignment must be guarded so it does NOT fire when _fresh_acct is true.
    assert "if _fresh_acct:" in body, "the uncommittable EXIT-9 setter must be guarded by the fresh-account flag"
    # Find the uncommittable assignment and confirm it sits in the else-branch (not fresh).
    set_idx = body.find("_WE_PREFILL_UNCOMMITTABLE = (")
    assert set_idx != -1, "expected the EXIT-9 flag assignment to still exist for legacy tenants"
    guard_idx = body.rfind("if _fresh_acct:", 0, set_idx)
    assert guard_idx != -1, "the EXIT-9 assignment must be downstream of a fresh-account guard"
    window = body[guard_idx: set_idx]
    assert "else" in window, "EXIT-9 must be banked only in the non-fresh (else) branch"
    assert "NOT EXIT-9" in body, "fresh-account path must explicitly log it is NOT banking EXIT-9"


# ===========================================================================
# 7. The existing EXIT-9 contract still holds for LEGACY tenants (regression
#    guard: the fresh-account change must not have disabled EXIT-9 entirely).
# ===========================================================================

def test_exit9_still_wired_for_legacy():
    body = _func_body("run")
    assert 'globals().get("_WE_PREFILL_UNCOMMITTABLE")' in body, (
        "EXIT-9 fast-fail must still be wired in the My-Experience branch"
    )
    idx = body.find('globals().get("_WE_PREFILL_UNCOMMITTABLE")')
    window = body[idx: idx + 400]
    assert "return 9" in window, "EXIT-9 must still return 9 for legacy uncommittable-prefill"


# ===========================================================================
# 8. CLI escape hatches exist.
# ===========================================================================

def test_cli_has_fresh_and_legacy_flags():
    assert "--fresh-account" in SRC and 'dest="fresh_account"' in SRC, "must expose --fresh-account"
    assert "--legacy-account" in SRC and 'dest="legacy_account"' in SRC, "must expose --legacy-account"


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
