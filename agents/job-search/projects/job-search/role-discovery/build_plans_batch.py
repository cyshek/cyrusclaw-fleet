#!/usr/bin/env python3
"""Build plan JSONs for PREP-READY roles that are missing plan files."""
import json, sys, shutil
from pathlib import Path
HERE = Path(__file__).parent
APPS_DIR = HERE.parent / "applications"
SUBMITTED_DIR = APPS_DIR / "submitted"
DRYRUN_DIR = APPS_DIR / "dryrun"
OUTPUT_DIR = HERE / "output"
UPLOADS_DIR = Path("/tmp/openclaw/uploads")

sys.path.insert(0, str(HERE))
import importlib
gf = importlib.import_module("greenhouse_filler")

# Map: (slug, dryrun_org_jid, role_id)
TARGETS = [
    ("oasis-security-5236510008", "oasissecurity-5236510008", 2737),
    ("beyondtrust-7899566", "beyondtrust-7899566", 2738),
    ("avepoint-7673317", "avepoint-7673317", 2741),
    ("avepoint-6760659", "avepoint-6760659", 2742),
    ("avepoint-7588856", "avepoint-7588856", 2743),
    ("divergent-4836116008", "divergent-4836116008", 2751),
    ("glossgenius-7741560003", "glossgenius-7741560003", 2765),
    ("dorsia-5003379007", "dorsia-5003379007", 2807),
    ("blend-5738714004", "blend-5738714004", 2819),
    ("anduril-5153820007", "andurilindustries-5153820007", 2841),
    ("anduril-5125591007", "andurilindustries-5125591007", 2842),
    ("aclu-8574963002", "aclu-8574963002", 2846),
    ("avepoint-6760657", "avepoint-6760657", 2847),
    ("verkada-4086501007", "verkada-4086501007", 2848),
    ("sigma-computing-7767591003", "sigmacomputing-7767591003", 2949),
    ("pure-storage-7983980", "purestorage-7983980", 2965),
]

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

results = []
for slug, dryrun_key, role_id in TARGETS:
    try:
        # Find dryrun spec
        spec_path = DRYRUN_DIR / f"{dryrun_key}.json"
        if not spec_path.exists():
            print(f"MISSING dryrun: {spec_path}", file=sys.stderr)
            results.append((slug, role_id, "MISSING_DRYRUN", None))
            continue
        
        # Find PDF
        workdir = SUBMITTED_DIR / slug
        pdf_files = list(workdir.glob("*.pdf"))
        if not pdf_files:
            print(f"MISSING PDF in {workdir}", file=sys.stderr)
            results.append((slug, role_id, "MISSING_PDF", None))
            continue
        pdf_path = pdf_files[0]
        
        # Stage PDF
        staged_pdf = UPLOADS_DIR / pdf_path.name
        shutil.copy2(pdf_path, staged_pdf)
        
        # Load spec and build plan
        spec = json.loads(spec_path.read_text())
        plan = gf.build_plan(spec)
        plan["resume_path"] = str(staged_pdf)
        
        # Merge cover answers if present
        cover_path = workdir / "cover_answers.md"
        if cover_path.exists():
            from inline_submit import merge_cover_answers_into_plan
            plan = merge_cover_answers_into_plan(plan, spec, cover_path)
        else:
            plan["cover_overrides"] = []
        
        # Build steps
        steps = gf.emit_steps(plan, label=slug)
        
        # Write plan
        out_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
        out_path.write_text(json.dumps({
            "slug": slug,
            "ats": "greenhouse",
            "wrapper_url": None,
            "spec_path": str(spec_path),
            "pdf_path_local": str(pdf_path),
            "pdf_path_staged": str(staged_pdf),
            "url": plan["url"],
            "text_fields": plan["text_fields"],
            "dropdowns": plan["dropdowns"],
            "country_dropdowns": plan.get("country_dropdowns", []),
            "phone_iti": plan.get("phone_iti", []),
            "needs_review_dropdowns": plan.get("needs_review_dropdowns", []),
            "_education": plan.get("_education", {}),
            "skipped": plan.get("skipped", []),
            "unknown": plan.get("unknown", []),
            "cover_overrides": plan.get("cover_overrides", []),
            "steps": steps,
            "role_id": role_id,
        }, indent=2, default=str) + "\n")
        print(f"OK: {slug} -> {out_path}")
        results.append((slug, role_id, "OK", str(out_path)))
    except Exception as e:
        print(f"ERROR {slug}: {e}", file=sys.stderr)
        results.append((slug, role_id, f"ERROR: {e}", None))

print(f"\nDone: {sum(1 for _,_,s,_ in results if s=='OK')}/{len(TARGETS)} plans built")
