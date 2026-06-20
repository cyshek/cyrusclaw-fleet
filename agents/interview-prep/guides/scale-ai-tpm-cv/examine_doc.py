import zipfile
import re

path = "/home/azureuser/.openclaw/agents/interview-prep/workspace/guides/scale-ai-tpm-cv/Scale_AI_Interview_Prep_Guide.docx"
with zipfile.ZipFile(path, 'r') as z:\n    xml = z.read('word/document.xml').decode('utf-8')\n\n# Find paragraphs containing Fill in here\npara_pattern = re.compile(r'<w:p[ >].*?</w:p>', re.DOTALL)
paras = para_pattern.findall(xml)

matches = []
for i, p in enumerate(paras):
    if 'Fill in here' in p:\n        matches.append((i, p))\n\nprint(f"Total paragraphs: {len(paras)}")
print(f"Found {len(matches)} paragraphs with 'Fill in here'")
for i, (idx, text) in enumerate(matches):
    print(f"\n--- Match {i+1} (para index {idx}) ---")
    print(text[:800])
