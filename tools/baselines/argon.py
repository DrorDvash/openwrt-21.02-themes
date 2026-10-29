"""Argon baseline: a theme's look in the Argon 2.3.1 sidebar layout.

  generate(theme) -> luci-theme-THEME21-argon/

Layout and chrome come from luci-theme-argon 2.3.1 (jerrykuku, Apache-2.0; the
version GL ships on 21.02 firmware, src/argon-2.3.1). The look comes from the
theme's upstream override block (vistrocity/openwrt-luci-themes), filtered to
its *content* rules (sections, tables, forms, buttons, page background): its
chrome rules target bootstrap's top bar and are replaced by
argon-template/30-argon-port.css, which maps Argon's variables and
sidebar/header onto the theme's --t-* tokens. Argon's own settings
(/etc/config/argon), dark.css and online wallpapers are not used.

css/base-argon-2.3.1.css -> css/cascade.css (argon, font faces trimmed); then
css/theme.css = 20 theme content block + 30 argon port layer + 35 theme-specific
fixes (kept on regeneration), linked after Argon's styles.
"""
import os, re, shutil
from baselines import ROOT, REF, VERSION, read, write, source_dir, title as theme_title, MAINTAINER, PKGS

SUFFIX = "-argon"
ARGON = os.path.join(ROOT, "src/argon-2.3.1")
MASTER = os.path.join(ROOT, "src/luci-master/themes/luci-theme-bootstrap/htdocs/luci-static/bootstrap/cascade.css")
TPL = os.path.join(ROOT, "tools/baselines/argon-template")
CONTROL_TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")
COMMON = os.path.join(ROOT, "tools/baselines/common-21.02.css")   # theme-independent 21.02 fixes
BSVARS = os.path.join(ROOT, "tools/baselines/bootstrap-vars-21.02.css")   # colours the theme blocks derive

# selectors that only exist in bootstrap's page frame (top bar, menu, footer)
CHROME = re.compile(r"^\s*(header\b|\.nav\b|\.brand\b|\.hdr-clock|footer\b|#topmenu|#modemenu|#indicators|"
                    r"\.dropdown-menu|li\.menu|\.pull-right|\.breadcrumb|\.container\b)")


def filter_block(css):
    """drop rules whose selectors are all bootstrap-chrome; keep everything else verbatim"""
    out, i, n = [], 0, len(css)
    dropped = []
    while i < n:
        j = css.find("{", i)
        if j < 0:
            out.append(css[i:]); break
        head = css[i:j]
        # find the matching close brace
        depth, k = 1, j + 1
        while k < n and depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0); k += 1
        body = css[j + 1:k - 1]
        sel = re.sub(r"/\*.*?\*/", "", head, flags=re.S).strip()
        if sel.startswith("@media") or sel.startswith("@supports"):
            inner, d = filter_block(body)
            dropped += d
            if inner.strip():
                out.append(f"{head}{{{inner}}}")
        elif sel.startswith("@") or not sel:
            out.append(css[i:k])
        else:
            sels = [s.strip() for s in sel.split(",")]
            keep = [s for s in sels if not CHROME.match(s)]
            if keep:
                comment = head[:len(head) - len(head.lstrip())]
                out.append(f"{comment}{', '.join(keep)} {{{body}}}")
            else:
                dropped.append(sel.replace("\n", " ")[:60])
        i = k
    return "".join(out), dropped


