#!/usr/bin/env python3
"""Compare CSS files order-insensitively at declaration level (csstidy reorders).
Prints declarations present in only one file, keyed by selector."""
import sys, re, rcssmin
def rules(p):
    s = rcssmin.cssmin(open(p, encoding="utf-8").read())
    s = re.sub(r"\s+", " ", s)
    out = set()
    # flatten one level of @media
    stack, sel, buf, ctx = [], "", "", []
    for ch in s:
        if ch == "{":
            ctx.append(buf.strip()); buf = ""
        elif ch == "}":
            if buf.strip():
                for d in buf.split(";"):
                    d = d.strip().replace(" ", "")
                    if d:
                        d = re.sub(r"#([0-9a-f])\1([0-9a-f])\2([0-9a-f])\3\b", r"#\1\2\3", d.lower())
                        for sl in ctx[-1].split(","):
                            out.add((" ".join(ctx[:-1]).replace(" ", ""), sl.strip().replace(" ", ""), d))
            buf = ""; ctx and ctx.pop()
        else:
            buf += ch
    return out
a, b = rules(sys.argv[1]), rules(sys.argv[2])
print(f"only-upstream={len(a-b)} only-router={len(b-a)}")
for x in sorted(a-b)[:25]: print("  -", x)
for x in sorted(b-a)[:25]: print("  +", x)
