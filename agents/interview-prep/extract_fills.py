"""
Extract Q2 and Q3 filled content from existing per-company guides.
Prints the runs/text for those paragraphs.
"""
from docx import Document

guides = [
    ("Lance PM", "guides/lance-pm/Lance_PM_Interview_Prep_Guide.docx"),
    ("MediaAlpha TPM", "guides/mediaalpha-tpm/MediaAlpha_TPM_Interview_Prep_Guide.docx"),
    ("New Relic PM", "guides/new-relic-product-manager-log-management/New_Relic_PM_Interview_Prep_Guide.docx"),
    ("Scale AI PM-TE", "guides/scale-ai-pm-te/ScaleAI_Interview_Prep_Guide.docx"),
    ("Scale AI TPM-CV", "guides/scale-ai-tpm-cv/Scale_AI_Interview_Prep_Guide.docx"),
    ("Podium PM", "guides/podium-pm/Podium_Interview_Prep_Guide.docx"),
    ("Mintlify SE", "guides/mintlify-solutions-engineer-post-sales/Mintlify_SE_PostSales_Interview_Prep_Guide.docx"),
    ("Datadog PTSE", "guides/datadog-partner-technology-solutions-engineer/Datadog_PTSE_Interview_Prep_Guide.docx"),
]

def extract_q_fills(path):
    doc = Document(path)
    paras = doc.paragraphs
    # Find Q2 and Q3 heading indices
    q2_idx = None
    q3_idx = None
    for i, p in enumerate(paras):
        if 'Q2:' in p.text and 'Why do you want' in p.text:
            q2_idx = i
        if 'Q3:' in p.text and ('Do you know' in p.text or 'what this role' in p.text.lower()):
            q3_idx = i

    result = {}

    def collect_fill(start_idx):
        """Collect paragraphs after 'Script:' line until next heading."""
        fills = []
        in_script = False
        for p in paras[start_idx+1:]:
            if p.style.name.startswith('Heading'):
                break
            if p.text.strip() == 'Script:':
                in_script = True
                continue
            if in_script and p.text.strip():
                # Collect runs with bold info
                run_info = [(r.bold, r.text) for r in p.runs]
                fills.append(run_info)
        return fills

    if q2_idx is not None:
        result['q2'] = collect_fill(q2_idx)
    if q3_idx is not None:
        result['q3'] = collect_fill(q3_idx)
    return result

for name, path in guides:
    try:
        fills = extract_q_fills(path)
        print(f"\n=== {name} ===")
        for q, bullets in fills.items():
            print(f"  {q.upper()}:")
            for runs in bullets:
                text = ''.join(t for _, t in runs)
                bold_parts = [t for b, t in runs if b]
                print(f"    bullet: {text[:120]}")
                if bold_parts:
                    print(f"    bold: {bold_parts}")
    except Exception as err:
        print(f"\n=== {name} ERROR: {err}")
