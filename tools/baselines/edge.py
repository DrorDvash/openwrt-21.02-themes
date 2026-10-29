"""Edge: luci-theme-edge (kiddin9 / GaryPang, Apache-2.0 per its Makefile and file headers,
src/luci-theme-edge, last commit 2023) on 21.02.

  generate("edge") -> luci-theme-edge21/

Edge is a 2020 fork of luci-theme-argon: a light material restyle of Argon's sidebar
layout. Its templates are not ported (they predate Argon 2.2.9's login page and run
curl on the router to fetch Unsplash photos for every login): Edge's stylesheet is put on
our Argon 2.3.1 frame instead (argon.py with a skin). Dropped: the embedded Google Sans
font (proprietary, not redistributable; system fonts instead), login photos and audio,
jQuery-driven script.js, waves.css, the "OPEN WRT" logo image.

Edge's colours are hard-coded throughout its CSS, so it is not a reskin baseline: the
same sidebar layout with another theme's colours is --baseline argon.
"""
import os, re
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
            f"a light/dark button, following the browser until one is picked; reduced-motion\n"
            f"support, 21.02 widget fixes, phone fix for\n"
            f"\"-- custom --\" dropdown entries.\n"),
    }
    return argon.generate(t, out, skin=skin)
