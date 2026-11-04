"""Layout baselines for porting vistrocity/openwrt-luci-themes to OpenWrt 21.02.

A baseline is the page frame a theme's look is put on:
  bootstrap  21.02 bootstrap (top menu)     -> luci-theme-<t>21/        id <t>21
  argon      Argon 2.3.1 (sidebar)          -> luci-theme-<t>21-argon/  id <t>21-argon
  aurora     Aurora 1.4.0 (mega-menu)       -> luci-theme-<t>21-aurora/ id <t>21-aurora
  alpha      Alpha 3.9.7 (glass sidebar)    -> luci-theme-alpha21/ only (hard-coded colours)
  edge       Edge (material sidebar)        -> luci-theme-edge21/  only (hard-coded colours)
  noobwrt    NoobWRT (Argon-fork sidebar)   -> luci-theme-noobwrt21/ only (hard-coded colours)
  uniwrt     UniWRT (controller-style rail) -> luci-theme-uniwrt21/  only (hard-coded colours)
A baseline that is a theme of its own (NATIVE, e.g. aurora) ports itself as <name>21.
Each module provides generate(theme) -> package dir, SUFFIX and optionally NATIVE.
"""
import glob, hashlib, json, os, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
THEMES = os.path.join(ROOT, "src/themes/themes")
PKGS = os.path.join(ROOT, "themes")                # the package sources, luci-theme-<id>/
REF = os.path.join(PKGS, "luci-theme-rack21")      # hand-made reference port (shared 30 layer, menu JS)
# Each package has its own version in tools/versions.json (see settle_version): a release only
# bumps the packages whose files changed. VERSION is what a package not listed there starts at.
VERSION = "1.0.7-1"
VERSIONS = os.path.join(TOOLS, "versions.json")
# the packages' Maintainer field (GitHub no-reply address: no personal mail in published files)
MAINTAINER = "Dror Dvash <DrorDvash@users.noreply.github.com>"
NAMES = ("bootstrap", "argon", "aurora", "alpha", "edge", "noobwrt", "uniwrt")


class PortError(Exception):
    """the source theme needs a hand port; args[0] is the list of problems"""


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s, mode=0o644):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    os.chmod(p, mode)


def source_dir(theme):
    return os.path.join(THEMES, f"luci-theme-{theme}")


def title(theme):
    """display name from the README's first list line ("Aquarium: ..."), else Capitalised"""
    lines = read(os.path.join(source_dir(theme), "README.md")).split("\n", 3)
    m = re.search(r"^(\w[\w -]*?):", lines[2] if len(lines) > 2 else "", re.M)
    return m.group(1) if m else theme.capitalize()


def get(name):
    if name not in NAMES:
        raise ValueError(f"unknown baseline {name!r} (have: {', '.join(NAMES)})")
    return __import__(f"baselines.{name}", fromlist=["generate"])


def theme_id(theme, baseline="bootstrap"):
    m = get(baseline)
    return theme + "21" + ("" if getattr(m, "NATIVE", None) == theme else m.SUFFIX)


def native_baseline(theme):
    """the baseline a theme *is* (aurora -> aurora), else None"""
    return next((n for n in NAMES if getattr(get(n), "NATIVE", None) == theme), None)


def package_dir(theme, baseline="bootstrap"):
    return os.path.join(PKGS, f"luci-theme-{theme_id(theme, baseline)}")


def _versions():
    return json.load(open(VERSIONS)) if os.path.exists(VERSIONS) else {}


def package_version(tid):
    """the version luci-theme-<tid> is built with"""
    return _versions().get(tid, {}).get("version", VERSION)


def fingerprint(pkgdir, ver):
    """sha256 of a package dir's files, with its version string masked (so a bump alone keeps it)"""
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(pkgdir)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, pkgdir).encode() + b"\0")
            h.update(open(p, "rb").read().replace(ver.encode(), b"@VERSION@") + b"\0")
    return h.hexdigest()


def settle_version(tid, pkgdir):
    """Call after (re)generating pkgdir at package_version(tid). If its files differ from what
    tools/versions.json recorded and that version is already in a release (public/release-*/),
    bump the release number (1.0.7-1 -> 1.0.7-2) and write the new version into the files: opkg
    skips a same-version reinstall, and ?v= busts browser caches. An unreleased version just takes
    the new files. A package seen for the first time is recorded as it is. Returns the version."""
    vs = _versions()
    rec = vs.get(tid, {})
    ver = rec.get("version", VERSION)
    fp = fingerprint(pkgdir, ver)
    if rec.get("files") == fp:
        return ver
    if rec and glob.glob(os.path.join(ROOT, "public", "release-*", f"luci-theme-{tid}_{ver}_*.ipk")):
        up, rel = ver.rsplit("-", 1)
        new = f"{up}-{int(rel) + 1}"
        for d, _, files in os.walk(pkgdir):
            for f in files:
                p = os.path.join(d, f)
                b = open(p, "rb").read()
                if ver.encode() in b:
                    with open(p, "wb") as o:
                        o.write(b.replace(ver.encode(), new.encode()))
        print(f"{tid}: files changed, version {ver} -> {new}")
        ver = new
    # the date tools/build.py stamps on the files: it changes only with them
    vs[tid] = {"version": ver, "files": fp, "date": int(time.time())}
    with open(VERSIONS, "w", newline="\n") as o:
        json.dump(dict(sorted(vs.items())), o, indent=1)
        o.write("\n")
    return ver
