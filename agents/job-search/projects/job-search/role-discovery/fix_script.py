content = open('ks_residential_reset.py').read()
# Fix literal backslash-n sequences in code
content = content.replace(
    'connect_over_cdp(CDP_RESIDENTIAL)\\n    ctx = b.contexts[0] if b.contexts else b.new_context()',
    'connect_over_cdp(CDP_RESIDENTIAL)\n    ctx = b.contexts[0] if b.contexts else b.new_context()'
)
content = content.replace(
    'ctx.new_page()\\n    pg.goto(reset_url',
    'ctx.new_page()\n    pg.goto(reset_url'
)
open('ks_residential_reset.py', 'w').write(content)
print('Fixed. Checking syntax...')
import ast
try:
    ast.parse(content)
    print('Syntax OK')
except SyntaxError as e:\n    print(f'Error at line {e.lineno}: {e.msg}')
    lines = content.split('\n')
    for i in range(max(0,e.lineno-3), min(len(lines),e.lineno+2)):
        print(f'{i+1}: {repr(lines[i][:80])}')
