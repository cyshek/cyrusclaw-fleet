import io
p="_verify_zips.py"
s=io.open(p,encoding="utf-8").read()
bad="with zipfile.ZipFile(zip_path) as z:"+chr(92)+"n        names = z.namelist()"+chr(92)+"n        print"
good="with zipfile.ZipFile(zip_path) as z:"+chr(10)+"        names = z.namelist()"+chr(10)+"        print"
s=s.replace(bad,good)
io.open(p,"w",encoding="utf-8").write(s)
print("patched, remaining literal:", s.count(chr(92)+"n"))
