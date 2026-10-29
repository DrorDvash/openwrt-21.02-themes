"""Alpha: luci-theme-alpha 3.9.7 (derisamedia, Apache-2.0, src/luci-theme-alpha) on 21.02.

  generate("alpha") -> luci-theme-alpha21/

Alpha is a dark glass restyle of Argon's page structure (sidebar, .main-left/.main-right).
Its stylesheet (gaya.css) is used as the base, its own header/footer/login templates are
translated to Lua (alpha-template/). Dropped: /etc/config/alpha and the alpha-config app
(the glass colour/blur defaults are written into the CSS), the icon dock, the background
illustrations (unknown origin; a CSS night-sky gradient replaces them), the Inter/Quicksand
web fonts (system fonts) and the 20th-anniversary image. Argon 2.3.1's icon font supplies
the glyphs gaya.css asks for (it referenced a font file Alpha never shipped).

Alpha's colours are hard-coded throughout gaya.css, so it is not a reskin baseline:
the same sidebar layout with another theme's colours is --baseline argon.
"""
import io, os, re, shutil
from baselines import ROOT, REF, VERSION, PortError, read, write, MAINTAINER, PKGS
from baselines.aurora import custom_entry_js

SUFFIX = "-alpha"
NATIVE = "alpha"
ALPHA = os.path.join(ROOT, "src/luci-theme-alpha")
ARGON = os.path.join(ROOT, "src/argon-2.3.1")
TPL = os.path.join(ROOT, "tools/baselines/alpha-template")
CONTROL_TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")
COMMON = os.path.join(ROOT, "tools/baselines/common-21.02.css")
ALPHA_VERSION = "3.9.7"
WEIGHTS = {"Thin": 100, "ExtraLight": 200, "Light": 300, "Regular": 400, "Medium": 500,
           "SemiBold": 600, "Bold": 700, "ExtraBold": 800, "Black": 900}
SYSFONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'


def base_css():
    css = read(f"{ALPHA}/luasrc/gaya/gaya.css")
    # web fonts -> system font stack (keeping the weight the font file carried)
    css = re.sub(r"@font-face\s*\{[^}]*(Inter|Quicksand)[^}]*\}\s*", "", css)
    css = re.sub(r"""font-family:\s*["']?(?:Inter|Quicksand)-(\w+)["']?\s*(;|(?=\}))""",
                 lambda m: f"font-family: {SYSFONT}; font-weight: {WEIGHTS.get(m[1], 400)}{m[2]}", css)
    css = re.sub(r"""\s*font-style:\s*["']Quicksand-\w+["'];""", "", css)   # invalid upstream declaration
    css = re.sub(r"'Inter-Regular',\s*", "system-ui, -apple-system, 'Segoe UI', Roboto, ", css)
    css = css.replace("url('/luci-static/alpha/fonts/argon.woff')", "url('../fonts/argon.woff')")
    css = css.replace("url(./icon/", "url(../gaya/icon/")
    left = re.findall(r"/luci-static/alpha|Inter-|Quicksand", css)
    if left:
        raise PortError([f"gaya.css still references {sorted(set(left))}"])
    return css


