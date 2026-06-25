#!/usr/bin/env python3
"""Build interview-prep bundles (lean scope): copy master guide, fill Q2/Q3 with
two bold-labeled bullets each, zip with JD.md + resume PDF. In-place XML patch."""
import zipfile, re, os, shutil, html

WS = "/home/azureuser/.openclaw/agents/interview-prep/workspace"
MASTER = os.path.join(WS, "templates", "Master_Interview_Prep_Guide.docx")
SUB = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted"

# The two placeholder paragraphs (exact strings from the master document.xml).
PH_Q3 = '[Fill in here]'
PH_Q2 = '[Fill in here. Job description usually explains both of these]'


def make_bullet(num_id, label, body):
    """One numbered-list <w:p> with a BOLD label run (ends in colon) + plain body run."""
    label_esc = html.escape(label, quote=False)
    body_esc = html.escape(body, quote=False)
    return (
        '<w:p w:rsidR="00000000" w:rsidDel="00000000" w:rsidP="00000000" '
        'w:rsidRDefault="00000000" w:rsidRPr="00000000">'
        '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="%s"/></w:numPr>'
        '<w:ind w:left="720" w:hanging="360"/><w:rPr><w:u w:val="none"/></w:rPr></w:pPr>'
        '<w:r w:rsidDel="00000000" w:rsidR="00000000" w:rsidRPr="00000000">'
        '<w:rPr><w:b w:val="1"/><w:rtl w:val="0"/></w:rPr>'
        '<w:t xml:space="preserve">%s </w:t></w:r>'
        '<w:r w:rsidDel="00000000" w:rsidR="00000000" w:rsidRPr="00000000">'
        '<w:rPr><w:rtl w:val="0"/></w:rPr>'
        '<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
        % (num_id, label_esc, body_esc)
    )


def replace_placeholder_paragraph(xml, placeholder_text, bullets_xml):
    """Find the <w:p>...placeholder...</w:p> and replace the WHOLE paragraph with bullets."""
    # locate the paragraph block containing the placeholder
    for m in re.finditer(r'<w:p\b[^>]*>.*?</w:p>', xml, re.S):
        if placeholder_text in m.group(0):
            return xml[:m.start()] + bullets_xml + xml[m.end():]
    raise SystemExit('placeholder not found: ' + placeholder_text[:30])


def build(company_key, q2_bullets, q3_bullets, jd_src, resume_src, out_zip_name, guide_name):
    raw = zipfile.ZipFile(MASTER).read('word/document.xml').decode('utf-8')
    xml = raw
    # Q2 uses numId 1, Q3 uses numId 10 (from the master scaffolding).
    q2_xml = ''.join(make_bullet('1', lbl, body) for lbl, body in q2_bullets)
    q3_xml = ''.join(make_bullet('10', lbl, body) for lbl, body in q3_bullets)
    xml = replace_placeholder_paragraph(xml, PH_Q2, q2_xml)
    xml = replace_placeholder_paragraph(xml, PH_Q3, q3_xml)

    # write the patched guide docx
    work_dir = os.path.join(WS, "bundles", company_key)
    os.makedirs(work_dir, exist_ok=True)
    guide_path = os.path.join(work_dir, guide_name)
    zin = zipfile.ZipFile(MASTER, 'r')
    zout = zipfile.ZipFile(guide_path, 'w', zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'word/document.xml':
            data = xml.encode('utf-8')
        zout.writestr(item, data)
    zin.close()
    zout.close()

    # copy JD + resume into the bundle dir
    jd_dst = os.path.join(work_dir, os.path.basename(jd_src))
    resume_dst = os.path.join(work_dir, os.path.basename(resume_src))
    shutil.copy2(jd_src, jd_dst)
    shutil.copy2(resume_src, resume_dst)

    # zip the 3 files
    zip_path = os.path.join(WS, "bundles", out_zip_name)
    z = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
    for f in (guide_path, jd_dst, resume_dst):
        z.write(f, os.path.basename(f))
    z.close()
    print('BUILT', zip_path)
    return guide_path, zip_path
