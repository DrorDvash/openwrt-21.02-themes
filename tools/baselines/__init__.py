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
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, "tools")
THEMES = os.path.join(ROOT, "src/themes/themes")
PKGS = os.path.join(ROOT, "themes")                # the package sources, luci-theme-<id>/
REF = os.path.join(PKGS, "luci-theme-rack21")      # hand-made reference port (shared 30 layer, menu JS)
VERSION = "1.0.6-1"   # bump on every release: opkg skips a same-version reinstall and ?v= busts browser caches
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
