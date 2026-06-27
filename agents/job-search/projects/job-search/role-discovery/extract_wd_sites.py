#!/usr/bin/env python3
import time, requests, re
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
def find(url, timeout=12):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)
        hits = re.findall(r"myworkdayjobs\.com/([A-Za-z0-9_]+)", r.text)
        return list(set(hits))
    except:
        return []
tests = [
    ("Verizon", "https://www.verizon.com/about/work-at-verizon"),
    ("Honeywell", "https://careers.honeywell.com"),
    ("L3Harris", "https://careers.l3harris.com"),
    ("Fidelity", "https://jobs.fidelity.com"),
    ("John Deere", "https://careers.deere.com"),
    ("Caterpillar", "https://cat.jobs"),
    ("Eaton", "https://www.eaton.com/us/en-us/company/careers.html"),
    ("GE Aerospace", "https://jobs.gecareers.com/aviation/global/en"),
    ("Emerson", "https://hubs.emerson.com/talent-community/job-search"),
    ("Collins Aerospace", "https://www.collinsaerospace.com/careers"),
    ("SAP", "https://jobs.sap.com"),
    ("Splunk", "https://www.splunk.com/en_us/careers.html"),
    ("Sony", "https://www.sonyjobs.com"),
    ("Nutanix", "https://www.nutanix.com/careers"),
    ("Unity", "https://careers.unity.com"),
    ("Roku", "https://www.roku.com/en-us/about/jobs"),
    ("NetApp", "https://www.netapp.com/us/careers/index.aspx"),
    ("Juniper", "https://jobs.juniper.net"),
    ("Texas Instruments", "https://careers.ti.com"),
    ("Lam Research", "https://www.lamresearch.com/career"),
    ("Synopsys", "https://careers.synopsys.com"),
    ("Block", "https://www.block.xyz/careers"),
    ("Best Buy", "https://jobs.bestbuy.com"),
    ("Paramount", "https://www.paramount.com/careers"),
    ("Electronic Arts", "https://jobs.ea.com"),
    ("Activision", "https://www.activisionblizzard.com/careers"),
    ("Thomson Reuters", "https://jobs.thomsonreuters.com"),
    ("Cloudflare", "https://www.cloudflare.com/careers/jobs/"),
    ("Twilio", "https://www.twilio.com/en-us/company/jobs"),
    ("DocuSign", "https://www.docusign.com/company/careers"),
    ("Dropbox", "https://jobs.dropbox.com"),
    ("Okta", "https://www.okta.com/company/careers/"),
    ("MongoDB", "https://www.mongodb.com/careers"),
    ("Elastic", "https://jobs.elastic.co"),
    ("GitLab", "https://about.gitlab.com/jobs/"),
    ("Cohesity", "https://www.cohesity.com/company/careers/"),
    ("Rapid7", "https://www.rapid7.com/company/careers/"),
    ("Teradata", "https://careers.teradata.com"),
    ("Informatica", "https://www.informatica.com/about-us/careers.html"),
    ("Dynatrace", "https://www.dynatrace.com/company/careers/"),
    ("F5", "https://www.f5.com/company/careers"),
    ("Fortinet", "https://www.fortinet.com/corporate/careers.html"),
    ("Datadog", "https://www.datadoghq.com/careers/"),
    ("American Express", "https://aexp.jobs"),
]
for name, url in tests:
    sites = find(url)
    if sites:
        print(f"FOUND {name}: {sites[:5]}")
    else:
        print(f"NOTFOUND {name}")
    time.sleep(0.2)
