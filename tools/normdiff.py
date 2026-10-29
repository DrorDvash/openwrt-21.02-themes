#!/usr/bin/env python3
"""Compare two JS/CSS files after minifying both and stripping all whitespace.
Usage: normdiff.py A B  -> prints SAME or DIFF plus a short context."""
import sys, re, difflib, rjsmin, rcssmin
def norm(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    s = rcssmin.cssmin(s) if p.endswith(".css") else rjsmin.jsmin(s)
    return re.sub(r"\s+", "", s)
a, b = norm(sys.argv[1]), norm(sys.argv[2])
if a == b:
    print("SAME", sys.argv[2]); sys.exit(0)
print("DIFF", sys.argv[2], len(a), len(b))
sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op != "equal":
        print(f"  {op}: upstream[{a[max(0,i1-60):i2+40]!r}]\n      router  [{b[max(0,j1-60):j2+40]!r}]")
