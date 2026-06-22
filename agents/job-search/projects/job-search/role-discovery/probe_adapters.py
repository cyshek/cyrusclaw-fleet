#!/usr/bin/env python3
"""Probe ATS APIs for companies with no adapter."""
import json
import sys
import time
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def http_get(url, timeout=12, post=False, data=b""):
    headers = {"User-Agent": UA, "Accept": "application/json,text/html,*/*"}
    if post:
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, headers=headers, data=data, method="POST")
    else:
        req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def probe_greenhouse(slug):
    url = "https://boards-api.greenhouse.io/v1/boards/%s/jobs" % slug
    status, body = http_get(url)
    if status == 200:
        try:
            jobs = json.loads(body).get("jobs", [])
            return ("greenhouse", slug, len(jobs)) if jobs else None
        except Exception:
            return None
    return None


def probe_ashby(slug):
    url = "https://api.ashbyhq.com/posting-api/job-board/%s" % slug
    status, body = http_get(url)
    if status == 200:
        try:
            jobs = json.loads(body).get("jobs", [])
            return ("ashby", slug, len(jobs)) if jobs else None
        except Exception:
            return None
    return None


def probe_lever(slug):
    url = "https://api.lever.co/v0/postings/%s?mode=json" % slug
    status, body = http_get(url)
    if status == 200:
        try:
            data = json.loads(body)
            if isinstance(data, list) and data:
                return ("lever", slug, len(data))
        except Exception:
            return None
    return None


def probe_smartrecruiters(slug):
    url = "https://api.smartrecruiters.com/v1/companies/%s/postings" % slug
    status, body = http_get(url)
    if status == 200:
        try:
            data = json.loads(body)
            jobs = data.get("content", [])
            total = data.get("totalFound", len(jobs))
            return ("smartrecruiters", slug, total) if jobs else None
        except Exception:
            return None
    return None


def probe_workable(slug):
    url = "https://apply.workable.com/api/v3/accounts/%s/jobs" % slug
    status, body = http_get(url, post=True, data=b"{}")
    if status == 200:
        try:
            jobs = json.loads(body).get("results", [])
            return ("workable", slug, len(jobs)) if jobs else None
        except Exception:
            return None
    return None


def probe_all(slug):
    results = []
    for fn in (probe_greenhouse, probe_ashby, probe_lever, probe_smartrecruiters, probe_workable):
        try:
            r = fn(slug)
            if r:
                results.append(r)
        except Exception:
            pass
        time.sleep(0.12)
    return results


if __name__ == "__main__":
    slugs = sys.argv[1:]
    for slug in slugs:
        res = probe_all(slug)
        if res:
            for adapter, s, n in res:
                print("  HIT %s: %s slug=%s jobs=%s" % (slug, adapter, s, n))
        else:
            print("  MISS %s" % slug)
