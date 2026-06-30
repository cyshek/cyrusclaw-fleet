#!/usr/bin/env python3
"""
STEP 3: give the Section-2 card FACT lines real bullet glyphs.
Cyrus's doc has no List Bullet style, so apply direct numbering/bullet formatting
via a minimal numbering definition. Phase labels (Situation:, etc.) and Maps to:
and the intro italic line stay un-bulleted.
"""
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

WS = Path("/home/azureuser/.openclaw/agents/interview-prep/workspace")
OUT = WS / "templates/Master_Interview_Prep_Guide.docx"
doc = Document(str(OUT))

# --- ensure a bullet numbering definition exists in numbering.xml ---
from docx.parts.numbering import NumberingPart
try:
    numbering = doc.part.numbering_part.numbering_definitions._numbering
    has_numbering = True
except Exception:
    has_numbering = False

def ensure_bullet_num():
    """Create (or reuse) an abstractNum + num for a simple bullet; return numId."""
    part = doc.part.numbering_part
    numbering = part.numbering_definitions._numbering
    # Reuse if we already made one tagged with our marker.
    for an in numbering.findall(qn('w:abstractNum')):
        if an.get(qn('w:abstractNumId')) == '90':
            break
    else:
        an = OxmlElement('w:abstractNum')
        an.set(qn('w:abstractNumId'), '90')
        lvl = OxmlElement('w:lvl'); lvl.set(qn('w:ilvl'), '0')
        numFmt = OxmlElement('w:numFmt'); numFmt.set(qn('w:val'), 'bullet'); lvl.append(numFmt)
        lvlText = OxmlElement('w:lvlText'); lvlText.set(qn('w:val'), '\u2022'); lvl.append(lvlText)
        # indentation
        pPr = OxmlElement('w:pPr')
        ind = OxmlElement('w:ind'); ind.set(qn('w:left'), '720'); ind.set(qn('w:hanging'), '360')
        pPr.append(ind); lvl.append(pPr)
        rPr = OxmlElement('w:rPr')
        rFonts = OxmlElement('w:rFonts'); rFonts.set(qn('w:ascii'), 'Symbol'); rFonts.set(qn('w:hAnsi'), 'Symbol'); rPr.append(rFonts)
        lvl.append(rPr)
        an.append(lvl)
        numbering.insert(0, an)
    # num element pointing at abstractNum 90
    for nm in numbering.findall(qn('w:num')):
        if nm.get(qn('w:numId')) == '90':
            return 90
    nm = OxmlElement('w:num'); nm.set(qn('w:numId'), '90')
    ai = OxmlElement('w:abstractNumId'); ai.set(qn('w:val'), '90'); nm.append(ai)
    numbering.append(nm)
    return 90

# If the doc has no numbering part, python-docx creates one on demand when we access it.
try:
    _ = doc.part.numbering_part
except Exception:
    # create a numbering part by adding a List Bullet styled paragraph then removing—fallback
    pass

numId = ensure_bullet_num()

def make_bullet(p):
    pPr = p._p.get_or_add_pPr()
    # remove any existing numPr
    for old in pPr.findall(qn('w:numPr')):
        pPr.remove(old)
    numPr = OxmlElement('w:numPr')
    ilvl = OxmlElement('w:ilvl'); ilvl.set(qn('w:val'), '0'); numPr.append(ilvl)
    nid = OxmlElement('w:numId'); nid.set(qn('w:val'), str(numId)); numPr.append(nid)
    pPr.append(numPr)

# Walk Section 2; bullet the fact lines only.
inS2 = False
phase_labels = {"situation:", "the disagreement & pivot:", "action taken:", "result:",
                "the roadblock:", "the tension & trade-off:"}
for p in doc.paragraphs:
    t = p.text.strip()
    if t.startswith("Section 2"):
        inS2 = True; continue
    if t.startswith("Section 3"):
        break
    if not inS2 or not t:
        continue
    low = t.lower()
    if low.startswith("maps to:"):  # italic pointer, no bullet
        continue
    if low.startswith("rehearse from the bullets"):  # intro
        continue
    if p.style.name == "Heading 3":
        continue
    if low in phase_labels:  # bold phase header, no bullet
        continue
    # everything else in S2 = a fact line -> bullet it
    make_bullet(p)

doc.save(str(OUT))
print("STEP 3 done — fact lines bulleted. numId=", numId)
