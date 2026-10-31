"""Edge: luci-theme-edge (kiddin9 / GaryPang, Apache-2.0 per its Makefile and file headers,
src/luci-theme-edge, last commit 2023) on 21.02.

  generate("edge") -> luci-theme-edge21/

Edge is a 2020 fork of luci-theme-argon: a light material restyle of Argon's sidebar
layout. Its templates are not ported (they predate Argon 2.2.9's login page and run
curl on the router to fetch Unsplash photos for every login): Edge's stylesheet is put on
our Argon 2.3.1 frame instead (argon.py with a skin). Dropped: the embedded Google Sans
font (proprietary, not redistributable; system fonts instead), login photos and audio,
jQuery-driven script.js, waves.css, the "OPEN WRT" logo image.

The login page is Edge's own look again, without its photos: a frosted card (logo,
"Have a nice day.", underlined user/password fields, blue button) over a landscape the
port draws itself (scene() below: inline SVG mountains, lake and pines, CSS sky and sun;
a night variant for dark mode). edge-template/sysauth.htm is a whole page of its own
(Argon's login frame, header_login/footer_login, is not used); css/login.css is its
only stylesheet.

Edge's colours are hard-coded throughout its CSS, so it is not a reskin baseline: the
same sidebar layout with another theme's colours is --baseline argon.
"""
import os, re, random
from baselines import ROOT, VERSION, PortError, read, MAINTAINER
from baselines import argon

SUFFIX = "-edge"
NATIVE = "edge"
EDGE = os.path.join(ROOT, "src/luci-theme-edge")
TPL = os.path.join(ROOT, "tools/baselines/edge-template")
SYSFONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'


def edge_css():
    css = read(f"{EDGE}/htdocs/luci-static/edge/cascade.css")
    css = css.replace('@import url("custom.css?v=1");', read(f"{EDGE}/htdocs/luci-static/edge/custom.css"))
    css, n = re.subn(r"@font-face\s*\{\s*font-family:\s*'Google Sans';[^}]*\}", "", css, flags=re.S)
    if n != 1:
        raise PortError(["Edge cascade.css: embedded Google Sans face not found"])
    css = css.replace('"Google Sans", ', "").replace("'Google Sans', ", "")
    css = re.sub(r'"Microsoft Yahei", "WenQuanYi Micro Hei", "sans-serif"', SYSFONT + ', "Microsoft Yahei", "WenQuanYi Micro Hei"', css)
    css = css.replace("url('fonts/argon.woff?vncylf')", "url('../fonts/argon.woff')")
    # WCAG AA: Edge's button green carries white text at 2.45:1; same hue, darker (4.66:1)
    css = re.sub(r"#23bd70\b", "#19854f", css, flags=re.I)
    css = css.replace("url(icons/spinner.svg", "url(../../resources/icons/loading.gif")   # luci-base's spinner
    css = css.replace("url(icons/", "url(../icon/").replace("url(../resources/icons/", "url(../../resources/icons/")
    return f"/* luci-theme-edge cascade.css (kiddin9, Apache-2.0); Google Sans and paths adapted by tools/baselines/edge.py */\n" + css


def _ridge(rnd, peaks, floor, step=16, rough=10.0, x0=-16, x1=1616):
    """mountain silhouette: y (top-down) of the lowest of the peak cones at each x, plus noise"""
    xs = list(range(x0, x1 + 1, step))
    noise = [0.0] * len(xs)        # midpoint displacement
    def md(a, b, amp):
        if b - a < 2:
            return
        m = (a + b) // 2
        noise[m] = (noise[a] + noise[b]) / 2 + rnd.uniform(-amp, amp)
        md(a, m, amp * .55); md(m, b, amp * .55)
    md(0, len(xs) - 1, rough * 3)
    pts = []
    for i, x in enumerate(xs):
        y = floor(x) if callable(floor) else floor
        for px, py, sl, sr in peaks:
            y = min(y, py + (px - x) * sl if x < px else py + (x - px) * sr)
        pts.append((x, y + noise[i]))
    return pts


def _poly(pts, close_y=None):
    d = "M" + " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
    if close_y is not None:
        d += f" L{pts[-1][0]:.0f},{close_y} L{pts[0][0]:.0f},{close_y}Z"
    return d


