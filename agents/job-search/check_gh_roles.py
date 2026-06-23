import requests, time

checks = [
    ("21shares", "5823209004"),
    ("chime", "8530421002"),
    ("figma", "5837760004"),
    ("figma", "6009613004"),
    ("nice", "4847972101"),
    ("nice", "4849399101"),
    ("otter", "8402672002"),
    ("pathrobotics", "8571279002"),
    ("securitize", "4173649009"),
    ("yipitdata", "8002296"),
    ("ziprecruiter", "7354406"),
]

for org, job_id in checks:
    url = f"https://boards-api.greenhouse.io/v1/boards/{org}/jobs/{job_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f"OPEN   {org}-{job_id}: {d.get('title','?')[:60]}")
        elif r.status_code == 404:
            print(f"CLOSED {org}-{job_id}")
        else:
            print(f"UNKWN  {org}-{job_id}: HTTP {r.status_code}")
    except Exception as e:\n        print(f"ERROR  {org}-{job_id}: {e}")
    time.sleep(0.3)
