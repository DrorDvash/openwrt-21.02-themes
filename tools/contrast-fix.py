#!/usr/bin/env python3
"""Minimal, targeted WCAG AA colour fixes for a ported theme.

Reads the theme's a11y.json (tools/a11y.py) and, for every failing text, writes
a rule for exactly the failing element in its recorded context (e.g.
`.cbi-value-title`, `footer a`, `.zonebadge strong`, `#cbi-firewall-redirect
.cbi-button-remove`) with the text colour moved in lightness, same hue, until it
reaches TARGET against every background it failed on. Text that is already
pure white/black gets a darker/lighter background instead. Button rules exclude
:hover/:focus so the theme's hover states stay as designed. Elements without a
usable context are listed for a manual fix.

The rules go into an auto-managed block in css/35-THEME-port.css; re-running
replaces that block and keeps hand-written rules around it. Iterate:
  port-theme.py THEME --quick  ->  contrast-fix.py THEME  ->  port-theme.py THEME --quick ...
(add --baseline argon to all three for the Argon-layout variant)

usage: contrast-fix.py THEME [--baseline B] [--a11y PATH] [--scope SELECTOR] [--dry-run]
  --scope prefixes every rule (own auto block per scope), e.g. ':root[data-tod="day"]'
  for themes whose palette depends on a root attribute (circadian).
"""
import argparse, colorsys, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = 4.6
BEGIN, END = "/* AUTO-CONTRAST BEGIN (tools/contrast-fix.py) */", "/* AUTO-CONTRAST END */"
GENERIC = {"btn", "cbi-button", "center", "nowrap", "important", "td", "th", "tr", "left", "right", "fade-in"}


def parse(v):
    """rgb(a) -> (r, g, b); None for a fully transparent colour (gradient-clipped text: the
    background paints the letters, so a background "fix" there would wipe the text out)"""
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", v.strip())
    if not m or (m.group(4) is not None and float(m.group(4)) == 0):
        return None
    return tuple(int(m.group(i)) for i in (1, 2, 3))


def lum(c):
    f = lambda x: x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4
    r, g, b = (x / 255 for x in c)
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)))
    return (lb + .05) / (la + .05)


def adjust(fg, bgs):
    lighter = lum(fg) >= sum(lum(b) for b in bgs) / len(bgs)
    h, l, s = colorsys.rgb_to_hls(*(x / 255 for x in fg))
    while 0 <= l <= 1:
        c = tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, l, s))
        if min(ratio(c, b) for b in bgs) >= TARGET:
            return c
        l += .005 if lighter else -.005
    return None


def hexc(c):
    return "#%02x%02x%02x" % c


def classes(sel):
    tag, *cls = sel.split(".")
    return tag, [c for c in cls if c and c not in GENERIC]