def _pine(rnd, x, base, h, w, tiers=None, prec=1):
    """one pine silhouette (path data): drooping tiers, slightly ragged, a short trunk"""
    tiers = tiers or max(7, min(16, int(h / 50)))
    top, crown = base - h, h * .9
    right, left = [], []
    for side, out in ((1, right), (-1, left)):
        for i in range(1, tiers + 1):
            t = i / tiers
            y = top + crown * t
            # ragged: tiers alternate between long and short branches, tips droop
            half = w / 2 * (.1 + .9 * t ** .85) * rnd.uniform(.72, 1.15)
            droop = h * rnd.uniform(.01, .028)
            notch = half * rnd.uniform(.22, .45)
            if tiers > 4:
                mid = (half + notch) / 2
                out += [(x + side * mid * rnd.uniform(.85, 1), y - droop * .4),
                        (x + side * (mid + half * .1), y - droop * 1.1)]
                if rnd.random() < .5:        # a second, shorter spike under the tip
                    out += [(x + side * half * .97, y + droop * .2), (x + side * half * .8, y + droop * .1)]
            out += [(x + side * half, y + droop), (x + side * notch, y + droop * .6)]
    tw = max(2.0, w * .035)
    pts = [(x, top)] + right + [(x + tw, base), (x - tw, base)] + left[::-1]
    return "M" + " ".join(f"{px:.{prec}f},{py:.{prec}f}" for px, py in pts) + "Z"


def scene():
    """the login landscape, drawn by this port (seeded, so every build is identical): the
    mountains/lake band (viewBox 1600x600, sliced from the bottom centre) and two pine groups
    (viewBox 600x1000, anchored to the bottom corners). Colours come from CSS (classes)."""
    rnd = random.Random(2026)
    far = _ridge(rnd, [(150, 300, .55, .7), (420, 250, .6, .5), (700, 300, .5, .6), (980, 235, .55, .6),
                       (1240, 290, .6, .55), (1500, 245, .5, .6)], 420, rough=6)
    mid = _ridge(rnd, [(60, 330, .7, .6), (330, 300, .6, .8), (560, 370, .7, .7), (1060, 360, .7, .6),
                       (1290, 300, .7, .6), (1560, 340, .6, .7)], lambda x: 470, rough=8)
    near = _ridge(rnd, [(-40, 330, 1, .5), (240, 380, .5, .45), (1380, 380, .45, .5), (1660, 320, .5, 1)],
                  lambda x: 455 + 70 * (1 - abs(x - 800) / 800) ** 2, rough=7)
    ground = _ridge(rnd, [(-60, 450, 1, .32), (1660, 450, .32, 1)],
                    lambda x: 560 - 30 * (1 - abs(x - 800) / 800), rough=4, step=20)
    # lit (sun-side) faces on the far and middle ranges
    facets = []
    for pts, peaks in ((far, [(420, 250), (980, 235), (1500, 245), (150, 300)]), (mid, [(330, 300), (1290, 300), (60, 330)])):
        for px, py in peaks:
            span = rnd.uniform(70, 110)
            ridge = [(x, y) for x, y in pts if px - span <= x <= px]
            if ridge:
                facets.append(_poly(ridge + [(px + span * .3, py + span * 1.25), (px - span * .2, py + span * 1.3)]) + "Z")
    # small trees along the far shore and on the near hills
    small = []
    for x in range(-10, 1610, 11):
        dist = abs(x - 800)
        if dist < 150:
            continue
        y = next(yy for xx, yy in near if xx >= x) + rnd.uniform(4, 16)
        h = rnd.uniform(14, 30) * (1 + dist / 900)
        small.append(_pine(rnd, x, y + 6, h, h * .45, tiers=3, prec=0))
    lake = ("M520,524 C560,505 640,492 720,490 C760,486 840,486 900,490 C980,494 1060,505 1085,522 "
            "C1040,538 960,548 860,552 C800,556 720,554 650,548 C590,543 545,535 520,524Z")
    mountains = (
        '<svg class="e21-band" viewBox="0 0 1600 600" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">'
        '<defs><linearGradient id="e21-lake" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="lk1"/><stop offset="1" class="lk2"/></linearGradient>'
        '<linearGradient id="e21-haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="hz1"/><stop offset="1" class="hz2"/></linearGradient></defs>'
        f'<path class="m-far" d="{_poly(far, 600)}"/><path class="m-lit" d="{" ".join(facets[:4])}"/>'
        f'<rect y="300" width="1600" height="300" fill="url(#e21-haze)"/>'
        f'<path class="m-mid" d="{_poly(mid, 600)}"/><path class="m-lit2" d="{" ".join(facets[4:])}"/>'
        f'<path class="m-near" d="{_poly(near, 600)}"/>'
        f'<path class="m-trees" d="{" ".join(small)}"/>'
        f'<path fill="url(#e21-lake)" d="{lake}"/>'
        '<path class="m-glint" d="M690,500h120v1.5H690zM860,509h70v1.2H860zM640,522h90v1.2H640zM800,534h110v1.2H800z"/>'
        f'<path class="m-ground" d="{_poly(ground, 600)}"/></svg>')
    def group(seed, trees):
        r = random.Random(seed)
        return "".join(f'<path{" class=\"p2\"" if h < 500 else ""} d="{_pine(r, x, 1000 + r.uniform(0, 12), h, h * w, prec=0)}"/>'
                       for x, h, w in sorted(trees, key=lambda tr: tr[1]))
    left = group(7, [(330, 560, .42), (470, 420, .4), (90, 900, .4), (230, 760, .42), (560, 300, .42)])
    right = group(11, [(260, 470, .42), (120, 640, .4), (420, 820, .42), (540, 980, .4), (30, 330, .44)])
    pines = ('<svg class="e21-pines e21-left" viewBox="0 0 600 1000" preserveAspectRatio="xMinYMax meet" aria-hidden="true" focusable="false">'
             f'{left}</svg><svg class="e21-pines e21-right" viewBox="0 0 600 1000" preserveAspectRatio="xMaxYMax meet" '
             f'aria-hidden="true" focusable="false">{right}</svg>')
    return mountains + pines


