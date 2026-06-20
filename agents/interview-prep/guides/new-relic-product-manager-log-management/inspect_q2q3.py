from docx import Document

doc = Document("New_Relic_PM_Interview_Prep_Guide.docx")
in_q2q3 = False
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if "Q2" in t or "Q3" in t:\n        in_q2q3 = True\n    if in_q2q3:
        print(f"[{i}] {repr(t)}")
        for j, r in enumerate(p.runs):
            print(f"    run[{j}] bold={r.bold} | {repr(r.text)}")
    if in_q2q3 and "Q4" in t and "Q2" not in t and "Q3" not in t:\n        break\nPYEOF\ncd /home/azureuser/.openclaw/agents/interview-prep/workspace/guides/new-relic-product-manager-log-management/\npython3 inspect_q2q3.py
