#!/usr/bin/env python3
"""Build the PointOne Forward Deployed Engineer prep bundle."""
import importlib.util, os

WS = "/home/azureuser/.openclaw/agents/interview-prep/workspace"
spec = importlib.util.spec_from_file_location("_builder", os.path.join(WS, "_builder.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

PROOF = "/home/azureuser/.openclaw/agents/job-search/workspace/outputs/proof/2026-06-21-pointone-2576"
JD = os.path.join(PROOF, "JD.md")
RESUME = os.path.join(PROOF, "Cyrus_Shekari_Resume_ashby-pointone_834a8648_v2.pdf")

q2 = [
    ("Why do I want to work at PointOne:",
     "PointOne is a Y Combinator / Bessemer / 8VC / General Catalyst-backed startup building an AI timekeeper that automatically captures billable time for law firms. It's one of the rare AI products with hard, measurable ROI, which is why it's so sticky inside a firm. I want to be an early member of the team, shaping the core infrastructure behind the product alongside a crew out of Jane Street, Google, and law."),
    ("Why do I want this role:",
     "A Forward Deployed Engineer sits right at the intersection of my strengths: building real AI workflows (I built a Copilot drill-planning agent and did RAG-style retrieval work at Microsoft) and staying close to the customer. I want to partner directly with firms, translate their needs into technical solutions, and own outcomes end to end."),
]

q3 = [
    ("What does PointOne do:",
     "AI-powered legal timekeeping: their product automatically captures attorneys' billable time and turns it into insights, delivering real cost savings that make it one of the stickiest tools in a law firm. Venture-backed (YC, Bessemer, 8VC, General Catalyst) and scaling the engineering team ahead of a Series A."),
    ("What is this role:",
     "A Forward Deployed Engineer drives strategic customer accounts, builds novel AI products (including RAG pipelines) to prove out new workflows, and regularly visits customers to translate their needs into solutions — on a serverless Go/AWS backend with React/TypeScript clients. High ownership, autonomous, in-person in NYC."),
]

guide_path, zip_path = b.build(
    company_key="pointone-fde",
    q2_bullets=q2,
    q3_bullets=q3,
    jd_src=JD,
    resume_src=RESUME,
    out_zip_name="PointOne_FDE_PrepBundle.zip",
    guide_name="PointOne_FDE_Interview_Prep_Guide.docx",
)
print("GUIDE", guide_path)
print("ZIP", zip_path)