def login(out, tid):
    """Edge's login look on 21.02: own sysauth page + css/login.css (replaces Argon's login frame)"""
    views = f"{out}/luasrc/view/themes/{tid}"
    for n in ("header_login", "footer_login", "out_header_login"):    # Argon's login frame: unused
        os.remove(f"{views}/{n}.htm")
    page = read(f"{TPL}/sysauth.htm").replace("@SCENE@", scene())
    for k, v in (("@ID@", tid), ("@VERSION@", VERSION)):
        page = page.replace(k, v)
    with open(f"{views}/sysauth.htm", "w", encoding="utf-8") as f:
        f.write(page)
    css = read(f"{TPL}/login.css")
    try:
        import rcssmin
        css = rcssmin.cssmin(css) + "\n"
    except ImportError:
        pass
    os.makedirs(f"{out}/htdocs/luci-static/{tid}/css", exist_ok=True)
    with open(f"{out}/htdocs/luci-static/{tid}/css/login.css", "w", encoding="utf-8") as f:
        f.write(f"/*! {tid} login page: Apache-2.0, see NOTICE. The landscape is drawn by the port. */\n" + css)


def generate(t, out=None):
    if t != NATIVE:
        raise PortError([f"Edge's colours are hard-coded, it is not a reskin baseline: for {t} in "
                         f"this sidebar layout use --baseline argon"])
    tid = "edge21"
    skin = {
        "id": tid, "title": "Edge", "key": "Edge21", "dark": False, "themecolor": "#5a8dee",
        "content": edge_css(), "port": read(f"{TPL}/30-edge-port.css"), "dark_css": read(f"{TPL}/dark.css"),
        "logo_svg": f"{TPL}/logo.svg", "favicon": f"{TPL}/favicon.png",
        "control": (
            f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
            f"Source: https://github.com/kiddin9/luci-theme-edge\nLicense: Apache-2.0\nSection: luci\n"
            f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
            f"Description: Edge (21.02 port) - material sidebar theme, light and dark.\n"
            f" Edge's stylesheet (kiddin9, Apache-2.0) on the luci-theme-argon 2.3.1 frame\n"
            f" (jerrykuku, Apache-2.0). Registers luci.themes.Edge21; it does not change the\n"
            f" active theme.\n"),
        "notice": (
            f"luci-theme-{tid} - \"Edge (21.02 port)\"\n\n"
            f"Stylesheet from luci-theme-edge by Kiddin' (kiddin9) and GaryPang,\n"
            f"https://github.com/kiddin9/luci-theme-edge. The repository has no LICENSE file; its\n"
            f"Makefile (PKG_LICENSE:=Apache-2.0) and file headers state the Apache License 2.0.\n"
            f"Edge derives from luci-theme-argon by jerrykuku and luci-theme-material by Lutty Yang\n"
            f"(both Apache-2.0); its header credits the Argon Dashboard design by Creative Tim.\n"
            f"Layout, templates, menu script, icon font and jQuery copy from luci-theme-argon 2.3.1\n"
            f"by jerrykuku, https://github.com/jerrykuku/luci-theme-argon (Apache-2.0).\n\n"
            f"Port changes (2026, Dror Dvash): Edge's stylesheet put on the Argon 2.3.1 templates\n"
            f"(Edge's own templates not used: they fetched Unsplash photos with curl on the router\n"
            f"and played remote login audio); the embedded Google Sans font removed (not\n"
            f"redistributable; system fonts instead); login photos, script.js, waves.css and logo\n"
            f"image removed; a dark palette of the port's own (Edge is light only upstream) with\n"
            f"a light/dark button, following the browser until one is picked; Edge's login look\n"
            f"(frosted card over a landscape) rebuilt with a landscape drawn by the port in SVG/CSS\n"
            f"(no photos, audio or downloads), with a night variant; reduced-motion\n"
            f"support, 21.02 widget fixes, phone fix for\n"
            f"\"-- custom --\" dropdown entries.\n"),
    }
    out = argon.generate(t, out, skin=skin)
    login(out, tid)
    return out
