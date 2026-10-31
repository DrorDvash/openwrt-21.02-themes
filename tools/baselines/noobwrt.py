"""NoobWRT: luci-theme-noobwrt (nooblk-98, Apache-2.0, src/luci-theme-noobwrt) on 21.02.

  generate("noobwrt") -> luci-theme-noobwrt21/

NoobWRT is a 2025 fork of luci-theme-argon (the ucode generation): Argon's sidebar page
structure with its own stylesheet, a quick-access toolbar on the right edge, a split login
card and a light/dark switch. Its stylesheet is the base, its templates are translated to
Lua (noobwrt-template/), its menu script is vendored with the shared "-- custom --" fix.
Dropped: /etc/config/noobwrt and the settings app (default accent colours kept), the
wallpaper fetcher (rpcd backend, Bing/Picsum downloads on the router), the login picture
(an illustration of unknown origin; a CSS sky in its colours instead), the TypoGraphica
font ("All Rights Reserved"; Red Hat Display instead), Google Sans references
(proprietary; Red Hat Display), Red Hat Display italic (synthesised), video backgrounds,
the PWA manifest, the timed dark mode. Kept: Red Hat Display (SIL OFL 1.1, licence shipped
next to it) and NoobWRT's icon font (Argon's, Apache-2.0).
Added: the row of stat cards NoobWRT's screenshots show on top of Status > Overview (they
come from NoobWRT's firmware, not the theme): noobwrt-template/dashboard.js + css/27, built
from read-only ubus calls (system info, luci-rpc getNetworkDevices, LuCI's network.js);
the CPU temperature card shows the load average (21.02 gives the browser no temperature).

NoobWRT's colours are hard-coded throughout its CSS, so it is not a reskin baseline: the
same sidebar layout with another theme's colours is --baseline argon.
"""
import os, re, shutil
from baselines import ROOT, REF, VERSION, PortError, read, write, MAINTAINER, PKGS

SUFFIX = "-noobwrt"
NATIVE = "noobwrt"
NW = os.path.join(ROOT, "src/luci-theme-noobwrt")
TPL = os.path.join(ROOT, "tools/baselines/noobwrt-template")
CONTROL_TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")
COMMON = os.path.join(ROOT, "tools/baselines/common-21.02.css")
OFL = os.path.join(ROOT, "tools/baselines/OFL-1.1.txt")   # SIL OFL 1.1 text (template copyright lines)
NW_VERSION = "1.1.7"
FONT = '"Red Hat Display", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial'
NAVBAR = ("home", "network", "wifi", "firewall", "info", "terminal", "settings")   # toolbar.htm's icons
OFL_COPYRIGHT = "Copyright 2024 The Red Hat Project Authors (https://github.com/RedHatOfficial/RedHatFont)"


def base_css():
    css = read(f"{NW}/htdocs/luci-static/noobwrt/css/cascade.css")
    faces = re.findall(r"@font-face\s*\{[^}]*\}", css)
    def face(m):
        b = m.group(0)
        if "TypoGraphica" in b or "Italic" in b:
            return ""
        if "'noobwrt'" in b:   # the icon font: woff2 only
            return re.sub(r"src:[^;]*;", "src: url('../fonts/noobwrt.woff2') format('woff2');", b)
        return b
    css = re.sub(r"@font-face\s*\{[^}]*\}\s*", face, css)
    if len(faces) != 4 or "TypoGraphica.woff" in css:
        raise PortError([f"NoobWRT cascade.css: expected 4 font faces, found {len(faces)}"])
    css = re.sub(r'--font-family-sans-serif:[^;]*;',
                 f'--font-family-sans-serif: {FONT}, "Microsoft Yahei", "WenQuanYi Micro Hei", sans-serif;', css)
    css = re.sub(r"""font-family:\s*["']TypoGraphica["'];""", f"font-family: {FONT}, sans-serif; font-weight: 800;", css)
    css = re.sub(r"""["']Google Sans["']""", '"Red Hat Display"', css)
    css = css.replace("url(/luci-static/resources/icons/loading.svg)", "url(../../resources/icons/loading.gif)")
    left = re.findall(r"TypoGraphica|Google Sans|/luci-static/noobwrt\b|Italic-Variable", css)
    if left:
        raise PortError([f"NoobWRT cascade.css still references {sorted(set(left))}"])
    return (f"/* luci-theme-noobwrt {NW_VERSION} cascade.css (nooblk-98, Apache-2.0); fonts and paths "
            f"adapted by tools/baselines/noobwrt.py */\n" + css)


