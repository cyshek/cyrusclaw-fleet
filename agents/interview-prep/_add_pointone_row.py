#!/usr/bin/env python3
"""In-place add PointOne FDE to the Interviews sheet (sheet4.xml) row 18.
Cyrus-directed manual edit. No re-render, no other sheet touched, backup already made."""
import sys, zipfile, re, shutil, os, html

F = "/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/Cyrus_Job_Tracker.xlsx"

# Values for the new row (col -> text). Truthful: submitted 6/24, no screen yet.
VALS = {
    "A": "PointOne",
    "B": "Forward Deployed Engineer",
    "C": "Yes",
    "D": "Applied",
    "E": "Submitted 6/24. YC/Bessemer/8VC-backed legal AI timekeeper (NYC, in-person). Awaiting recruiter response.",
}
ROW = 18
STYLE = "7"

def cell_xml(col):
    ref = f"{col}{ROW}"
    txt = html.escape(VALS[col], quote=False)
    return (f'<c r="{ref}" s="{STYLE}" t="inlineStr">'
            f'<is><t xml:space="preserve">{txt}</t></is></c>')

xml = zipfile.ZipFile(F).read('xl/worksheets/sheet4.xml').decode('utf-8')

# Find the existing row 18 block and rebuild it with our 5 inlineStr cells.
m = re.search(r'(<row\b[^>]*\br="%d"[^>]*>)(.*?)(</row>)' % ROW, xml, re.S)
if not m:
    sys.exit("row %d not found" % ROW)
open_tag, _old_inner, close_tag = m.group(1), m.group(2), m.group(3)
new_inner = "".join(cell_xml(c) for c in ("A","B","C","D","E"))
new_row = open_tag + new_inner + close_tag
new_xml = xml[:m.start()] + new_row + xml[m.end():]

if new_xml == xml:
    sys.exit("no change made")

# Repackage: rewrite ONLY sheet4.xml, leave everything else byte-identical.
tmp = F + ".tmp"
zin = zipfile.ZipFile(F, 'r')
zout = zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename == 'xl/worksheets/sheet4.xml':
        data = new_xml.encode('utf-8')
    zout.writestr(item, data)
zin.close(); zout.close()
os.replace(tmp, F)
print("PATCHED row %d:" % ROW, VALS)
