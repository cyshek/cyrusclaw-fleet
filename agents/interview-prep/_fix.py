import io
p = "build_lc_ma.py"
s = io.open(p, encoding="utf-8").read()
bad1 = "except Exception as e:" + chr(92) + "n        print"
good1 = "except Exception as e:" + chr(10) + "        print"
bad2 = "as z:" + chr(92) + "n        for f in files:"
good2 = "as z:" + chr(10) + "        for f in files:"
s = s.replace(bad1, good1).replace(bad2, good2)
io.open(p, "w", encoding="utf-8").write(s)
print("fixed", s.count(chr(92)+"n"), "literal backslash-n remain (string-literals OK)")
