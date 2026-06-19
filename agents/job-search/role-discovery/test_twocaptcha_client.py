"""Tests for twocaptcha_client — proxy parsing + task-shape selection (no live API)."""
import pytest
import twocaptcha_client as tc


def test_parse_proxy_at_form():
    # NOTE: dummy creds (RFC 5737 doc IP) — never commit real proxy creds to git.
    f = tc.parse_proxy("testuser:testpass@203.0.113.10:7949")
    assert f == {"proxyType": "http", "proxyAddress": "203.0.113.10",
                 "proxyPort": 7949, "proxyLogin": "testuser",
                 "proxyPassword": "testpass"}


def test_parse_proxy_at_form_with_scheme_and_slash():
    f = tc.parse_proxy("http://u:p@1.2.3.4:8080/")
    assert f["proxyAddress"] == "1.2.3.4" and f["proxyPort"] == 8080
    assert f["proxyLogin"] == "u" and f["proxyPassword"] == "p"


def test_parse_proxy_colon_form_with_creds():
    f = tc.parse_proxy("1.2.3.4:8080:user:pass")
    assert f == {"proxyType": "http", "proxyAddress": "1.2.3.4",
                 "proxyPort": 8080, "proxyLogin": "user", "proxyPassword": "pass"}


def test_parse_proxy_host_port_only():
    f = tc.parse_proxy("1.2.3.4:8080")
    assert f == {"proxyType": "http", "proxyAddress": "1.2.3.4", "proxyPort": 8080}
    assert "proxyLogin" not in f


def test_parse_proxy_empty_is_none():
    assert tc.parse_proxy("") is None
    assert tc.parse_proxy(None) is None
    assert tc.parse_proxy("   ") is None


def test_parse_proxy_garbage_raises():
    with pytest.raises(tc.TwoCaptchaError):
        tc.parse_proxy("not a proxy at all")


def test_client_no_key_raises():
    import os
    old = os.environ.pop("TWOCAPTCHA_API_KEY", None)
    try:
        tc._DOTENV_LOADED = True  # block dotenv load
        with pytest.raises(tc.TwoCaptchaDisabled):
            tc.TwoCaptchaClient(api_key="")
    finally:
        if old is not None:
            os.environ["TWOCAPTCHA_API_KEY"] = old
        tc._DOTENV_LOADED = False


def test_recaptcha_v3_always_proxyless():
    # 2Captcha has no proxy-backed v3; always proxyless even when proxy set
    c = tc.TwoCaptchaClient(api_key="x", proxy="u:p@1.2.3.4:8080")
    captured = {}
    c._solve = lambda task, keys, label: captured.update(task=task) or "TOKEN"
    c.recaptcha_v3("sitekey", "https://e.com")
    assert captured["task"]["type"] == "RecaptchaV3TaskProxyless"
    assert "proxyAddress" not in captured["task"]


def test_recaptcha_v3_picks_proxyless_when_no_proxy():
    c = tc.TwoCaptchaClient(api_key="x", proxy="")
    captured = {}
    c._solve = lambda task, keys, label: captured.update(task=task) or "TOKEN"
    c.recaptcha_v3("sitekey", "https://e.com")
    assert captured["task"]["type"] == "RecaptchaV3TaskProxyless"


def test_hcaptcha_proxyless_when_no_proxy():
    c = tc.TwoCaptchaClient(api_key="x", proxy="")
    captured = {}
    c._solve = lambda task, keys, label: captured.update(task=task) or "TOKEN"
    c.hcaptcha("sitekey", "https://jobs.lever.co/x")
    assert captured["task"]["type"] == "HCaptchaTaskProxyless"
