#!/usr/bin/env python3
"""Distinct WCAG AA failures per theme from a11y.json files.
usage: contrast-report.py A11Y_JSON [...]"""
import json, sys, os
for p in sys.argv[1:]:
    r = json.load(open(p))
    seen = {}
    for page, v in r["contrast"].items():
        for f in v["fails"]:
            k = ((f.get("ctx", "") + " " + f["sel"].split(".")[0])[:46], f["color"], f["bg"])
            seen.setdefault(k, [f["ratio"], f["text"][:22], set()])[2].add(page.split("/")[-1])
    parts = p.split("/")
    name = parts[parts.index("ports") + 1] if "ports" in parts else p
    print(f"== {name}: {len(seen)} distinct")
    for (sel, fg, bg), (ratio, text, pages) in sorted(seen.items(), key=lambda x: x[1][0]):
        print(f"   {ratio:5}  {sel:46} {fg:20} on {bg:18} {text!r:26} {len(pages)}p")