def generate(t, out=None, skin=None):
    """skin: a theme of its own on the Argon frame (see edge.py) instead of a vistrocity
    theme: dict with id, title, key, dark, themecolor, content (20 layer), port (30 layer),
    logo_svg and favicon (paths), control/notice texts"""
    tid = skin["id"] if skin else f"{t}21{SUFFIX}"
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    keep35 = os.path.join(out, "css", f"35-{t}-{'port' if skin else 'argon'}.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None

    if skin:
        title, key, dark, tc = skin["title"], skin["key"], skin["dark"], skin["themecolor"]
    else:
        src = source_dir(t)
        title = theme_title(t)
        key = re.sub(r"[^A-Za-z0-9_]", "", title) + "21_argon"
        hdr = read(f"{src}/ucode/template/themes/{t}/header.ut")
        dark = "'true'" in (re.search(r"const darkpref = (.+?);", hdr) or [None, ""])[1]
        tc = (re.search(r'<meta name="theme-color" content="([^"]+)">', hdr) or [None, "#000000"])[1]

    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)

    # 10: argon cascade with only the woff icon font (no TypoGraphica, no legacy formats)
    ac = read(f"{ARGON}/htdocs/luci-static/argon/css/cascade.css")
    def fontface(mm):
        b = mm.group(0)
        if "TypoGraphica" in b:
            return ""
        if "font-family:'argon'" not in b.replace(" ", ""):
            return b                    # e.g. the embedded (data: URI) Google Sans face: keep as is
        return re.sub(r"src:[^;}]*(;src:[^;}]*)*", "src:url('../fonts/argon.woff?u6kthm') format('woff')", b)
    ac = re.sub(r"@font-face\s*\{[^}]*\}", fontface, ac)
    write(f"{css}/base-argon-2.3.1.css", ac)
    # Argon's dark.css is not used: it hard-codes greys (many !important); the theme's own
    # tokens provide the dark look on top of Argon's variable-driven light base.

    dropped = []
    if skin:
        write(f"{css}/20-{t}.css", skin["content"])
        write(f"{css}/30-{t}-port.css", skin["port"] + "\n" + read(COMMON))
        write(f"{css}/35-{t}-port.css", keep35 or f"\n/* {title} on 21.02: theme-specific fixes */\n")
        if skin.get("dark_css"):
            write(f"{css}/dark.css", skin["dark_css"])   # linked by the header (dark-head.htm), not in cascade
    else:
        # 15: bootstrap's derived colours (the blocks set only their inputs); 20: the theme's content rules
        write(f"{css}/15-bootstrap-vars.css", read(BSVARS))
        mlen = len(read(MASTER).splitlines(keepends=True))
        block = "".join(read(f"{src}/htdocs/luci-static/{t}/cascade.css").splitlines(keepends=True)[mlen:])
        content, dropped = filter_block(block)
        write(f"{css}/20-upstream-{t}-content.css",
              f"/* {title} override block (vistrocity/openwrt-luci-themes), content rules only;\n"
              f"   {len(dropped)} bootstrap top-bar rules removed by tools/port-theme.py --baseline argon */\n" + content)
        write(f"{css}/30-argon-port.css", read(f"{TPL}/30-argon-port.css") + "\n" + read(COMMON))
        write(f"{css}/35-{t}-argon.css", keep35 or f"\n/* {title} on Argon: theme-specific fixes */\n")

    # static assets
    st = f"{out}/htdocs/luci-static/{tid}"
    for sub, files in (("fonts", ["argon.woff"]), ("js", ["jquery.min.js"]),
                       ("icon", ["favicon-32x32.png", "apple-icon-144x144.png", "android-icon-192x192.png", "arrow.svg"]),
                       ("img", ["blank.png"])):
        os.makedirs(f"{st}/{sub}", exist_ok=True)
        for f in files:
            shutil.copy(f"{ARGON}/htdocs/luci-static/argon/{sub}/{f}", f"{st}/{sub}/{f}")
    shutil.copy(skin["logo_svg"] if skin else f"{src}/htdocs/luci-static/{t}/logo.svg", f"{st}/logo.svg")
    shutil.copy(skin["favicon"] if skin else f"{src}/htdocs/luci-static/{t}/logo_48.png", f"{st}/favicon.png")

    # JS: argon menu + the shared phone fix for "-- custom --" entries
    menu = read(f"{ARGON}/htdocs/luci-static/resources/menu-argon.js")
    fix = read(f"{REF}/htdocs/luci-static/resources/menu-rack21.js")
    fn = fix[fix.index("\t/*\n\t * \"-- custom --\" entries"):fix.index("\trender: function(tree)")]
    menu = menu.replace("ui.menu.load().then(L.bind(this.render, this));",
                        "ui.menu.load().then(L.bind(this.render, this));\n\t\tthis.initCustomEntry();", 1)
    assert "this.initCustomEntry();" in menu, "menu-argon.js __init__ not found"
    menu = menu.replace("return baseclass.extend({", "return baseclass.extend({\n" + fn, 1)
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    write(f"{out}/htdocs/luci-static/resources/menu-{tid}.js", menu)

    # templates
    # (the dark parts come first: they hold @ID@ and @VERSION@ themselves)
    subs = {"@DARKHEAD@": "", "@DARKBUTTON@": "", "@ID@": tid, "@TITLE@": title, "@SRCID@": t, "@KEY@": key,
            "@VERSION@": VERSION, "@MODE@": "dark" if dark else "normal", "@THEMECOLOR@": tc}
    if skin and skin.get("dark_css"):
        subs["@DARKHEAD@"], subs["@DARKBUTTON@"] = read(f"{TPL}/dark-head.htm"), read(f"{TPL}/dark-button.htm")
    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    for n in ("header", "footer", "header_login", "footer_login", "out_header_login", "sysauth"):
        write(f"{out}/luasrc/view/themes/{tid}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{CONTROL_TPL}/{n}")), 0o755)
    if skin:
        write(f"{out}/CONTROL/control", skin["control"])
        shutil.copy(f"{ARGON}/LICENSE", f"{out}/LICENSE")
        write(f"{out}/NOTICE", skin["notice"])
        print(f"{t}: {os.path.relpath(out, ROOT)} (id {tid}, key {key}, {'dark' if dark else 'light'}, Argon frame)")
        return out
    write(f"{out}/CONTROL/control", (
        f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
        f"Source: https://github.com/vistrocity/openwrt-luci-themes\nLicense: Apache-2.0\nSection: luci\n"
        f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
        f"Description: {title} on Argon (21.02 port) - the {title} look in the Argon sidebar layout.\n"
        f" Layout from luci-theme-argon 2.3.1 (jerrykuku, Apache-2.0), look from luci-theme-{t}\n"
        f" (vistrocity/openwrt-luci-themes, Apache-2.0). Registers luci.themes.{key};\n"
        f" it does not change the active theme.\n"))
    shutil.copy(f"{ARGON}/LICENSE", f"{out}/LICENSE")
    write(f"{out}/NOTICE", (
        f"luci-theme-{tid} - \"{title} on Argon (21.02 port)\"\n\n"
        f"Layout, templates, menu script, icon font and jQuery copy from luci-theme-argon 2.3.1\n"
        f"by jerrykuku, https://github.com/jerrykuku/luci-theme-argon (Apache-2.0).\n"
        f"Colours and content styling from luci-theme-{t} by vistrocity,\n"
        f"https://github.com/vistrocity/openwrt-luci-themes (Apache-2.0), itself a fork of\n"
        f"luci-theme-bootstrap (OpenWrt LuCI project, Apache-2.0).\n\n"
        f"Port changes (2026, Dror Dvash): Argon's online wallpapers, /etc/config/argon\n"
        f"settings, background photos, TypoGraphica font and legacy font formats removed;\n"
        f"theme colours mapped onto Argon; phone fix for \"-- custom --\" dropdown entries.\n"))
    print(f"{t}: {os.path.relpath(out, ROOT)} (id {tid}, key {key}, {'dark' if dark else 'light'}, "
          f"{len(dropped)} chrome rules dropped)")
    return out
