"""Bootstrap baseline: a 21.02 port of a theme from vistrocity/openwrt-luci-themes
on the 21.02 bootstrap page frame, using the same layers as luci-theme-rack21.

  generate(theme) -> luci-theme-THEME21/

The source must follow the repo's fork layout (verified, otherwise PortError):
  cascade.css = 25.12 bootstrap cascade.css + appended override block
  mobile.css, menu-THEME.js, view/THEME/sysauth.js = unchanged 25.12 bootstrap
  header/footer/sysauth.ut = bootstrap + static HTML/JS additions only
Anything else is listed for manual review and the port is not written.
"""
import difflib, filecmp, os, re, shutil, subprocess
from baselines import ROOT, REF, VERSION, PortError, read, write, source_dir, title as theme_title, PKGS

SUFFIX = ""
MASTER = os.path.join(ROOT, "src/luci-master/themes/luci-theme-bootstrap")
B21 = os.path.join(ROOT, "src/luci-21.02/themes/luci-theme-bootstrap")
TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")


def inserted_chunks(base, theme):
    """Lines added by the theme relative to bootstrap, with the theme-file line
    index where each chunk starts."""
    a, b = base.splitlines(), theme.splitlines()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("insert", "replace"):
            out.append((j1, b[j1:j2], a[i1:i2]))
        elif op == "delete":
            out.append((j1, [], a[i1:i2]))
    return out, b


def has_ucode(lines):
    return any(re.search(r"\{\{|\{%|\{#", l) for l in lines)


