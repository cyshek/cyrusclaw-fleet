import sys
fname = '_icims_runner.py'
with open(fname) as f:
    lines = f.readlines()

# Find function boundaries
start = None
end = None
for i, ln in enumerate(lines):
    if ln.strip().startswith('def try_solve_hcaptcha'):
        start = i
    elif start is not None and i > start + 2 and ln.strip().startswith('def ') and 'try_solve' not in ln:
        end = i
        break
print(f'Found: lines {start+1}-{end}')
# Just print the function for inspection
for ln in lines[start:end]:
    sys.stdout.write(ln)
