#!/usr/bin/env python3
"""Port a theme from vistrocity/openwrt-luci-themes to OpenWrt 21.02, build it, test it.

  port-theme.py THEME [--baseline bootstrap|argon] [--force] [--no-generate]
                      [--test | --quick | --install [--activate]] [--instance N]

  1. generate luci-theme-<id>/ on the chosen layout baseline (tools/baselines/):
       bootstrap  luci-theme-THEME21/        21.02 bootstrap frame, top menu (default)
       argon      luci-theme-THEME21-argon/  Argon 2.3.1 frame, sidebar menu
       aurora     luci-theme-THEME21-aurora/ Aurora 1.4.0 frame, top bar + mega-menu
                  (port-theme.py aurora: Aurora itself as luci-theme-aurora21)
     An existing package dir is reused as it is; --force regenerates it (its
     css/35-*.css theme fixes are kept). rack on bootstrap is the hand-made
     reference port and is never regenerated.
  2. build dist/ports/<id>/*.ipk (+ .sha256, files/) with tools/build.py
  3. file-conflict check against the router ref tree (work/ref/tree)
  4. --test, in test router N (testenv/up.sh with INSTANCE=N): install (the active
     theme must not change), activate, qa.py (layout, clipped text, console errors),
     a11y.py (contrast, focus, reduced motion, phone menu; circadian at four times
     of day), abtest.py (same flows on bootstrap and the theme, saved config must
     match), remove while active and check the fallback.
     Summary: dist/ports/<id>/TEST-SUMMARY.txt (exit 1 on any FAIL)
     --quick    install + a11y only (fast loop while tuning css/35-*.css)
     --install  only (re)install into router N, keeping its active theme;
                --activate makes the new theme the active one

env: SUDO (docker prefix; default "sudo" on Linux unless root, "" elsewhere),
     LUCI_USER / LUCI_PASS (default: testenv/test-root-password.env)
"""
import argparse, datetime, json, os, shlex, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baselines
from baselines import ROOT, PortError
from build import build

PY = sys.executable
TOOLS = os.path.join(ROOT, "tools")


def default_sudo():
    if "SUDO" in os.environ:
        return os.environ["SUDO"]
    return "sudo" if sys.platform.startswith("linux") and os.geteuid() != 0 else ""


class Router:
    """an offline OpenWrt 21.02.7 test container, published on 127.0.0.1 only"""

    def __init__(self, n, sudo):
        self.name = "luci21-opt" + (f"-{n}" if n else "")
        self.url = f"http://127.0.0.1:{18180 + n}"
        self.pre = shlex.split(sudo)

    def docker(self, *args, check=True):
        r = subprocess.run(self.pre + ["docker", *args], capture_output=True, text=True)
        if check and r.returncode:
            raise RuntimeError(f"docker {' '.join(args[:3])}: {r.stderr.strip()}")
        return r.stdout.strip()

    def sh(self, cmd, check=True):
        return self.docker("exec", self.name, "sh", "-c", cmd, check=check)

    def copy_in(self, path):
        # into /root: the container's /tmp is a tmpfs that docker cp cannot write to
        self.docker("cp", path, f"{self.name}:/root/")
        return "/root/" + os.path.basename(path)

    def active(self, value=None):
        if value:
            self.sh(f"uci set luci.main.mediaurlbase={value} && uci commit luci")
        return self.sh("uci get luci.main.mediaurlbase")


