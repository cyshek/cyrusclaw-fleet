p = "_probe_wd_date.py"
s = open(p).read()
NL = chr(10)
BS_N = chr(92) + "n"  # literal backslash + n

# In the broken code lines, a literal backslash-n appears where a real newline belongs.
# But we must NOT touch:
#   - the f-string content f"[{ts}] {msg}\n"  (that \n is intentional -> keep as backslash-n)
#   - the DATE_DOM_JS / other JS heredocs (raw strings, real newlines already)
#   - .replace(chr(10), ...) style code
# The safe move: only collapse the SPECIFIC broken join sequences below.

pairs = [
    # (broken_literal, fixed)
    ('as f:' + BS_N + '            f.write(', 'as f:' + NL + '            f.write('),
    ('            if g:' + BS_N + '                return str(g[0])' + BS_N + '    return None' + BS_N + BS_N + BS_N + 'DATE_DOM_JS',
     '            if g:' + NL + '                return str(g[0])' + NL + '    return None' + NL + NL + NL + 'DATE_DOM_JS'),
    ('    except Exception as e:' + BS_N + '        return {"err": str(e)[:120]}',
     '    except Exception as e:' + NL + '        return {"err": str(e)[:120]}'),
    ('    except Exception as e:' + BS_N + '        return "err:" + str(e)[:80]',
     '    except Exception as e:' + NL + '        return "err:" + str(e)[:80]'),
    ('    with sync_playwright() as p:' + BS_N + '        ctx = p.chromium.launch_persistent_context(' + BS_N + '            user_data_dir',
     '    with sync_playwright() as p:' + NL + '        ctx = p.chromium.launch_persistent_context(' + NL + '            user_data_dir'),
    ('            except Exception as e:' + BS_N + '                status("handle_experience err: " + str(e)[:120])',
     '            except Exception as e:' + NL + '                status("handle_experience err: " + str(e)[:120])'),
    ('                except Exception as e:' + BS_N + '                    ret = "EXC:" + str(e)[:100]',
     '                except Exception as e:' + NL + '                    ret = "EXC:" + str(e)[:100]'),
]
for bad, good in pairs:
    c = s.count(bad)
    s = s.replace(bad, good)
    print("replaced", c, "x:", repr(bad[:45]))
open(p, "w").write(s)
print("WROTE_OK")
