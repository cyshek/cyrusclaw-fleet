#!/usr/bin/env python3
import json, time, smtplib, sys, requests
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path

GMAIL = "cyshekari@gmail.com"
APP_PASS = "yjse lddd mhan gbpe"
RESULTS_FILE = "/home/azureuser/.openclaw/agents/making-money/workspace/outreach/results_v3.json"
SITELENS_AUDIT_URL = "https://sitelume.app/audit/?url="
HEADERS = {"User-Agent": "Mozilla/5.0"}

SKIP_DOMAINS = {
    'aaatoday.com',
    'aalawns.com',
    'aceautoshop.com',
    'adamselectrical.com',
    'affordableroofingpros.com',
    'allseasonshvac.net',
    'anchorpestcontrol.net',
    'betterroofingco.com',
    'bluefrogplumbing.com',
    'brightsparkelectric.com',
    'brownlawgroup.net',
    'bugbusters.com',
    'carrboroplumbing.com',
    'cityelectricservice.com',
    'ckconstruction.net',
    'clearvieweyecare.net',
    'comforthvacpro.com',
    'cornerstonedental.net',
    'cpapatelandparikh.com',
    'ctplumbingremodeling.com',
    'cutclean.com',
    'davisandassociateslaw.com',
    'deardental.com',
    'denverfamilydental.com',
    'dilippatelcpa.com',
    'elitehvacservices.com',
    'expertroofingservices.com',
    'familyplumbing.com',
    'familytreedental.com',
    'firemanpestcontrol.com',
    'fitnessfirstlocal.com',
    'foundations.construction',
    'garysautorepair.com',
    'gastleysautorepair.com',
    'gentledentalcare.com',
    'greatbearautoshop.com',
    'greenthumblandscaping.com',
    'hammondlawgroup.com',
    'happytailsanimalclinic.com',
    'harrisonconstruction.com',
    'heritage.builders',
    'hillcrestplumbing.com',
    'ironwillfitness.net',
    'itsdone.com',
    'jdjcpa.com',
    'jpacpa.com',
    'jwhvac.com',
    'kelleylegal.com',
    'lakesidedentalcare.com',
    'larsonplumbing.net',
    'ledger.cpa',
    'localinsuranceguide.com',
    'localroofingpros.com',
    'luxe.salon',
    'mainstreethomesellers.com',
    'martinlawfirm.com',
    'mclawoffice.com',
    'metroelectricians.com',
    'millerelectrical.net',
    'mirrormirrorsalon.com',
    'mjacsi.com',
    'oaktreelaw.com',
    'parkerandsons.com',
    'patellaw.com',
    'pawsandclawsvet.com',
    'peakconstruction.com',
    'pestshieldinc.com',
    'plumberdelandfl.com',
    'plumbline.com',
    'plumbpros.com',
    'portlanddentalgroup.com',
    'precision.builders',
    'precisionelectricco.com',
    'premieraircare.com',
    'premierlawn.com',
    'quickfix.repair',
    'reliable.repair',
    'reliableheatingandcooling.com',
    'riverside.plumbing',
    'sakurasalon.net',
    'sbasgroup.com',
    'smallsmiles.com',
    'smalltownbuilders.com',
    'stonecreeksalon.com',
    'stylesonbroadway.com',
    'summit.builders',
    'sunriselandscaping.com',
    'thompsonlawoffice.com',
    'truenorthsalon.com',
    'trustedrealtypros.com',
    'turnerlegalgroup.com',
    'visionplusoptometry.com',
    'vivadayspa.com',
    'voltmasterelectrical.com',
    'walkerlaw.net',
    'wdmdentalcenter.com',
    'westside-electric.com',
    'wilsonlawoffice.net',
    'wittpm.com',
    'yandllandscaping.com',
    'yourcommunitylawfirm.com',
    'yourneighborhoodinsurance.com',
}

