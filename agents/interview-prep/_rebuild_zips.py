"""Rebuild the two delivered bundle zips so they contain the FIXED (bold-label) guide.
Keep the exact same member layout/files that were already in each zip; only the guide
docx content changed on disk. We re-read every member from disk by its path.
"""
import zipfile, os

WS = "/home/azureuser/.openclaw/agents/interview-prep/workspace"

BUNDLES = {
    "guides/Mintlify_SE_PostSales_Bundle.zip": [
        "guides/mintlify-solutions-engineer-post-sales/Mintlify_SE_PostSales_Interview_Prep_Guide.docx",
        "guides/mintlify-solutions-engineer-post-sales/bundle/Mintlify_SE_PostSales_JD.txt",
        "guides/mintlify-solutions-engineer-post-sales/bundle/Cyrus_Shekari_Resume_ashby-mintlify_1312c4be_v2.docx",
        "guides/mintlify-solutions-engineer-post-sales/bundle/Cyrus_Shekari_Resume_ashby-mintlify_1312c4be_v2.pdf",
    ],
    "guides/Podium_PM_Bundle.zip": [
        "guides/podium-product-manager/Podium_PM_Interview_Prep_Guide.docx",
        "guides/podium-product-manager/bundle/Podium_PM_JD.md",
        "guides/podium-product-manager/bundle/Cyrus_Shekari_Resume_master.docx",
        "guides/podium-product-manager/bundle/Cyrus_Shekari_Resume_master.pdf",
    ],
}


def arcname(p):
    # preserve the same internal arcname (strip the leading "guides/")
    return p[len("guides/"):]


for zpath, members in BUNDLES.items():
    full_zip = os.path.join(WS, zpath)
    # sanity: all members exist
    for m in members:
        fp = os.path.join(WS, m)
        assert os.path.exists(fp), "missing: " + fp
    with zipfile.ZipFile(full_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in members:
            zf.write(os.path.join(WS, m), arcname(m))
    print("rebuilt", zpath)
    with zipfile.ZipFile(full_zip) as zf:
        for n in zf.namelist():
            print("   ", n)
