p = "_probe2_wd_date.py"
s = open(p).read()
NL = chr(10)
BS_N = chr(92) + "n"
pairs = [
    ('with open(STATUS, "a") as f:' + BS_N + '            f.write(',
     'with open(STATUS, "a") as f:' + NL + '            f.write('),
    ('    except Exception as e:' + BS_N + '        return {"err": str(e)[:120], "base": base}',
     '    except Exception as e:' + NL + '        return {"err": str(e)[:120], "base": base}'),
    ('        return "err:" + str(e)[:70]', '        return "err:" + str(e)[:70]'),  # noop safety
    ('    except Exception as e:' + BS_N + '        return "err:" + str(e)[:70]',
     '    except Exception as e:' + NL + '        return "err:" + str(e)[:70]'),
    ('    with sync_playwright() as p:' + BS_N + '        ctx = p.chromium.launch_persistent_context(' + BS_N + '            user_data_dir',
     '    with sync_playwright() as p:' + NL + '        ctx = p.chromium.launch_persistent_context(' + NL + '            user_data_dir'),
    ('                except Exception as e:' + BS_N + '                    ret = "EXC:" + str(e)[:90]',
     '                except Exception as e:' + NL + '                    ret = "EXC:" + str(e)[:90]'),
]
for bad, good in pairs:
    c = s.count(bad)
    s = s.replace(bad, good)
    print("replaced", c, "x:", repr(bad[:40]))
open(p, "w").write(s)
print("WROTE_OK")