def toolbar_css():
    tb = read(f"{NW}/ucode/template/themes/noobwrt/toolbar.ut")
    m = re.search(r"<style>(.*?)</style>", tb, re.S)
    if not m:
        raise PortError(["NoobWRT toolbar.ut: <style> block not found"])
    return (f"/* luci-theme-noobwrt {NW_VERSION} toolbar.ut styles (nooblk-98, Apache-2.0), "
            f"moved out of the template */\n" + m.group(1).strip() + "\n")


def menu_js():
    """NoobWRT's menu script + the shared phone fix for "-- custom --" entries (as argon.py)"""
    menu = read(f"{NW}/htdocs/luci-static/resources/menu-noobwrt.js")
    fix = read(f"{REF}/htdocs/luci-static/resources/menu-rack21.js")
    fn = fix[fix.index("\t/*\n\t * \"-- custom --\" entries"):fix.index("\trender: function(tree)")]
    load = "ui.menu.load().then(L.bind(this.render, this));"
    if menu.count(load) != 1 or menu.count("return baseclass.extend({") != 1:
        raise PortError(["menu-noobwrt.js: __init__ or baseclass.extend not found once"])
    menu = menu.replace(load, load + "\n\t\tthis.initCustomEntry();")
    return menu.replace("return baseclass.extend({", "return baseclass.extend({\n" + fn)