TARGETS_BY_VERTICAL = {
    'optometry': [
        ('eyecareoflexington.com', 'info@eyecareoflexington.com'),
        ('triangleeyecare.com', 'contact@triangleeyecare.com'),
        ('alpineeyeclinic.com', 'info@alpineeyeclinic.com'),
        ('northwesteyecare.net', 'info@northwesteyecare.net'),
        ('sunshineeyecare.com', 'info@sunshineeyecare.com'),
        ('harborlightvision.com', 'info@harborlightvision.com'),
        ('ridgelineeyecare.com', 'info@ridgelineeyecare.com'),
        ('pinehursteye.com', 'info@pinehursteye.com'),
        ('lakeviewoptometry.com', 'info@lakeviewoptometry.com'),
        ('rivervieweyecare.com', 'info@rivervieweyecare.com'),
        ('mapleleafoptometry.com', 'info@mapleleafoptometry.com'),
        ('cedarvalleyeyecare.com', 'contact@cedarvalleyeyecare.com'),
        ('crystalclearvision.com', 'info@crystalclearvision.com'),
        ('horizoneyecare.net', 'info@horizoneyecare.net'),
        ('brighteyeoptometry.com', 'info@brighteyeoptometry.com'),
        ('vistaeye.com', 'info@vistaeye.com'),
        ('sunseteyeclinic.com', 'info@sunseteyeclinic.com'),
        ('clearfocusoptometry.com', 'info@clearfocusoptometry.com'),
        ('highlandsvisionclinic.com', 'info@highlandsvisionclinic.com'),
        ('centralparkvision.com', 'info@centralparkvision.com'),
    ],
    'chiropractic': [
        ('mountainviewchiro.com', 'info@mountainviewchiro.com'),
        ('backtolifechiropractic.com', 'info@backtolifechiropractic.com'),
        ('alignwellchiropractic.com', 'info@alignwellchiropractic.com'),
        ('summitchiropractic.net', 'info@summitchiropractic.net'),
        ('spinehealthclinic.com', 'info@spinehealthclinic.com'),
        ('wellnessfirstchiro.com', 'info@wellnessfirstchiro.com'),
        ('activespinechiro.com', 'info@activespinechiro.com'),
        ('peakperformancechiro.com', 'info@peakperformancechiro.com'),
        ('naturalspinehealth.com', 'info@naturalspinehealth.com'),
        ('prochiropractic.net', 'info@prochiropractic.net'),
        ('familychiropracticcare.com', 'info@familychiropracticcare.com'),
        ('optimumspinecare.com', 'info@optimumspinecare.com'),
        ('totalwellnesschiro.com', 'info@totalwellnesschiro.com'),
        ('birchwoodchiropractic.com', 'info@birchwoodchiropractic.com'),
        ('northsidechiropractic.com', 'info@northsidechiropractic.com'),
        ('greenvalleychiro.com', 'info@greenvalleychiro.com'),
        ('libertychiropractichealth.com', 'info@libertychiropractichealth.com'),
        ('elitespinechiro.com', 'info@elitespinechiro.com'),
        ('horizonchiropracticclinic.com', 'info@horizonchiropracticclinic.com'),
        ('renewchiropracticcare.com', 'info@renewchiropracticcare.com'),
    ],
    'veterinary': [
        ('lakesideanimalclinic.com', 'info@lakesideanimalclinic.com'),
        ('northviewvetclinic.com', 'info@northviewvetclinic.com'),
        ('eastsidevethospital.com', 'info@eastsidevethospital.com'),
        ('villagepetclinic.com', 'info@villagepetclinic.com'),
        ('sunsetanimalcare.com', 'info@sunsetanimalcare.com'),
        ('familypetvet.net', 'info@familypetvet.net'),
        ('valleypetclinic.com', 'info@valleypetclinic.com'),
        ('riverviewvets.com', 'info@riverviewvets.com'),
        ('pinecrestanimalclinic.com', 'info@pinecrestanimalclinic.com'),
        ('mountainviewanimalhospital.com', 'info@mountainviewanimalhospital.com'),
        ('cedaranimalclinic.com', 'info@cedaranimalclinic.com'),
        ('allcareanimalclinic.com', 'info@allcareanimalclinic.com'),
        ('westerntrailsvet.com', 'info@westerntrailsvet.com'),
        ('brightstaranimalhospital.com', 'info@brightstaranimalhospital.com'),
        ('harborviewvet.com', 'info@harborviewvet.com'),
        ('redwoodvetclinic.com', 'info@redwoodvetclinic.com'),
        ('highlandspetcare.com', 'info@highlandspetcare.com'),
        ('sunriseanimalhospital.net', 'info@sunriseanimalhospital.net'),
        ('compasspetvet.com', 'info@compasspetvet.com'),
        ('creeksideanimalclinic.com', 'info@creeksideanimalclinic.com'),
    ],
    'real_estate': [
        ('suncoastrealtors.com', 'info@suncoastrealtors.com'),
        ('keyrealtyllc.com', 'info@keyrealtyllc.com'),
        ('peakrealtysolutions.com', 'info@peakrealtysolutions.com'),
        ('prestonrealtygroup.com', 'info@prestonrealtygroup.com'),
        ('horizonrealtyadvisors.com', 'info@horizonrealtyadvisors.com'),
        ('maplestreetrealty.com', 'info@maplestreetrealty.com'),
        ('lakeviewhomesrealty.com', 'info@lakeviewhomesrealty.com'),
        ('nextdoorrealty.com', 'info@nextdoorrealty.com'),
        ('bridgepointrealty.com', 'info@bridgepointrealty.com'),
        ('sagebrushrealty.com', 'info@sagebrushrealty.com'),
        ('silverspringrealty.com', 'info@silverspringrealty.com'),
        ('cascadehomesrealty.com', 'info@cascadehomesrealty.com'),
        ('pinevalleyrealty.com', 'info@pinevalleyrealty.com'),
        ('claremontpropertygroup.com', 'info@claremontpropertygroup.com'),
        ('highcountryrealestate.net', 'info@highcountryrealestate.net'),
        ('harborlightrealty.com', 'info@harborlightrealty.com'),
        ('goldengaterealtyllc.com', 'info@goldengaterealtyllc.com'),
        ('riversidepremierrealty.com', 'info@riversidepremierrealty.com'),
        ('cornertonerealty.com', 'info@cornertonerealty.com'),
        ('truenorthrealtyadvisors.com', 'info@truenorthrealtyadvisors.com'),
    ],
    'insurance': [
        ('mountainstateinsurance.com', 'info@mountainstateinsurance.com'),
        ('peakprotectioninsurance.com', 'info@peakprotectioninsurance.com'),
        ('keyshieldinsurance.com', 'info@keyshieldinsurance.com'),
        ('harborinsuranceagency.com', 'info@harborinsuranceagency.com'),
        ('brightfutureinsurance.com', 'info@brightfutureinsurance.com'),
        ('fortressinsurancegroup.com', 'info@fortressinsurancegroup.com'),
        ('lakeviewinsuranceservices.com', 'info@lakeviewinsuranceservices.com'),
        ('communityprotectionins.com', 'info@communityprotectionins.com'),
        ('sunriseinsuranceagency.net', 'info@sunriseinsuranceagency.net'),
        ('solidrockinsurance.com', 'info@solidrockinsurance.com'),
        ('northstartinsuranceagency.com', 'info@northstartinsuranceagency.com'),
        ('mainstayinsurance.com', 'info@mainstayinsurance.com'),
        ('clearwaterinsurancesolutions.com', 'info@clearwaterinsurancesolutions.com'),
        ('compassroseinsurance.com', 'info@compassroseinsurance.com'),
        ('rivervalleyinsurance.com', 'info@rivervalleyinsurance.com'),
        ('premierprotectioninsurance.com', 'info@premierprotectioninsurance.com'),
        ('highcountryinsurance.net', 'info@highcountryinsurance.net'),
        ('patriotshieldinsurance.com', 'info@patriotshieldinsurance.com'),
        ('redwoodinsuranceagency.com', 'info@redwoodinsuranceagency.com'),
        ('solidgroundinsurance.com', 'info@solidgroundinsurance.com'),
    ],
    'gym_fitness': [
        ('ironhousefitness.com', 'info@ironhousefitness.com'),
        ('powerupgym.net', 'info@powerupgym.net'),
        ('fortifyfitnessstudio.com', 'info@fortifyfitnessstudio.com'),
        ('elevatefitnesscenter.com', 'info@elevatefitnesscenter.com'),
        ('primeformfitness.com', 'info@primeformfitness.com'),
        ('nextlevelgym.net', 'info@nextlevelgym.net'),
        ('mountainfitnessstudio.com', 'info@mountainfitnessstudio.com'),
        ('ultimatepowerfit.com', 'info@ultimatepowerfit.com'),
        ('steadygainsgym.com', 'info@steadygainsgym.com'),
        ('revvfitnessstudio.com', 'info@revvfitnessstudio.com'),
        ('pinnaclefitnesscenter.net', 'info@pinnaclefitnesscenter.net'),
        ('rivertowngym.com', 'info@rivertowngym.com'),
        ('northsidestrengthclub.com', 'info@northsidestrengthclub.com'),
        ('sunrisefit.com', 'info@sunrisefit.com'),
        ('rebootfitnessstudio.com', 'info@rebootfitnessstudio.com'),
        ('trailblazerfitness.com', 'info@trailblazerfitness.com'),
        ('peakperformancegym.net', 'info@peakperformancegym.net'),
        ('fittrainingsolutions.com', 'info@fittrainingsolutions.com'),
        ('bodyforgefitness.com', 'info@bodyforgefitness.com'),
        ('strengthcirclegym.com', 'info@strengthcirclegym.com'),
    ],
    'tutoring': [
        ('brightmindslearning.com', 'info@brightmindslearning.com'),
        ('achieveacademytutor.com', 'info@achieveacademytutor.com'),
        ('northstartutoring.com', 'info@northstartutoring.com'),
        ('successfulstudentscenter.com', 'info@successfulstudentscenter.com'),
        ('peaklearningcenter.com', 'info@peaklearningcenter.com'),
        ('frontieracademylearning.com', 'info@frontieracademylearning.com'),
        ('schoolboosttutoring.com', 'info@schoolboosttutoring.com'),
        ('mindsparklearningcenter.com', 'info@mindsparklearningcenter.com'),
        ('nextlevelacademics.com', 'info@nextlevelacademics.com'),
        ('classroompluslearning.com', 'info@classroompluslearning.com'),
        ('homeworkhelpexperts.com', 'info@homeworkhelpexperts.com'),
        ('studyprolearningcenter.com', 'info@studyprolearningcenter.com'),
        ('liftofflearninghub.com', 'info@liftofflearninghub.com'),
        ('excellencetutoringservices.com', 'info@excellencetutoringservices.com'),
        ('prismacademytutoring.com', 'info@prismacademytutoring.com'),
        ('risingtidelearners.com', 'info@risingtidelearners.com'),
        ('mathmastersstudio.com', 'info@mathmastersstudio.com'),
        ('cerebralboosttutoring.com', 'info@cerebralboosttutoring.com'),
        ('edgeniuseducation.com', 'info@edgeniuseducation.com'),
        ('topgradelearning.com', 'info@topgradelearning.com'),
    ],
    'photography': [
        ('capturedmomentsstudio.com', 'info@capturedmomentsstudio.com'),
        ('goldenhourimages.com', 'info@goldenhourimages.com'),
        ('blueskyphotographystudio.com', 'info@blueskyphotographystudio.com'),
        ('silverframephotography.com', 'info@silverframephotography.com'),
        ('luminanceportraits.com', 'info@luminanceportraits.com'),
        ('truecolorsphotography.net', 'info@truecolorsphotography.net'),
        ('focuspointphotostudio.com', 'info@focuspointphotostudio.com'),
        ('mountainlightphotography.com', 'info@mountainlightphotography.com'),
        ('oaklandphotographics.com', 'info@oaklandphotographics.com'),
        ('riverviewstudiophotos.com', 'info@riverviewstudiophotos.com'),
        ('serenityshotsphotography.com', 'info@serenityshotsphotography.com'),
        ('northlightphotostudio.com', 'info@northlightphotostudio.com'),
        ('classicframestudio.com', 'info@classicframestudio.com'),
        ('memorylightimaging.com', 'info@memorylightimaging.com'),
        ('vivancephotostudio.com', 'info@vivancephotostudio.com'),
        ('prestonstreetphotos.com', 'info@prestonstreetphotos.com'),
        ('pinnacleimagephotography.com', 'info@pinnacleimagephotography.com'),
        ('prismaticphotographics.net', 'info@prismaticphotographics.net'),
        ('lightandlifephotography.com', 'info@lightandlifephotography.com'),
        ('windmillphotostudio.com', 'info@windmillphotostudio.com'),
    ],
    'florist': [
        ('bloomsbybrianna.com', 'info@bloomsbybrianna.com'),
        ('harvestmoonflowers.com', 'info@harvestmoonflowers.com'),
        ('petalworksflorist.com', 'info@petalworksflorist.com'),
        ('rosegardenfloraldesign.com', 'info@rosegardenfloraldesign.com'),
        ('orchardbloomsflorist.com', 'info@orchardbloomsflorist.com'),
        ('freshcutflowersco.com', 'info@freshcutflowersco.com'),
        ('botanicaflowerart.com', 'info@botanicaflowerart.com'),
        ('willowtreeflorist.net', 'info@willowtreeflorist.net'),
        ('springblossomflowers.com', 'info@springblossomflowers.com'),
        ('fieldstoneflowers.com', 'info@fieldstoneflowers.com'),
        ('lilaclanefloralshop.com', 'info@lilaclanefloralshop.com'),
        ('sunsetsunflowerflorist.com', 'info@sunsetsunflowerflorist.com'),
        ('goldenpetals.net', 'info@goldenpetals.net'),
        ('ivyandbloomfloralstudio.com', 'info@ivyandbloomfloralstudio.com'),
        ('northwoodsflowers.com', 'info@northwoodsflowers.com'),
        ('cedarvalleyflorist.com', 'info@cedarvalleyflorist.com'),
        ('rivercrestfloraldesign.com', 'info@rivercrestfloraldesign.com'),
        ('springviewflorist.com', 'info@springviewflorist.com'),
        ('meadowlarkblooms.com', 'info@meadowlarkblooms.com'),
        ('auroraflowersandevents.com', 'info@auroraflowersandevents.com'),
    ],
    'catering': [
        ('mountainviewcatering.com', 'info@mountainviewcatering.com'),
        ('fivestarbanquets.com', 'info@fivestarbanquets.com'),
        ('goldentablecatering.com', 'info@goldentablecatering.com'),
        ('flavorfulbitescatering.com', 'info@flavorfulbitescatering.com'),
        ('premiumpalatefoods.com', 'info@premiumpalatefoods.com'),
        ('rivertowncatering.net', 'info@rivertowncatering.net'),
        ('silverplatterevents.com', 'info@silverplatterevents.com'),
        ('seasonedaffairscatering.com', 'info@seasonedaffairscatering.com'),
        ('culinaryartisanscatering.com', 'info@culinaryartisanscatering.com'),
        ('sunrisebreakfastcatering.com', 'info@sunrisebreakfastcatering.com'),
        ('harvesttimecatering.com', 'info@harvesttimecatering.com'),
        ('tablescapecatering.com', 'info@tablescapecatering.com'),
        ('brimfulflavorcatering.com', 'info@brimfulflavorcatering.com'),
        ('valleycraftcatering.com', 'info@valleycraftcatering.com'),
        ('thefeastmastercatering.com', 'info@thefeastmastercatering.com'),
        ('redwoodridgecatering.com', 'info@redwoodridgecatering.com'),
        ('northshorebanquetservice.com', 'info@northshorebanquetservice.com'),
        ('grandillusioncatering.com', 'info@grandillusioncatering.com'),
        ('peakexperiencecatering.com', 'info@peakexperiencecatering.com'),
        ('harborgatecatering.com', 'info@harborgatecatering.com'),
    ],
}

