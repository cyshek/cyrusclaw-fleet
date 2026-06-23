from docx import Document

d = Document('templates/Master_Interview_Prep_Guide.docx')
keys = ['Fill in', 'Q2', 'Q3', 'why', 'Why', 'know', 'Know', 'company', 'role', 'What', 'Section', 'understand', 'this']
for i, p in enumerate(d.paragraphs):
    t = p.text.strip()
    if not t:\n        continue\n    hit = any(k in t for k in keys) or '[' in t\n    if hit:
        print(i, '|', p.style.name, '|', t[:120])