def child_env(sudo):
    env = dict(os.environ, SUDO=sudo)
    f = os.path.join(ROOT, "testenv/test-root-password.env")
    if os.path.exists(f) and "LUCI_PASS" not in env:
        for line in open(f, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v.strip("'\"")
    return env


def tz_at(hour):
    """an Etc/GMT zone in which the local time is now about `hour` o'clock"""
    off = (hour - datetime.datetime.now(datetime.timezone.utc).hour + 24) % 24
    off = off - 24 if off > 12 else off
    return f"Etc/GMT-{off}" if off >= 0 else f"Etc/GMT+{-off}"


def read_all(d):
    return "".join(open(os.path.join(d, f), encoding="utf-8").read() for f in os.listdir(d) if f.endswith(".htm"))


def run_tool(env, log, *args):
    with open(log, "w") as f:
        return subprocess.run([PY, "-I", *args], stdout=f, stderr=subprocess.STDOUT, env=env).returncode == 0


def qa_lines(report):
    r = json.load(open(report))
    res = [x for x in r["results"] if x.get("checks")]
    bad = [f"{x['page']}@{x['vp']}" for x in res
           if x["checks"]["pageOverflowX"] > 0 or x["checks"]["offscreen"] or x["checks"].get("clipped")
           or x["checks"].get("invisible")]
    out = [f"layout + clipped text ({len(r['results'])} page/viewport shots): {'PASS' if not bad else 'FAIL ' + ', '.join(bad)}"]
    out += [f"    clipped: {c}" for c in sorted({c for x in res for c in x["checks"].get("clipped", [])})[:8]]
    out += [f"    invisible text: {c}" for c in sorted({c for x in res for c in x["checks"].get("invisible", [])})[:8]]
    fl = sorted({f"{x['page']}@{x['vp']}: {f}" for x in res for f in x["checks"].get("floating", [])})
    out.append(f"opaque menus, dialogs and open lists: {'PASS' if not fl else 'FAIL'}")
    out += [f"    see-through: {f}" for f in fl[:6]]
    ls = sorted({f"{x['page']}@{x['vp']}: {f}" for x in res for f in x["checks"].get("list", [])})
    out.append(f"open lists shown whole, page stays put: {'PASS' if not ls else 'FAIL'}")
    out += [f"    {f}" for f in ls[:6]]
    ce = [c for c in r["console"] if "403" not in c["text"]]   # the login page itself answers 403
    out.append(f"console errors from the theme: {'PASS (0)' if not ce else 'FAIL ' + str(ce[:3])}")
    return out


def contrast_fails(r):
    seen = {}
    for page, v in r["contrast"].items():
        for f in v["fails"]:
            seen.setdefault((f["sel"], f["color"], f["bg"]), (f, page))
    return seen


def a11y_lines(report):
    r = json.load(open(report))
    b = r["burger"]
    ok_menu = (b["navigated_to"].endswith("/firewall") and b["expanded_items"]
               and all(i["inView"] for i in b["expanded_items"]))
    rm = r["reduced_motion"]
    out = [f"phone menu: {'PASS' if ok_menu else 'FAIL'}",
           f"keyboard focus ring: {r['focus']['outline']}",
           f"reduced motion: {'PASS' if rm['brandLed'] == 'none' and rm['buttonTransition'] == '0s' else 'FAIL ' + str(rm)}"]
    fails = contrast_fails(r)
    worst = min(v["min"] for v in r["contrast"].values())
    out.append(f"WCAG AA contrast: {'PASS (worst ' + str(worst) + ':1)' if not fails else 'FAIL on ' + str(len({p for _, p in fails.values()})) + ' pages'}")
    for f, page in fails.values():
        out.append(f"    {f['ratio']}:1 {f['sel'][:40]} {f['color']} on {f['bg']} '{f['text'][:24]}' ({page.split('/')[-1]})")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("\n", 2)[2])
    ap.add_argument("theme")
    ap.add_argument("--baseline", "--theme-baseline", choices=baselines.NAMES,
                    help="layout frame (default: bootstrap; for a baseline's own theme, e.g. aurora, that baseline)")
    ap.add_argument("--force", action="store_true", help="regenerate an existing package dir")
    ap.add_argument("--no-generate", action="store_true", help="build/test the package dir as it is")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--test", action="store_true")
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--install", action="store_true")
    ap.add_argument("--activate", action="store_true", help="with --install: make it the active theme")
    ap.add_argument("--instance", type=int, default=int(os.environ.get("INSTANCE", 0)),
                    help="test router number (0 = luci21-opt on :18180, N = luci21-opt-N on :18180+N)")
    a = ap.parse_args()

    t = a.theme
    base = a.baseline or baselines.native_baseline(t) or "bootstrap"
    tid = baselines.theme_id(t, base)
    pkgdir = baselines.package_dir(t, base)
    hand_port = os.path.realpath(pkgdir) == os.path.realpath(baselines.REF)
    out = os.path.join(ROOT, "dist" if hand_port else f"dist/ports/{tid}")

    # 1. generate
    if not os.path.isdir(os.path.join(ROOT, "src/themes")):
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        "https://github.com/vistrocity/openwrt-luci-themes.git", os.path.join(ROOT, "src/themes")], check=True)
    if not (hand_port or a.no_generate or a.quick or a.install) and (a.force or not os.path.isdir(pkgdir)):
        try:
            mod = baselines.get(base)
            # regenerate at the recorded version (see below), in every baseline module the port uses
            for m in [m for n, m in sys.modules.items() if n.startswith("baselines.")]:
                if hasattr(m, "VERSION"):
                    m.VERSION = baselines.package_version(tid)
            mod.generate(t)
        except PortError as e:
            print(f"{t}: NOT PORTED on {base}, manual review needed:")
            for p in e.args[0]:
                print("  -", p)
            sys.exit(2)
    elif not os.path.isdir(pkgdir):
        sys.exit(f"{pkgdir} does not exist")

    # its own version: bumped only when its files changed since tools/versions.json recorded them
    if not (a.quick or a.install):
        baselines.settle_version(tid, pkgdir)

    # 2. build, 3. conflict check
    ipk = build(pkgdir, out)
    cc = subprocess.run([PY, "-I", f"{TOOLS}/conflict-check.py", ipk, os.path.join(ROOT, "work/ref/tree")],
                        capture_output=True, text=True).stdout.strip().splitlines()
    conflict = cc[-1] if cc else "conflict check did not run"
    print(conflict)

    sudo = default_sudo()
    box = Router(a.instance, sudo)
    if a.install:
        prev = box.active()
        box.sh(f"opkg install --force-reinstall {box.copy_in(ipk)} >/dev/null")
        now = box.active(f"/luci-static/{tid}" if a.activate else prev)   # reinstall resets an active theme
        box.sh("rm -rf /tmp/luci-*")
        print(f"installed {os.path.basename(ipk)} in {box.name} ({box.url}), active theme {now}")
        return
    if not (a.test or a.quick):
        return

    # 4. tests
    env = child_env(sudo)
    shots = os.path.join(out, "screenshots", tid) if hand_port else os.path.join(out, "screenshots")
    summary = os.path.join(out, ".quick-summary.txt" if a.quick else
                           ("screenshots/TEST-SUMMARY.txt" if hand_port else "TEST-SUMMARY.txt"))
    os.makedirs(shots, exist_ok=True)
    key = next(l.split("luci.themes.", 1)[1].split("=")[0] for l in open(f"{pkgdir}/CONTROL/postinst")
               if l.startswith("uci set luci.themes."))
    lines = []

    def say(*ls):
        for l in ls:
            print(l, flush=True)
            lines.append(l)

    size = os.path.getsize(ipk)
    say(f"== {tid}  ({datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}, container {box.name}, baseline {base})",
        f"package: {os.path.basename(ipk)} {size} bytes, sha256 {open(ipk + '.sha256').read()[:16]}...",
        f"conflict check: {conflict}")
    remote = box.copy_in(ipk)
    prev = box.active()
    box.active("/luci-static/bootstrap")   # reinstalling an *active* theme legitimately resets it
    box.sh(f"opkg install --force-reinstall {remote} >/dev/null")
    now = box.active()
    say(f"install: active theme unchanged ({now}) PASS" if now == "/luci-static/bootstrap" else f"install: active theme changed to {now} FAIL")
    box.active(f"/luci-static/{tid}")

    if not a.quick:
        if run_tool(env, f"{out}/.qa.log", f"{TOOLS}/qa.py", "--url", box.url, "--label", tid, "--out", shots):
            say(*qa_lines(f"{shots}/report.json"))
        else:
            say("qa.py crashed FAIL")
    if run_tool(env, f"{out}/.a11y.log", f"{TOOLS}/a11y.py", "--url", box.url, "--out", f"{shots}/a11y"):
        say(*a11y_lines(f"{shots}/a11y/a11y.json"))
    else:
        say("a11y.py crashed FAIL")
    views = os.path.join(pkgdir, "luasrc/view/themes", tid)
    follows_device = any(m in read_all(views) for m in ('local mode = "auto"', "follow the browser's colour scheme"))
    if follows_device:
        # the palette follows prefers-color-scheme: the run above was light, check dark too
        if run_tool(env, f"{out}/.a11y-dark.log", f"{TOOLS}/a11y.py", "--url", box.url,
                    "--color-scheme", "dark", "--out", f"{shots}/a11y-dark"):
            r = json.load(open(f"{shots}/a11y-dark/a11y.json"))
            n = len(contrast_fails(r))
            say("WCAG AA contrast (dark palette): " + ("PASS (worst " + str(min(v["min"] for v in r["contrast"].values())) + ":1)" if not n else f"FAIL ({n} distinct)"),
                *[f"    {f['ratio']}:1 {f['sel'][:40]} {f['color']} on {f['bg']} '{f['text'][:24]}' ({p.split('/')[-1]})"
                  for f, p in contrast_fails(r).values()])
        else:
            say("a11y.py (dark) crashed FAIL")
    if t == "circadian":
        # the palette follows the browser clock: check dawn/dusk/night too (day ran above)
        for tod, hour in (("dawn", 7), ("dusk", 18), ("night", 23)):
            if not run_tool(env, f"{out}/.a11y-{tod}.log", f"{TOOLS}/a11y.py", "--url", box.url,
                            "--timezone", tz_at(hour), "--out", f"{shots}/a11y-{tod}"):
                say(f"a11y.py ({tod}) crashed FAIL")
                continue
            n = len(contrast_fails(json.load(open(f"{shots}/a11y-{tod}/a11y.json"))))
            say(f"WCAG AA contrast ({tod} palette): " + ("PASS" if not n else f"FAIL ({n} distinct)"))
    if not a.quick:
        log = f"{out}/.abtest.log"
        if run_tool(env, log, f"{TOOLS}/abtest.py", "--url", box.url, "--container", box.name,
                    "--theme", f"/luci-static/{tid}", "--out", f"{shots}/abtest"):
            better = sum("B better" in l for l in open(log))
            say(f"functional A/B vs bootstrap: PASS (same saved config; phone custom entry: {better} improvements)")
        else:
            say(f"functional A/B vs bootstrap: FAIL (see {log})",
                *[l.rstrip() for l in open(log) if any(w in l for w in ("DIFF", "ERROR", "only", "console"))][:8])

    box.sh(f"opkg remove luci-theme-{tid} >/dev/null")
    act, entry = box.active(), box.sh(f"uci -q get luci.themes.{key} || echo gone", check=False)
    say("remove while active: fallback bootstrap, entry gone PASS" if act == "/luci-static/bootstrap" and entry == "gone"
        else f"remove: active={act} entry={entry} FAIL")
    left = box.sh(f"ls -d /www/luci-static/{tid} /usr/lib/lua/luci/view/themes/{tid} "
                  f"/www/luci-static/resources/menu-{tid}.js 2>/dev/null", check=False)
    say("leftover files: none PASS" if not left else f"leftover files FAIL: {left}")
    box.active("/luci-static/bootstrap" if prev == f"/luci-static/{tid}" else prev)

    with open(summary, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(1 if any("FAIL" in l for l in lines) else 0)


if __name__ == "__main__":
    main()