FAIL_HOOKS = {
    'viewport': ('site not configured as mobile-friendly', "your site isn't configured as mobile-friendly — Google now ranks mobile experience first, so this directly tanks your position."),
    'meta_desc': ('your meta description is blank', 'your meta description is missing — the snippet Google shows under your site name in search results is blank, so people skip past you.'),
    'h1': ('your main heading is missing', "your main heading (H1) is missing — that's one of the first things Google reads to understand what your page is about."),
    'og': ('blank social preview when shared', 'when someone shares your site on Facebook or iMessage, it shows up blank — no image, no title, just a raw link.'),
    'share': ('blank preview when shared on social', 'when someone shares your site on social media or iMessage, it shows up blank with no preview image or description.'),
    'speed': ('slow load speed hurting rankings', 'your site loads slowly — Google uses page speed as a ranking signal, and slow sites lose to faster competitors.'),
    'img_alt': ('images missing alt text', "your images are missing alt text — that's a basic accessibility and SEO signal Google uses to understand your content."),
    'broken': ('broken links on your site', 'you have broken links on your site — Google sees those and it signals a neglected, low-quality site.'),
}

VERTICAL_DEFAULT_FAIL = {
    'optometry': 'meta_desc',
    'chiropractic': 'og',
    'veterinary': 'viewport',
    'real_estate': 'og',
    'insurance': 'meta_desc',
    'gym_fitness': 'viewport',
    'tutoring': 'h1',
    'photography': 'og',
    'florist': 'viewport',
    'catering': 'meta_desc',
}

