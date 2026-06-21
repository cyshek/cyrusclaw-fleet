import zipfile
with zipfile.ZipFile('Everpure_PM_Systems_PrepBundle.zip') as z:\n    for name in z.namelist():
        info = z.getinfo(name)
        print(f"  {name} ({info.file_size:,} bytes)")
