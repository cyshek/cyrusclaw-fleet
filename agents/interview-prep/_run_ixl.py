#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/interview-prep/workspace")
from _builder import build

SUB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"
IXL = f"{SUB}/ixl-learning-8447267002"

ixl_q2 = [
    ("Why do I want to work at IXL:",
     "IXL is the country's largest EdTech company — 1 in 4 U.S. students uses IXL.com, and the family "
     "includes Rosetta Stone, Wyzant, and Teachers Pay Teachers. I'm drawn to building products that "
     "make a real, measurable difference for millions of learners and teachers, and to IXL's "
     "collaborative, mission-driven culture with strong mentorship and executive visibility for someone "
     "growing in product."),
    ("Why do I want this role:",
     "The Associate Product Manager role takes products from initial brainstorm through launch and beyond, "
     "working across Engineering, Design, and Marketing while keeping the user first. That mix of "
     "analytical problem-solving, writing crisp requirements, and coordinating cross-functional teams to "
     "ship is exactly the work I've been doing at Microsoft — and a chance to apply it to a product "
     "teachers and students genuinely love."),
]
ixl_q3 = [
    ("What does IXL do:",
     "IXL Learning is the largest EdTech company in the U.S. — it builds personalized learning products "
     "used by millions globally, anchored by IXL.com (used by 1 in 4 American students) plus Rosetta Stone "
     "(language), Wyzant (tutoring), and Teachers Pay Teachers, all aimed at solving hard problems in "
     "K-12 and broader education."),
    ("What is this role:",
     "An Associate Product Manager on IXL's product team (in San Mateo HQ): deeply understanding student, "
     "teacher, and parent needs, writing and communicating product requirements, partnering with designers "
     "and engineers to ship features, and coordinating launches with marketing. They want 1–3 years of PM "
     "or adjacent experience, strong analytical reasoning, some technical/CS background, and an interest in "
     "education and UI/UX. (Note: this is the general APM role, separate from their New-Grad APM program.)"),
]

build(
    "ixl-apm",
    ixl_q2,
    ixl_q3,
    f"{IXL}/JD.md",
    f"{IXL}/Cyrus_Shekari_Resume_ixllearning_8447267002_v2.pdf",
    "ixl-associate-product-manager.zip",
    "Master_Interview_Prep_Guide.docx",
)
print("DONE")