def selector(ctx, sel):
    tag, cls = classes(sel)
    el = (tag if tag else "") + "".join("." + c for c in cls)
    if tag == "button" or "cbi-button" in sel:
        el = (el or "button") + ":not(:hover):not(:focus)"
    ctag, ccls = classes(ctx) if not ctx.startswith("#") else ("", [])
    if ctx not in ("page", "") and not ctx.startswith("#") and (ctag, ccls) == (tag, cls):
        return (tag + "".join("." + x for x in cls)) or None   # the text element is the context itself
    if ctx.startswith("#cbid.") or ctx.startswith("#widget."):
        c = ".cbi-dropdown"                      # dynamic widget ids
    elif ctx.startswith("#"):
        c = ctx if re.fullmatch(r"#[A-Za-z][\w-]*", ctx) else None
    elif ctx in ("page", ""):
        c = None
    else:
        ctag, ccls = classes(ctx)
        c = "".join("." + x for x in ccls) or ctag
    if c is None:
        return el if (cls and tag) else None    # e.g. button.cbi-button-negative anywhere
    return f"{c} {el}" if el else c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("theme")
    ap.add_argument("--a11y")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scope", default="")
    ap.add_argument("--baseline", help="default: bootstrap, or the theme's own baseline (aurora, alpha)")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import baselines
    t = a.theme
    tid = baselines.theme_id(t, a.baseline or baselines.native_baseline(t) or "bootstrap")
    src = os.path.join(ROOT, "themes", f"luci-theme-{tid}")
    jpath = a.a11y or (os.path.join(ROOT, "dist/screenshots", tid, "a11y/a11y.json") if tid == "rack21"
                       else os.path.join(ROOT, "dist/ports", tid, "screenshots/a11y/a11y.json"))
    r = json.load(open(jpath))
    global BEGIN, END
    if a.scope:
        BEGIN = BEGIN.replace(" BEGIN", f" BEGIN [{a.scope}]")
        END = END.replace(" END", f" END [{a.scope}]")

    # keep earlier auto rules (they fixed elements that now pass) and add/replace new ones
    p35 = glob.glob(f"{src}/css/35-*.css")[0]
    cur = open(p35).read()
    old = re.search(re.escape(BEGIN) + r"(.*?)" + re.escape(END), cur, flags=re.S)
    rules = {}
    if old:
        for m in re.finditer(r"^(.+?) \{ (color|background): (#[0-9a-f]{6}) !important; \}(.*)$", old.group(1), re.M):
            rules[(m.group(1), m.group(2))] = (m.group(3), m.group(4).strip())

    groups, manual = {}, []
    for page, v in r["contrast"].items():
        for f in v["fails"]:
            fg, bg = parse(f["color"]), parse(f["bg"])
            if not (fg and bg):
                continue
            s = selector(f.get("ctx", ""), f["sel"])
            if s and a.scope:
                s = f"{a.scope} {s}"
            if not s:
                manual.append(f"{hexc(fg)} on {hexc(bg)} {ratio(fg, bg):.2f}:1  {f.get('ctx')} {f['sel']} '{f['text'][:24]}' ({page.split('/')[-1]})")
                continue
            groups.setdefault((s, fg), set()).add(bg)

    for (s, fg), bgs in groups.items():
        if fg in ((255, 255, 255), (0, 0, 0)):
            for bg in bgs:
                nb = adjust(bg, [fg])
                if nb:
                    rules[(s, "background")] = (hexc(nb), f"/* was {hexc(bg)} under {hexc(fg)}: {ratio(fg, bg):.2f} -> {ratio(fg, nb):.2f}:1 */")
            continue
        prev = rules.get((s, "color"))
        base = fg
        new = adjust(base, list(bgs))
        if not new:
            # the hue can't get there (e.g. cream text on a mid green): plain black or white text
            best = max(((17, 17, 17), (255, 255, 255)), key=lambda c: min(ratio(c, b) for b in bgs))
            new = best if min(ratio(best, b) for b in bgs) >= TARGET else None
        if new:
            rules[(s, "color")] = (hexc(new), f"/* was {hexc(fg)}: {min(ratio(fg, b) for b in bgs):.2f} -> {min(ratio(new, b) for b in bgs):.2f}:1 */")
            continue
        # near-white/near-black text on a mid-tone fill (e.g. #f2ecff on a red button): no text
        # colour reaches 4.6:1, so move the element's background instead, same hue
        done = False
        for bg in bgs:
            nb = adjust(bg, [fg])
            if nb:
                rules[(s, "background")] = (hexc(nb), f"/* was {hexc(bg)} under {hexc(fg)}: {ratio(fg, bg):.2f} -> {ratio(fg, nb):.2f}:1 */")
                done = True
        if not done:
            manual.append(f"{hexc(fg)} cannot reach {TARGET}:1 on {[hexc(b) for b in bgs]} ({s})")

    lines = [BEGIN] + [f"{s} {{ {p}: {val} !important; }} {why}" for (s, p), (val, why) in sorted(rules.items())] + [END]
    print(f"{tid}: {len(rules)} auto rules, {len(manual)} need a manual look")
    for l in lines[1:-1]:
        print("  ", l[:170])
    for m in manual:
        print("   MANUAL:", m[:170])
    if a.dry_run:
        return
    cur = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", cur, flags=re.S).rstrip() + "\n"
    if rules:
        cur += "\n" + "\n".join(lines) + "\n"
    open(p35, "w").write(cur)


if __name__ == "__main__":
    main()
