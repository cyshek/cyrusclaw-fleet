import io

path = "strategies_candidates/leveraged_long_trend/backtest_daily.py"
src = open(path).read()

bad = '    if len(values) < n:\\n        return None\\n    return sum(values[-n:]) / n'
good = "    if len(values) < n:\n        return None\n    return sum(values[-n:]) / n"

if bad in src:
    src = src.replace(bad, good)
    open(path, "w").write(src)
    print("FIXED _sma")
else:
    print("pattern not found; manual scan:")
    for i, line in enumerate(src.splitlines(), 1):
        if "\\n" in line:
            print("  line", i, repr(line))