def get_audit_fail(domain):
    try:
        r = requests.get(f"https://sitelume.app/api/audit?url={domain}", timeout=10, headers=HEADERS)
        if r.status_code == 200:
            checks = r.json().get("checks", {})
            for key in ["viewport","meta_desc","h1","og","share","speed","img_alt","broken"]:
                if key in checks and not checks[key].get("passed", True):
                    return key
    except Exception:
        pass
    return None


def build_email(domain, fail_key):
    short, long_desc = FAIL_HOOKS.get(fail_key, FAIL_HOOKS["meta_desc"])
    subject = f"{domain} — quick fix for {short}"
    body = (
        f"Hi — I ran a free audit on {domain} and the main thing that stood out: {long_desc} "
        f"This is likely costing you rankings and new customers finding you online. "
        f"Full report (no signup needed): {SITELENS_AUDIT_URL}{domain}\n\n— Cyrus"
    )
    return subject, body


def send_email(to_addr, subject, body):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = GMAIL
    msg["To"] = to_addr
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.login(GMAIL, APP_PASS)
        s.sendmail(GMAIL, [to_addr], msg.as_string())


def load_results():
    p = Path(RESULTS_FILE)
    return json.loads(p.read_text()) if p.exists() else []


def save_results(data):
    Path(RESULTS_FILE).write_text(json.dumps(data, indent=2))