def generate(t, out=None):
    if t != NATIVE:
        raise PortError([f"NoobWRT's colours are hard-coded, it is not a reskin baseline: for {t} in "
                         f"this sidebar layout use --baseline argon"])
    from PIL import Image
    tid = "noobwrt21"
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    keep35 = os.path.join(out, "css", "35-noobwrt-port.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None
    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)
    src = f"{NW}/htdocs/luci-static/noobwrt"
    write(f"{css}/base-noobwrt-{NW_VERSION}.css", base_css())
    write(f"{css}/dark.css", f"/* luci-theme-noobwrt {NW_VERSION} dark.css (nooblk-98, Apache-2.0) */\n"
          + read(f"{src}/css/dark.css"))
    write(f"{css}/25-noobwrt-toolbar.css", toolbar_css())
    write(f"{css}/27-noobwrt-dashboard.css", read(f"{TPL}/27-noobwrt-dashboard.css"))
    write(f"{css}/30-noobwrt-port.css", read(f"{TPL}/30-noobwrt-port.css") + "\n" + read(COMMON))
    write(f"{css}/35-noobwrt-port.css", keep35 or "\n/* NoobWRT on 21.02: theme-specific fixes */\n")

    st = f"{out}/htdocs/luci-static/{tid}"
    for sub, files in (("fonts", ["RedHatDisplay-Variable.woff2", "noobwrt.woff2"]),
                       ("icon", ["favicon-32x32.png", "apple-icon-144x144.png", "android-icon-192x192.png", "arrow.svg"]),
                       ("img", ["blank.png", "volume_high.svg", "volume_off.svg"])):
        os.makedirs(f"{st}/{sub}", exist_ok=True)
        for f in files:
            shutil.copy(f"{src}/{sub}/{f}", f"{st}/{sub}/{f}")
    ofl = re.sub(r"\ACopyright.*?(?=\n\n)", OFL_COPYRIGHT, read(OFL), flags=re.S)
    write(f"{st}/fonts/OFL.txt", "Red Hat Display (RedHatDisplay-Variable.woff2)\n\n" + ofl)
    logo = Image.open(f"{src}/img/logo.png")
    logo.thumbnail((256, 256))
    logo.save(f"{st}/img/logo.png", optimize=True)
    brand = Image.open(f"{src}/img/brand.png")
    brand.quantize(64, method=Image.Quantize.FASTOCTREE).save(f"{st}/img/brand.png", optimize=True)
    os.makedirs(f"{st}/navbar")
    for n in NAVBAR:
        ic = Image.open(f"{src}/navbar/{n}.png")
        ic.thumbnail((48, 48))
        ic.save(f"{st}/navbar/{n}.png", optimize=True)

    subs = {"@ID@": tid, "@KEY@": "NoobWRT21", "@VERSION@": VERSION, "@NWVER@": NW_VERSION,
            "@THEMECOLOR@": "#5e72e4"}

    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    # the Overview's stat cards (NoobWRT's firmware has them, the theme doesn't): footer.htm loads
    # it on admin/status/overview only; read-only ubus calls, no ACL or view of our own
    write(f"{st}/dashboard.js", fill(read(f"{TPL}/dashboard.js")))
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    write(f"{out}/htdocs/luci-static/resources/menu-{tid}.js", menu_js())
    for n in ("header", "footer", "toolbar", "header_login", "footer_login", "out_header_login", "sysauth"):
        write(f"{out}/luasrc/view/themes/{tid}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{CONTROL_TPL}/{n}")), 0o755)
    write(f"{out}/CONTROL/control", (
        f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
        f"Source: https://github.com/nooblk-98/luci-theme-noobwrt\nLicense: Apache-2.0, OFL-1.1\nSection: luci\n"
        f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
        f"Description: NoobWRT (21.02 port) - clean sidebar theme with a quick-access toolbar.\n"
        f" Port of luci-theme-noobwrt {NW_VERSION} (nooblk-98, Apache-2.0) to OpenWrt 21.02\n"
        f" Lua templates. Light or dark (follows the browser, switch in the toolbar).\n"
        f" Registers luci.themes.NoobWRT21; it does not change the active theme.\n"))
    shutil.copy(f"{NW}/LICENSE", f"{out}/LICENSE")
    write(f"{out}/NOTICE", (
        f"luci-theme-{tid} - \"NoobWRT (21.02 port)\"\n\n"
        f"Port of luci-theme-noobwrt {NW_VERSION} by nooblk-98,\n"
        f"https://github.com/nooblk-98/luci-theme-noobwrt (Apache-2.0), itself derived from\n"
        f"luci-theme-argon by jerrykuku (Apache-2.0) and luci-theme-material by Lutty Yang.\n"
        f"Stylesheets, menu script, toolbar, icons, icon font and the NoobWRT logos are NoobWRT's.\n"
        f"Red Hat Display: {OFL_COPYRIGHT},\n"
        f"SIL Open Font License 1.1 (www/luci-static/{tid}/fonts/OFL.txt).\n\n"
        f"Port changes (2026, Dror Dvash): ucode templates rewritten as OpenWrt 21.02 Lua\n"
        f"templates; /etc/config/noobwrt, the settings page and the online wallpaper fetcher\n"
        f"(rpcd backend) removed; the login picture removed (unknown origin; a CSS gradient\n"
        f"instead); TypoGraphica font (all rights reserved) and Google Sans references replaced\n"
        f"by Red Hat Display; italic face, video backgrounds, PWA manifest and the timed dark mode\n"
        f"removed; toolbar shows a fixed set of 21.02 pages that exist on the router; dark.css\n"
        f"linked instead of inlined; images downscaled; reduced-motion support, 21.02 widget\n"
        f"fixes, phone fix for \"-- custom --\" dropdown entries; a row of stat cards on\n"
        f"Status > Overview drawn after NoobWRT's screenshots (written for the port).\n"))
    print(f"noobwrt: {os.path.relpath(out, ROOT)} (id {tid}, key NoobWRT21, light/dark)")
    return out