def generate(t, out=None):
    src = source_dir(t)
    tid = f"{t}21"
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    problems = []
    if not os.path.isdir(src):
        raise PortError([f"no such source theme: {src}"])
    if os.path.realpath(out) == os.path.realpath(REF):
        raise PortError([f"{out} is the hand-made reference port, never regenerated"])
    # keep hand-written theme fixes across regeneration
    keep35 = os.path.join(out, "css", f"35-{t}-port.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None

    # --- 1. verify the fork layout --------------------------------------------
    mcss = read(f"{MASTER}/htdocs/luci-static/bootstrap/cascade.css").splitlines(keepends=True)
    tcss = read(f"{src}/htdocs/luci-static/{t}/cascade.css").splitlines(keepends=True)
    if tcss[2:len(mcss)] != mcss[2:]:
        problems.append("cascade.css does not start with the 25.12 bootstrap cascade.css")
    block = "".join(tcss[len(mcss):])
    for rel_t, rel_m in ((f"htdocs/luci-static/{t}/mobile.css", "htdocs/luci-static/bootstrap/mobile.css"),
                         (f"htdocs/luci-static/resources/menu-{t}.js", "htdocs/luci-static/resources/menu-bootstrap.js"),
                         (f"htdocs/luci-static/resources/view/{t}/sysauth.js", "htdocs/luci-static/resources/view/bootstrap/sysauth.js")):
        if not filecmp.cmp(f"{src}/{rel_t}", f"{MASTER}/{rel_m}", shallow=False):
            problems.append(f"{rel_t} differs from bootstrap (needs a manual port)")
    unknown = []
    for dp, _, fs in os.walk(src):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), src)
            if not re.match(rf"(README\.md|Makefile|install\.sh|root/etc/uci-defaults/.*|htdocs/luci-static/{t}/(cascade\.css|mobile\.css|logo\.svg|logo_48\.png)|"
                            rf"htdocs/luci-static/resources/menu-{t}\.js|htdocs/luci-static/resources/view/{t}/sysauth\.js|"
                            rf"ucode/template/themes/{t}/(header|footer|sysauth)\.ut)$", rel):
                unknown.append(rel)
    if unknown:
        problems.append("unexpected source files (not ported): " + ", ".join(unknown))

    # --- 2. template deltas -----------------------------------------------------
    mt, tt = f"{MASTER}/ucode/template/themes/bootstrap", f"{src}/ucode/template/themes/{t}"
    hdr_t = read(f"{tt}/header.ut")
    m = re.search(r"const darkpref = (.+?);", hdr_t)
    dp = m.group(1).strip() if m else ""
    mode = "dark" if dp == "'true'" else "light" if dp == "'false'" else "auto"
    tc = re.search(r'<meta name="theme-color" content="([^"]+)">', hdr_t)
    head_extra, header_extra = [], []
    chunks, tlines = inserted_chunks(read(f"{mt}/header.ut"), hdr_t)
    head_end = next(i for i, l in enumerate(tlines) if "</head>" in l)
    hdr_open = next((i for i, l in enumerate(tlines) if "<header>" in l), None)
    hdr_close = next((i for i, l in enumerate(tlines) if "</header>" in l), None)
    for j, added, removed in chunks:
        for k, line in enumerate(added):
            idx = j + k
            if "const darkpref" in line or 'name="theme-color"' in line:
                continue
            if has_ucode([line]):
                problems.append(f"header.ut:{idx + 1} adds template code, translate by hand: {line.strip()}")
            elif idx < head_end:
                head_extra.append(line)
            elif hdr_open is not None and hdr_open < idx < hdr_close:
                # decorative clocks are noise for screen readers
                if 'class="hdr-clock"' in line and "aria-hidden" not in line:
                    line = line.replace('class="hdr-clock"', 'class="hdr-clock" aria-hidden="true"', 1)
                header_extra.append(line)
            else:
                problems.append(f"header.ut:{idx + 1} addition outside <head>/<header>: {line.strip()}")
        for line in removed:
            s = line.strip()
            if s and not re.search(r"darkpref|mediaQuery|rootElement|setDarkMode|^</?script>$|^\{% (if \(!darkpref\)|endif) .*%\}$", s):
                problems.append(f"header.ut removes a bootstrap line: {s}")

    footer_extra = []
    chunks, tlines = inserted_chunks(read(f"{mt}/footer.ut"), read(f"{tt}/footer.ut"))
    for j, added, removed in chunks:
        for line in added:
            if re.search(r"L\.require\('menu-", line):
                continue
            if has_ucode([line]):
                problems.append(f"footer.ut adds template code, translate by hand: {line.strip()}")
            else:
                footer_extra.append(line.replace("<script>", '<script type="text/javascript">', 1))
        for line in removed:
            if line.strip() and "L.require('menu-bootstrap')" not in line:
                problems.append(f"footer.ut removes a bootstrap line: {line.strip()}")

    chunks, _ = inserted_chunks(read(f"{mt}/sysauth.ut"), read(f"{tt}/sysauth.ut"))
    for j, added, removed in chunks:
        if not all("instantiateView" in l for l in added + removed):
            problems.append("sysauth.ut has changes beyond the view name")

    if problems:
        raise PortError(problems)

    # --- 3. names ------------------------------------------------------------
    title = theme_title(t)
    key = re.sub(r"[^A-Za-z0-9_]", "", title) + "21"
    mk = read(f"{src}/Makefile")
    lt = re.search(r"LUCI_TITLE:=(.*)", mk)
    luci_title = lt.group(1).strip() if lt else f"{title} Theme"
    srcrev = subprocess.run(["git", "-C", os.path.join(ROOT, "src/themes"), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"

    # --- 4. write the port ----------------------------------------------------
    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)
    shutil.copy(f"{B21}/htdocs/luci-static/bootstrap/cascade.css", f"{css}/10-base-bootstrap-21.02.css")
    write(f"{css}/20-upstream-{t}-overrides.css", block)
    shutil.copy(f"{REF}/css/30-port-21.02.css", f"{css}/30-port-21.02.css")
    write(f"{css}/35-{t}-port.css", keep35 or f"\n/* {title}-specific 21.02 port fixes (add rules found by tools/qa.py / tools/a11y.py) */\n")
    shutil.copy(f"{B21}/htdocs/luci-static/bootstrap/mobile.css", f"{css}/mobile-base-bootstrap-21.02.css")

    st = f"{out}/htdocs/luci-static/{tid}"
    os.makedirs(st)
    for f in ("logo.svg", "logo_48.png"):
        shutil.copy(f"{src}/htdocs/luci-static/{t}/{f}", st)
    shutil.copy(f"{src}/htdocs/luci-static/{t}/logo_48.png", f"{st}/favicon.png")
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    shutil.copy(f"{REF}/htdocs/luci-static/resources/menu-rack21.js", f"{out}/htdocs/luci-static/resources/menu-{tid}.js")

    darkpref = {"dark": f'-- {title} is dark-only: always render with the bootstrap dark palette enabled\n\tlocal darkpref = "true"',
                "light": f'-- {title} is light-only\n\tlocal darkpref = "false"',
                "auto": "-- follow the browser's colour scheme\n\tlocal darkpref"}[mode]
    if tc:
        head_extra.insert(0, f'\t\t<meta name="theme-color" content="{tc.group(1)}">')
    subs = {"@TITLE@": title, "@ID@": tid, "@SRCID@": t, "@AUTHOR@": "vistrocity", "@VERSION@": VERSION,
            "@DARKPREF_LUA@": darkpref, "@KEY@": key}

    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        s = s.replace("<!--@HEAD_EXTRA@-->\n", "".join(l + "\n" for l in head_extra))
        s = s.replace("<!--@HEADER_EXTRA@-->\n", "".join(l + "\n" for l in header_extra))
        s = s.replace("<!--@FOOTER_EXTRA@-->\n", "".join(l + "\n" for l in footer_extra))
        return s

    vd = f"{out}/luasrc/view/themes/{tid}"
    for n in ("header", "footer", "sysauth"):
        write(f"{vd}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{TPL}/{n}")), 0o755)
    ctl = read(f"{REF}/CONTROL/control")
    ctl = ctl.replace("luci-theme-rack21", f"luci-theme-{tid}")
    ctl = re.sub(r"(?m)^Version: .*", f"Version: {VERSION}", ctl)
    ctl = re.sub(r"Description:.*", (
        f"Description: {title} (21.02 port) - {luci_title}.\n"
        f" Port of luci-theme-{t} (vistrocity/openwrt-luci-themes, Apache-2.0) to\n"
        f" OpenWrt 21.02 Lua templates. Registers itself in luci.themes as {key};\n"
        f" it does not change the active theme."), ctl, flags=re.S)
    write(f"{out}/CONTROL/control", ctl.rstrip("\n") + "\n")
    shutil.copy(os.path.join(ROOT, "src/themes/LICENSE"), f"{out}/LICENSE")
    notice = read(f"{REF}/NOTICE")
    notice = notice.replace("luci-theme-rack21 - \"Rack (21.02 port)\"", f"luci-theme-{tid} - \"{title} (21.02 port)\"")
    notice = notice.replace("port of luci-theme-rack (\"Rack\" theme)", f"port of luci-theme-{t} (\"{title}\" theme)")
    notice = notice.replace("themes/luci-theme-rack, commit a407f7c5ea601ef1fd6d5013fceaf287981d0346", f"themes/luci-theme-{t}, commit {srcrev}")
    notice = notice.replace("The original Rack theme", f"The original {title} theme").replace("unmodified Rack override", f"unmodified {title} override")
    notice = notice.replace("menu-rack.js rewritten as menu-rack21.js", f"menu-{t}.js rewritten as menu-{tid}.js")
    notice = notice.replace("Theme id renamed rack -> rack21", f"Theme id renamed {t} -> {tid}").replace("\n  - Port generated by tools/port-theme.sh.", "")
    notice += "  - Port generated by tools/port-theme.py (bootstrap baseline).\n"
    write(f"{out}/NOTICE", notice)

    print(f"{t}: ported to {os.path.relpath(out, ROOT)}  (id {tid}, uci key {key}, mode {mode}, "
          f"theme-color {tc.group(1) if tc else '-'}, +{len(head_extra)} head / +{len(header_extra)} header / "
          f"+{len(footer_extra)} footer lines, override block {len(block.splitlines())} lines)")
    return out
