#!/usr/bin/env python3
import sys
content = open('/tmp/uber_diag2.py', 'rb').read()
print("File has", len(content), "bytes")
# Show offending lines
for i, line in enumerate(content.split(b'\n'), 1):
    if b'\x5c\x6e' in line:  # literal backslash-n
        print(f"Line {i}: {repr(line[:80])}")
