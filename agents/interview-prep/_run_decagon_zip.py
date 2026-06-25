#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/interview-prep/workspace")
from _builder import build

SUB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"

# ---------------- DECAGON: Customer Engineer, Agent Builder ----------------
decagon_q2 = [
    ("Why do I want to work at Decagon:",
     "Decagon is the leading conversational-AI platform helping enterprises like Cash App, Chime, and "
     "Oura deploy AI agents across voice, chat, email, and SMS. I'm drawn to a company that's redefining "
     "customer experience with agents that actually resolve problems instead of deflecting them, and the "
     "in-office, high-velocity culture (\"Just Get It Done,\" Winner's Mindset) matches how I like to work."),
    ("Why do I want this role:",
     "The Customer Engineer, Agent Builder role is hands-on, technical, and customer-facing all at once — "
     "owning agent builds end to end, configuring behavior and guardrails, validating integrations, and "
     "feeding real customer needs back into the platform. That blend of deep execution and translating "
     "senior stakeholder requirements into working systems is exactly the work I've done building "
     "automated resilience tooling at Microsoft."),
]
decagon_q3 = [
    ("What does Decagon do:",
     "Decagon builds enterprise-grade AI customer-service agents — a conversational-AI platform that lets "
     "brands deploy agents across every channel (voice, chat, email, SMS) to deliver fast, personalized "
     "resolutions at scale, backed by a16z, Accel, and Bain."),
    ("What is this role:",
     "A highly technical delivery role on the new Agent Builder Org: I'd own end-to-end execution of AI "
     "agent builds for strategic customers — scoping with senior technical stakeholders, writing/configuring "
     "agent artifacts and guardrails, setting up and validating integrations like ticketing systems, and "
     "running tight feedback loops with Engineering and APMs. Needs a strong technical foundation (code, "
     "APIs, integrations) and comfort in fast-moving, ambiguous environments."),
]

# ---------------- ZIP: Enterprise Solution Engineer (Pre-Sales) ----------------
zip_q2 = [
    ("Why do I want to work at Zip:",
     "Zip is the AI platform for enterprise procurement, trusted by T-Mobile, OpenAI, AMD, and Mars to "
     "orchestrate spend across teams, tools, and suppliers — they've processed over $500B in spend and "
     "raised $371M at a $2.2B valuation. I want to be at a company moving this fast on a real enterprise "
     "problem, with a product team out of Apple, Airbnb, and Meta and an underdog, ownership-driven culture."),
    ("Why do I want this role:",
     "The Enterprise Solution Engineer (Pre-Sales) role is the technical champion in the sales motion — "
     "running discovery, building custom demos, handling objections, scoping POCs, and funneling customer "
     "feedback back into product. I like being the trusted technical advisor who helps a prospect see how "
     "the solution fits their landscape, and my background translating complex technical systems for "
     "stakeholders maps directly onto that."),
]
zip_q3 = [
    ("What does Zip do:",
     "Zip is an AI-powered enterprise procurement platform — it orchestrates the buying process across "
     "teams, tools, and suppliers (with AI agents) so companies can get the resources they need faster, "
     "covering procurement and billing/AP workflows for the world's largest enterprises."),
    ("What is this role:",
     "The primary pre-sales technical point of contact for the Zip solution suite: partnering with account "
     "executives to drive deals, leading discovery and demos, responding to RFx and IT-security "
     "questionnaires, building custom demos, and scoping POCs with Post-Sales. Needs solution-selling "
     "experience, F500 / C-level exposure, familiarity with the procurement/AP space, and a solid grasp of "
     "software integrations and APIs."),
]

build(
    "decagon-customer-engineer",
    decagon_q2,
    decagon_q3,
    f"{SUB}/decagon-8c40fb7a-5f25-4112-a1df-f1c22b81042c/JD.md",
    f"{SUB}/decagon-8c40fb7a-5f25-4112-a1df-f1c22b81042c/Cyrus_Shekari_Resume_ashby-decagon_8c40fb7a_v2.pdf",
    "decagon-customer-engineer.zip",
    "Master_Interview_Prep_Guide.docx",
)
build(
    "zip-solution-engineer",
    zip_q2,
    zip_q3,
    f"{SUB}/zip-d28dc61e-b4fa-4517-b61e-a31bccefddba/JD.md",
    f"{SUB}/zip-d28dc61e-b4fa-4517-b61e-a31bccefddba/Cyrus_Shekari_Resume_ashby-zip_d28dc61e_v2.pdf",
    "zip-solution-engineer.zip",
    "Master_Interview_Prep_Guide.docx",
)
print("DONE")
