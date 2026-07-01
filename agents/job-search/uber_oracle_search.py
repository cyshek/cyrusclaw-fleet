import json
import urllib.request
import sys

url = "https://iaziqy.fa.us6.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?expand=all&onlyData=true&finder=findReqs;siteNumber=CX_1001,language=en&limit=100"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    items = data.get('items', [])
    print("Total items: %d" % len(items))
    for item in items:
        title = item.get('Title', '?')
        req_num = item.get('Id', '?')
        print("  %s: %s" % (req_num, title))
except Exception as e:\n    print("err: %s" % e)
    sys.exit(1)