def generate(t, out=None):
    if t != NATIVE:
        raise PortError([f"Alpha's colours are hard-coded, it is not a reskin baseline: for {t} in "
                         f"this sidebar layout use --baseline argon"])
    from PIL import Image
    tid = "alpha21"
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    keep35 = os.path.join(out, "css", "35-alpha-port.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None
    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)
    write(f"{css}/base-alpha-{ALPHA_VERSION}-gaya.css",
          f"/* luci-theme-alpha {ALPHA_VERSION} gaya.css (derisamedia, Apache-2.0); web fonts and paths "
          f"adapted by tools/baselines/alpha.py */\n" + base_css())
    write(f"{css}/30-alpha-port.css", read(f"{TPL}/30-alpha-port.css") + "\n" + read(COMMON))
    write(f"{css}/35-alpha-port.css", keep35 or "\n/* Alpha on 21.02: theme-specific fixes */\n")

    st = f"{out}/htdocs/luci-static/{tid}"
    a = f"{ALPHA}/luasrc"
    os.makedirs(f"{st}/gaya/icon/sidebar-icon")
    os.makedirs(f"{st}/fonts")
    os.makedirs(f"{st}/style")
    for f in os.listdir(f"{a}/gaya/icon"):
        if f.endswith(".svg"):
            shutil.copy(f"{a}/gaya/icon/{f}", f"{st}/gaya/icon/{f}")
    for f in os.listdir(f"{a}/gaya/icon/sidebar-icon"):
        shutil.copy(f"{a}/gaya/icon/sidebar-icon/{f}", f"{st}/gaya/icon/sidebar-icon/{f}")
    shutil.copy(f"{ARGON}/htdocs/luci-static/argon/fonts/argon.woff", f"{st}/fonts/argon.woff")
    write(f"{st}/style/style.css", read(f"{a}/style/style.css"))
    logo = Image.open(f"{a}/brand.png")
    logo.thumbnail((440, 440))
    logo.quantize(64, method=Image.Quantize.FASTOCTREE).save(f"{st}/brand.png", optimize=True)
    fav = Image.open(f"{a}/favicon.ico")
    fav.thumbnail((48, 48))
    fav.save(f"{st}/favicon.png", optimize=True)
    subs = {"@ID@": tid, "@TITLE@": "Alpha", "@KEY@": "Alpha21", "@VERSION@": VERSION}

    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    write(f"{st}/custom-entry.js", fill(custom_entry_js()))
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    write(f"{out}/htdocs/luci-static/resources/menu-{tid}.js", read(f"{ALPHA}/js/menu-alpha.js"))

    for n in ("header", "footer", "sysauth"):
        write(f"{out}/luasrc/view/themes/{tid}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{CONTROL_TPL}/{n}")), 0o755)
    write(f"{out}/CONTROL/control", (
        f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
        f"Source: https://github.com/derisamedia/luci-theme-alpha\nLicense: Apache-2.0\nSection: luci\n"
        f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
        f"Description: Alpha (21.02 port) - dark glass sidebar theme.\n"
        f" Port of luci-theme-alpha {ALPHA_VERSION} (derisamedia, Apache-2.0) to OpenWrt 21.02\n"
        f" Lua templates. Registers luci.themes.Alpha21; it does not change the active theme.\n"))
    shutil.copy(f"{ALPHA}/LICENSE", f"{out}/LICENSE")
    write(f"{out}/NOTICE", (
        f"luci-theme-{tid} - \"Alpha (21.02 port)\"\n\n"
        f"Port of luci-theme-alpha {ALPHA_VERSION} by derisamedia,\n"
        f"https://github.com/derisamedia/luci-theme-alpha (Apache-2.0), itself derived from\n"
        f"luci-theme-argon by jerrykuku (Apache-2.0). gaya.css, login style.css, menu script,\n"
        f"icons and the Alpha OS logo are Alpha's; fonts/argon.woff is Argon 2.3.1's icon font.\n\n"
        f"Port changes (2026, Dror Dvash): ucode templates rewritten as OpenWrt 21.02 Lua\n"
        f"templates; /etc/config/alpha and the alpha-config dependency removed (glass colour and\n"
        f"blur defaults written into the CSS); icon dock, background illustrations, Inter/Quicksand\n"
        f"fonts, anniversary image and app.js removed; logo and favicon downscaled; CSS night-sky\n"
        f"background; reduced-motion support, 21.02 widget fixes, phone fix for \"-- custom --\"\n"
        f"dropdown entries.\n"))
    print(f"alpha: {os.path.relpath(out, ROOT)} (id {tid}, key Alpha21, dark)")
    return out
