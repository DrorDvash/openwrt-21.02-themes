"""Aurora baseline: the Aurora 1.4.0 frame (top bar with mega-menu, phone overlay menu).

  generate("aurora") -> luci-theme-aurora21/          Aurora itself, its own colours
  generate(theme)    -> luci-theme-THEME21-aurora/    a vistrocity theme's look on Aurora

luci-theme-aurora (eamonxg, Apache-2.0, src/luci-theme-aurora, tag v1.4.0) targets
23.05+ (ucode). Its CSS and menu script are vendored prebuilt (the Tailwind build
needs the npm registry) and only run on the 21.02 APIs they use; the three ucode
templates are translated to Lua in aurora-template/. Dropped: /etc/config/aurora
(settings app), uci token overrides, page patches, floating toolbar, PWA manifest,
the Lato web font (system font stack instead) and the same-document router.

css/theme.css (linked after Aurora's main.css or login.css):
  native:  30 aurora port layer + common 21.02 fixes, 31 aurora -> --p21-* tokens
  reskin:  20 theme content block (bootstrap top-bar rules removed), 30 port layer,
           31 --t-* -> Aurora tokens; both + 35 theme-specific fixes (kept on regeneration)
"""
import os, re, shutil
from baselines import ROOT, REF, VERSION, read, write, source_dir, title as theme_title, MAINTAINER, PKGS
from baselines.argon import filter_block, MASTER, BSVARS

SUFFIX = "-aurora"
NATIVE = "aurora"
AURORA = os.path.join(ROOT, "src/luci-theme-aurora")
TPL = os.path.join(ROOT, "tools/baselines/aurora-template")
CONTROL_TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")
COMMON = os.path.join(ROOT, "tools/baselines/common-21.02.css")
AURORA_VERSION = "1.4.0"


def custom_entry_js():
    """the phone fix for "-- custom --" dropdown entries (master: rack21's menu JS) as a plain script"""
    src = read(f"{REF}/htdocs/luci-static/resources/menu-rack21.js")
    i = src.index("\t/*\n\t * \"-- custom --\" entries")
    j = src.index("\tinitCustomEntry: function() {\n")
    k = src.index("\n\t},\n", j)
    body = src[j + len("\tinitCustomEntry: function() {\n"):k]
    doc = src[i:j].replace("\n\t", "\n").lstrip("\t")
    return (f"/* luci-theme-@ID@: generated from luci-theme-rack21's menu-rack21.js initCustomEntry() */\n"
            f"{doc}(function() {{\n'use strict';\n{body}\n}})();\n")


