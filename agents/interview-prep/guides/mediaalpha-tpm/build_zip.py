#!/usr/bin/env python3
"""Build MediaAlpha TPM bundle zip."""

import zipfile
import os

OUT_DIR = '/home/azureuser/.openclaw/agents/interview-prep/workspace/guides/mediaalpha-tpm/'
RESUME_DIR = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/submitted/mediaalpha-8525774002/'

FILES = [
    (OUT_DIR + 'MediaAlpha_TPM_Interview_Prep_Guide.docx', 'MediaAlpha_TPM_Interview_Prep_Guide.docx'),
    (OUT_DIR + 'MediaAlpha_TPM_Shorter_Interview_Prep_Guide.docx', 'MediaAlpha_TPM_Shorter_Interview_Prep_Guide.docx'),
    (RESUME_DIR + 'Cyrus_Shekari_Resume_mediaalpha_8525774002_v2.docx', 'Cyrus_Shekari_Resume_mediaalpha_8525774002_v2.docx'),
    (RESUME_DIR + 'Cyrus_Shekari_Resume_mediaalpha_8525774002_v2.pdf', 'Cyrus_Shekari_Resume_mediaalpha_8525774002_v2.pdf'),
    (OUT_DIR + 'MediaAlpha_TPM_JD.md', 'MediaAlpha_TPM_JD.md'),
]

ZIP_PATH = OUT_DIR + 'MediaAlpha_TPM_Bundle.zip'

with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for src, arcname in FILES:
        if not os.path.exists(src):
            print(f"ERROR: Missing file: {src}")
        else:
            zf.write(src, arcname)
            size = os.path.getsize(src)
            print(f"  Added: {arcname} ({size:,} bytes)")

zip_size = os.path.getsize(ZIP_PATH)
print(f"\nZip created: {ZIP_PATH} ({zip_size:,} bytes)")

# List final output dir
print("\nFinal output directory:")
for f in sorted(os.listdir(OUT_DIR)):
    path = os.path.join(OUT_DIR, f)
    if os.path.isfile(path):
        print(f"  {f}: {os.path.getsize(path):,} bytes")
