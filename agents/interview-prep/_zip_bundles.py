import zipfile, os
os.chdir("/home/azureuser/.openclaw/agents/interview-prep/workspace/guides")
jobs = {
 "Podium_PM_Bundle.zip": ("podium-product-manager", [
     "Podium_PM_Interview_Prep_Guide.docx",
     "bundle/Podium_PM_JD.md",
     "bundle/Cyrus_Shekari_Resume_master.docx",
     "bundle/Cyrus_Shekari_Resume_master.pdf",
 ]),
 "Mintlify_SE_PostSales_Bundle.zip": ("mintlify-solutions-engineer-post-sales", [
     "Mintlify_SE_PostSales_Interview_Prep_Guide.docx",
     "bundle/Mintlify_SE_PostSales_JD.txt",
     "bundle/Cyrus_Shekari_Resume_ashby-mintlify_1312c4be_v2.docx",
     "bundle/Cyrus_Shekari_Resume_ashby-mintlify_1312c4be_v2.pdf",
 ]),
}

def build(zname, root, files):
    z = zipfile.ZipFile(zname, "w", zipfile.ZIP_DEFLATED)
    for f in files:
        src = os.path.join(root, f)
        assert os.path.exists(src), "MISSING " + src
        z.write(src, arcname=os.path.join(os.path.basename(root), f))
    z.close()
    print("WROTE", zname)
    zz = zipfile.ZipFile(zname)
    for n in zz.namelist():
        print("   ", n)
    zz.close()

for zname, (root, files) in jobs.items():
    build(zname, root, files)
