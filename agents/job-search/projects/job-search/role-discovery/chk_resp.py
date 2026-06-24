import json
try:
    d = json.load(open("/tmp/submit_resp_2.json"))
    afr = d.get("data",{}).get("submitMultipleFormsAction",{}).get("applicationFormResult",{})
    ok = afr.get("ok", False)
    errs = afr.get("errorMessages",[])
    print(f"ok={ok}, errors={errs}")
    for sec in (afr.get("sections") or []):
        for fe in (sec.get("fieldEntries") or []):
            ft = fe.get("field",{}).get("__autoSerializationID","")
            if ft == "BooleanField":
                val = fe.get("fieldValue")
                title = fe.get("field",{}).get("title","")[:40]
                print(f"  {title}: {val}")
except Exception as e:
    print(f"No resp: {e}")
