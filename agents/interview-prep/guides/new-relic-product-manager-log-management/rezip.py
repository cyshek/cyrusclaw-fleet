import zipfile, os

bundle_dir = "bundle"
guide = "New_Relic_PM_Interview_Prep_Guide.docx"
out = "New_Relic_PM_Bundle.zip"

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:\n    z.write(guide)\n    for f in os.listdir(bundle_dir):
        z.write(os.path.join(bundle_dir, f), f)

print("done:", out)