def generate(t, out=None, nav="mega-menu"):
    native = t == NATIVE
    tid = f"{t}21" if native else f"{t}21{SUFFIX}"
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    keep35 = os.path.join(out, "css", f"35-{t}-aurora.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None
    if native:
        title, key, mode = "Aurora", "Aurora21", "auto"
        themecolor = ('<meta name="theme-color" content="#f8fafc" media="(prefers-color-scheme: light)">\n'
                      '\t\t<meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)">')
    else:
        src = source_dir(t)
        title = theme_title(t)
        key = re.sub(r"[^A-Za-z0-9_]", "", title) + "21_aurora"
        hdr = read(f"{src}/ucode/template/themes/{t}/header.ut")
        dp = (re.search(r"const darkpref = (.+?);", hdr) or [None, ""])[1].strip()
        mode = "dark" if dp == "'true'" else "light" if dp == "'false'" else "auto"
        tc = (re.search(r'<meta name="theme-color" content="([^"]+)">', hdr) or [None, "#000000"])[1]
        themecolor = f'<meta name="theme-color" content="{tc}">'

    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)
    dropped = []
    if not native:
        mlen = len(read(MASTER).splitlines(keepends=True))
        block = "".join(read(f"{src}/htdocs/luci-static/{t}/cascade.css").splitlines(keepends=True)[mlen:])
        content, dropped = filter_block(block)
        write(f"{css}/15-bootstrap-vars.css", read(BSVARS))
        write(f"{css}/20-upstream-{t}-content.css",
              f"/* {title} override block (vistrocity/openwrt-luci-themes), content rules only;\n"
              f"   {len(dropped)} bootstrap top-bar rules removed by tools/port-theme.py --baseline aurora */\n" + content)
    write(f"{css}/30-aurora-port.css", read(f"{TPL}/30-aurora-port.css") + "\n" + read(COMMON))
    write(f"{css}/31-aurora-{'native' if native else 'tokens'}.css",
          read(f"{TPL}/31-aurora-{'native' if native else 'tokens'}.css"))
    write(f"{css}/35-{t}-aurora.css", keep35 or f"\n/* {title} on Aurora: theme-specific fixes */\n")

    # static files: Aurora's prebuilt main.css / login.css as they are, icons, the custom-entry fix
    a = f"{AURORA}/htdocs/luci-static/aurora"
    st = f"{out}/htdocs/luci-static/{tid}"
    os.makedirs(f"{st}/images")
    for f in ("main.css", "login.css"):
        shutil.copy(f"{a}/{f}", f"{st}/{f}")
    if native:
        shutil.copy(f"{a}/images/logo.svg", f"{st}/images/logo.svg")
        shutil.copy(f"{a}/images/apple-touch-icon.png", f"{st}/images/favicon.png")
    else:
        shutil.copy(f"{src}/htdocs/luci-static/{t}/logo.svg", f"{st}/images/logo.svg")
        shutil.copy(f"{src}/htdocs/luci-static/{t}/logo_48.png", f"{st}/images/favicon.png")
    subs = {"@ID@": tid, "@TITLE@": title, "@SRCID@": t, "@KEY@": key, "@VERSION@": VERSION,
            "@MODE@": mode, "@NAVTYPE@": nav, "@THEMECOLOR@": themecolor, "@FAVICON@": "favicon.png"}

    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    write(f"{st}/custom-entry.js", fill(custom_entry_js()))
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    shutil.copy(f"{AURORA}/htdocs/luci-static/resources/menu-aurora.js", f"{out}/htdocs/luci-static/resources/menu-{tid}.js")

    for n in ("header", "footer", "sysauth", "switcher"):
        write(f"{out}/luasrc/view/themes/{tid}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{CONTROL_TPL}/{n}")), 0o755)
    look = ("Aurora's own look" if native else
            f"look from luci-theme-{t}\n (vistrocity/openwrt-luci-themes, Apache-2.0)")
    write(f"{out}/CONTROL/control", (
        f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
        f"Source: https://github.com/eamonxg/luci-theme-aurora\nLicense: Apache-2.0\nSection: luci\n"
        f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
        f"Description: {title} on Aurora (21.02 port) - the Aurora top-bar layout{'' if native else ' in ' + title + ' colours'}.\n"
        f" Layout, CSS and menu script from luci-theme-aurora {AURORA_VERSION} (eamonxg, Apache-2.0),\n"
        f" {look}. Registers luci.themes.{key};\n"
        f" it does not change the active theme.\n"))
    shutil.copy(f"{AURORA}/LICENSE", f"{out}/LICENSE")
    write(f"{out}/NOTICE", (
        f"luci-theme-{tid} - \"{title} on Aurora (21.02 port)\"\n\n"
        f"Layout, main.css, login.css, menu script and template markup from luci-theme-aurora\n"
        f"{AURORA_VERSION} by eamonxg, https://github.com/eamonxg/luci-theme-aurora (Apache-2.0),\n"
        f"itself derived from luci-theme-bootstrap (OpenWrt LuCI project, Apache-2.0).\n"
        + ("" if native else
           f"Colours and content styling from luci-theme-{t} by vistrocity,\n"
           f"https://github.com/vistrocity/openwrt-luci-themes (Apache-2.0).\n")
        + f"\nPort changes (2026, Dror Dvash): ucode templates rewritten as OpenWrt 21.02 Lua\n"
        f"templates; /etc/config/aurora settings, uci token overrides, page patches, floating\n"
        f"toolbar, web manifest, Lato web font and the same-document router removed;\n"
        f"{'' if native else 'theme colours mapped onto Aurora design tokens; '}21.02 widget fixes;\n"
        f"phone fix for \"-- custom --\" dropdown entries.\n"))
    print(f"{t}: {os.path.relpath(out, ROOT)} (id {tid}, key {key}, {mode}, nav {nav}"
          f"{'' if native else f', {len(dropped)} chrome rules dropped'})")
    return out
