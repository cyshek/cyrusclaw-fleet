#!/usr/bin/env python3
"""Quick plan generator from existing dryrun specs - bypasses LLM cover gen."""
import sys, json, shutil
from pathlib import Path

HERE = Path(__file__).parent
DRYRUN_DIR = HERE.parent / "applications" / "dryrun"
OUTPUT_DIR = HERE / "output"
UPLOADS_DIR = Path("/tmp/openclaw/uploads")

sys.path.insert(0, str(HERE))
import importlib

def gen_plan(role_id, dryrun_spec_name, company, role_title):
    spec_path = DRYRUN_DIR / dryrun_spec_name
    if not spec_path.exists():
        return "SKIP: spec not found: " + str(spec_path)

    spec = json.loads(spec_path.read_text())
    slug_base = spec.get("org", company.lower().replace(" ", "-"))
    job_id = spec.get("job_id", "")
    slug = slug_base + "-" + job_id

    plan_path = OUTPUT_DIR / ("inline-plan-" + slug + ".json")
    if plan_path.exists():
        return "SKIP: plan exists: " + plan_path.name

    resume_candidates = [
        Path("/home/azureuser/.openclaw/agents/job-search/workspace/resume/Cyrus_Shekari_Resume.pdf"),
        HERE.parent / "resume" / "Cyrus_Shekari_Resume.pdf",
    ]
    pdf_path = next((c for c in resume_candidates if c.exists()), None)
    if pdf_path is None:
        return "ERROR: resume PDF not found"

    af = importlib.import_module("ashby_filler")
    plan = af.build_plan(spec)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    staged_pdf = UPLOADS_DIR / pdf_path.name
    shutil.copy2(pdf_path, staged_pdf)
    plan["resume_path"] = str(staged_pdf)

    steps = af.emit_steps(plan, label=slug)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_data = {
        "slug": slug,
        "ats": "ashby",
        "spec_path": str(spec_path),
        "pdf_path_local": str(pdf_path),
        "pdf_path_staged": str(staged_pdf),
        "url": plan["url"],
        "tenant_embed": None,
        "text_fields": plan["text_fields"],
        "radios": plan["radios"],
        "checkboxes": plan.get("checkboxes", []),
        "resume_path": plan["resume_path"],
        "skipped": plan.get("skipped", []),
        "needs_review": plan.get("needs_review", []),
        "dropdowns": plan.get("dropdowns", []),
        "steps": steps,
        "cover_overrides": plan.get("cover_overrides", []),
    }
    plan_path.write_text(json.dumps(out_data, indent=2))
    return "OK: " + plan_path.name


if __name__ == "__main__":
    roles = [
        (919,  "cohere-b0bcef37-1d20-414f-aade-c54942d63df9.json",        "Cohere",     "Forward Deployed Engineer, Agentic Platform"),
        (1112, "higharc-6e1c2e07-b812-4e3e-ae44-9a55ed2c7f3f.json",       "Higharc",    "Solutions Engineer"),
        (1206, "coframe-8e95cc54-b642-4ffe-b4d5-3fffb4f51363.json",       "Coframe",    "Forward Deployed Engineer"),
        (1209, "happyrobot.ai-ca2ec773-fa00-4b9e-a439-200599e4f0cf.json", "HappyRobot", "Forward Deployed Engineer"),
        (1235, "liquid-ai-59fd7c6b-bc62-4855-bbd5-dd0233e6c672.json",     "Liquid AI",  "Solutions Architect"),
        (1326, "brettonai-b21f7919-92f0-4de8-bd76-daeb16341a31.json",     "Bretton AI", "Forward Deployed Engineer"),
        (1380, "artisan-558908d9-bbbb-4d98-9e8c-a03cc647fcba.json",       "Artisan",    "Forward Deployed Engineer"),
        (1552, "console-395c3f5b-759f-4bf1-b6ed-38db7f0c76ee.json",       "Console",    "Forward Deployed Engineer"),
        (2563, "ambient.ai-eb953820-7748-4620-98a0-b97bcdc40001.json",    "Ambient.ai", "Enterprise Sales Engineer"),
        (2605, "ready-586fd053-b5b9-463f-a9dd-2df68856adb0.json",         "Ready",      "Product Solutions Engineer"),
        (2606, "anara-f69dcabe-1f30-46ce-8407-ba03f55f2ced.json",         "Anara",      "Technical Product Manager"),
        (2781, "antithesis-9e409d07-0c85-43f3-bd55-fa1120eb8082.json",    "Antithesis", "Solutions Engineer"),
    ]

    for role_id, spec_name, company, role in roles:
        print("[%d] %s -- %s" % (role_id, company, role))
        result = gen_plan(role_id, spec_name, company, role)
        print("  => " + result)