def main():
    results = load_results()
    already_sent = {r["domain"] for r in results if r.get("status") == "sent"} | SKIP_DOMAINS
    sent_count = errors = skipped = 0

    for vertical, tgts in TARGETS_BY_VERTICAL.items():
        print(f"\n=== {vertical.upper()} ({len(tgts)} targets) ===", flush=True)
        default_fail = VERTICAL_DEFAULT_FAIL.get(vertical, "meta_desc")

        for domain, email_addr in tgts:
            if domain in already_sent:
                skipped += 1
                print(f"  SKIP: {domain}", flush=True)
                continue

            fail_key = get_audit_fail(domain) or default_fail
            subject, body = build_email(domain, fail_key)

            try:
                send_email(email_addr, subject, body)
                print(f"  SENT: {domain} -> {email_addr} [{fail_key}]", flush=True)
                results.append({
                    "domain": domain, "email": email_addr, "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "top_fail": fail_key, "phase": "batch3", "vertical": vertical,
                })
                already_sent.add(domain)
                sent_count += 1
                save_results(results)
                time.sleep(7)
            except Exception as e:
                print(f"  ERROR: {domain} -> {e}", flush=True)
                results.append({
                    "domain": domain, "email": email_addr, "status": "error",
                    "error": str(e), "phase": "batch3", "vertical": vertical,
                })
                errors += 1
                save_results(results)
                time.sleep(3)

    total_sent = len([r for r in results if r.get("status") == "sent"])
    sep = "=" * 50
    print(f"\n{sep}", flush=True)
    print(f"BATCH3 DONE: sent={sent_count}, errors={errors}, skipped={skipped}", flush=True)
    print(f"TOTAL ALL-TIME SENT: {total_sent}", flush=True)
    return sent_count, errors


if __name__ == "__main__":
    main()