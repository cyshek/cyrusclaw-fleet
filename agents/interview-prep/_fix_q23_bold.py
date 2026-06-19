"""
Surgical fix: re-bold the inline leading label ("Why do I want ... :", "What does ... :",
"What is this role:") on the 4 Q2/Q3 bullets in the Mintlify + Podium guides.

These two 06-10 builds dropped the bold-run split (single plain run per bullet).
New Relic + Datadog have it correct. We bring these two in line.

ADDITIVE/SURGICAL: we only touch the 4 target bullets; we split the existing single run
into [bold label][plain remainder]. No text content changes, no other paragraph touched.
"""
import copy
from docx import Document

TARGETS = [
    "guides/mintlify-solutions-engineer-post-sales/Mintlify_SE_PostSales_Interview_Prep_Guide.docx",
    "guides/podium-product-manager/Podium_PM_Interview_Prep_Guide.docx",
]

# A bullet qualifies if its text starts with one of these label stems and contains ": "
LABEL_PREFIXES = (
    "Why do I want to work at ",
    "Why do I want this role:",
    "What does ",
    "What is this role:",
)


def is_target_bullet(text):
    t = text.strip()
    for p in LABEL_PREFIXES:
        if t.startswith(p):
            return True
    return False


def split_label_run(p):
    """Split the first run so the 'Label: ' lead-in becomes its own bold run."""
    full = p.text
    if ":" not in full:
        return False
    idx = full.index(":")
    label = full[: idx + 1]            # include the colon
    # keep any single trailing space with the bold label, matching New Relic ("...: ")
    rest = full[idx + 1 :]
    if rest.startswith(" "):
        label = label + " "
        rest = rest[1:]

    runs = p.runs
    if not runs:
        return False
    first = runs[0]

    # Style the first run as the bold LABEL and set its text to the label only.
    first.text = label
    first.bold = True

    # Remove any other existing runs (the bullet was a single run, but be safe).
    for extra in list(runs[1:]):
        extra._element.getparent().remove(extra._element)

    # Add a new run for the remainder, cloning the first run's rPr but NOT bold,
    # so font/size/family are preserved.
    if rest:
        new_r = copy.deepcopy(first._element)
        # set its text
        # clear existing text nodes in the clone
        for t in new_r.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            new_r.remove(t)
        # build a fresh w:t
        from docx.oxml.ns import qn
        wt = new_r.makeelement(qn('w:t'), {})
        wt.text = rest
        wt.set(qn('xml:space'), 'preserve')
        new_r.append(wt)
        # ensure not bold: drop/!set b in rPr
        rpr = new_r.find(qn('w:rPr'))
        if rpr is not None:
            for b in rpr.findall(qn('w:b')):
                rpr.remove(b)
            for b in rpr.findall(qn('w:bCs')):
                rpr.remove(b)
        first._element.addnext(new_r)
    return True


def fix(path):
    doc = Document(path)
    fixed = 0
    for p in doc.paragraphs:
        if is_target_bullet(p.text):
            # Only fix if not already split into a bold label
            already = bool(p.runs and p.runs[0].bold and ":" in p.runs[0].text and len(p.runs) >= 2)
            if already:
                continue
            if split_label_run(p):
                fixed += 1
                print("   bolded:", p.text[:60])
    doc.save(path)
    print("SAVED", path, "-> fixed", fixed, "bullets")
    return fixed


if __name__ == "__main__":
    total = 0
    for t in TARGETS:
        print("==>", t)
        total += fix(t)
    print("TOTAL fixed:", total)
