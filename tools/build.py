#!/usr/bin/env python3
"""Build a theme package dir into an OpenWrt 21.02 .ipk (+ .sha256 and a plain files/ tree).

  build.py PKGDIR [--dist DIR]     default DIST: dist/ports/<id>/ (dist/ for rack21), plus a copy
                                   in dist/all-ipks/

Pure Python, so it runs the same on Linux, macOS and Windows (needs: pip install
rcssmin rjsmin). The .ipk has the layout of openwrt-21.02 scripts/ipkg-build: an
outer tar.gz of ./debian-binary, ./data.tar.gz, ./control.tar.gz; GNU tar, entries
sorted by name, root-owned, fixed mtime (SOURCE_DATE_EPOCH or the last git commit),
gzip without name/time, Installed-Size filled in.

CSS layouts:
  bootstrap  css/NN-*.css -> cascade.css; mobile-base(+mobile-port) -> mobile.css
  argon      css/base-*.css -> css/cascade.css; css/NN-*.css -> css/theme.css
             (+ css/dark.css if present)
  other      (e.g. aurora: prebuilt frame CSS in htdocs) css/NN-*.css -> css/theme.css
"""
import argparse, glob, gzip, hashlib, io, json, os, re, shutil, subprocess, sys, tarfile, time
import rcssmin, rjsmin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_IPKS = os.path.join(ROOT, "dist/all-ipks")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def cat(paths):
    return "".join(read(p) for p in paths)


def control_field(ctl, name):
    m = re.search(rf"^{name}: *(.+)$", ctl, re.M)
    return m.group(1).strip() if m else None


def stage(src):
    """{path inside the package: (bytes, mode)} for data and CONTROL"""
    ctl = read(f"{src}/CONTROL/control")
    tid = control_field(ctl, "Package").replace("luci-theme-", "")
    data, banner = {}, f"/*! {tid}: LuCI theme for OpenWrt 21.02, Apache-2.0. See NOTICE. */\n"
    put = lambda path, b, mode=0o644: data.__setitem__(path, (b if isinstance(b, bytes) else b.encode(), mode))
    mincss = lambda css: banner + rcssmin.cssmin(css) + "\n"
    static = f"www/luci-static/{tid}"
    layers = sorted(glob.glob(f"{src}/css/[0-9][0-9]-*.css"))
    if glob.glob(f"{src}/css/base-*.css"):
        put(f"{static}/css/cascade.css", mincss(cat(sorted(glob.glob(f"{src}/css/base-*.css")))))
        put(f"{static}/css/theme.css", mincss(cat(layers)))
        if os.path.exists(f"{src}/css/dark.css"):
            put(f"{static}/css/dark.css", mincss(read(f"{src}/css/dark.css")))
    elif not os.path.exists(f"{src}/css/mobile-base-bootstrap-21.02.css"):
        # vendored, prebuilt frame CSS lives in htdocs (copied as is); the layers on top
        put(f"{static}/css/theme.css", mincss(cat(layers)))
    else:
        put(f"{static}/cascade.css", mincss(cat(layers)))
        mobile = [f"{src}/css/mobile-base-bootstrap-21.02.css"] + glob.glob(f"{src}/css/mobile-port-21.02.css")
        put(f"{static}/mobile.css", mincss(cat(mobile)))
    sd = f"{src}/htdocs/luci-static/{tid}"
    for dp, _, fs in os.walk(sd):
        for f in fs:
            p = os.path.join(dp, f)
            put(f"{static}/" + os.path.relpath(p, sd).replace(os.sep, "/"), open(p, "rb").read())
    for p in sorted(glob.glob(f"{src}/htdocs/luci-static/resources/*.js")):
        js = read(p)   # vendored files that are minified already (modern syntax rjsmin does not know) stay as they are
        put(f"www/luci-static/resources/{os.path.basename(p)}", js if max(map(len, js.splitlines() or [""])) > 1000 else rjsmin.jsmin(js) + "\n")
    views = f"usr/lib/lua/luci/view/themes/{tid}"
    for p in sorted(glob.glob(f"{src}/luasrc/view/themes/{tid}/*.htm")) + [f"{src}/LICENSE", f"{src}/NOTICE"]:
        put(f"{views}/{os.path.basename(p)}", open(p, "rb").read())
    control = {}
    for p in sorted(glob.glob(f"{src}/CONTROL/*")):
        n = os.path.basename(p)
        control[n] = (open(p, "rb").read(), 0o755 if n in ("postinst", "prerm", "postrm", "preinst") else 0o644)
    return tid, ctl, data, control


def tar_gz(files, mtime, dirs=True):
    """GNU tar (gzip -n) of {path: (bytes, mode)} as ./path, directories included, sorted by name"""
    entries = set(files)
    if dirs:
        for p in files:
            parts = p.split("/")[:-1]
            entries.update("/".join(parts[:i]) + "/" for i in range(1, len(parts) + 1))
        entries.add("")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as t:
        # depth-first with names sorted per directory, like tar --sort=name
        key = lambda p: p.rstrip("/").split("/") if p else []
        for p in sorted(entries, key=key) if dirs else list(files):
            ti = tarfile.TarInfo("./" + p)
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            ti.mtime = mtime
            if p.endswith("/") or p == "":
                ti.type, ti.mode = tarfile.DIRTYPE, 0o755
                t.addfile(ti)
            else:
                b, ti.mode = files[p]
                ti.size = len(b)
                t.addfile(ti, io.BytesIO(b))
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0, compresslevel=6) as g:
        g.write(raw.getvalue())
    return out.getvalue()


def source_date(root):
    if os.environ.get("SOURCE_DATE_EPOCH"):
        return int(os.environ["SOURCE_DATE_EPOCH"])
    try:
        return int(subprocess.run(["git", "-C", root, "log", "-1", "--format=%ct"],
                                  capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError, ValueError):
        return int(time.time())


def build(src, dist=None, quiet=False):
    src = os.path.abspath(src)
    tid, ctl, data, control = stage(src)
    pkg, ver, arch = (control_field(ctl, k) for k in ("Package", "Version", "Architecture"))
    if not (pkg and ver and arch) or not ctl.endswith("\n"):
        sys.exit(f"{src}/CONTROL/control: needs Package, Version, Architecture and a final newline")
    std = os.path.join(ROOT, "dist" if tid == "rack21" else f"dist/ports/{tid}")
    dist = os.path.abspath(dist or std)
    # a listed package keeps its recorded date, so an unchanged package rebuilds to the same bytes
    vs = os.path.join(ROOT, "tools/versions.json")
    mtime = (json.load(open(vs)).get(tid, {}).get("date") if os.path.exists(vs) else None) or source_date(ROOT)
    data_gz = tar_gz(data, mtime)
    cb, mode = control["control"]
    cb = re.sub(rb"^Installed-Size: .*$", b"Installed-Size: %d" % len(data_gz), cb, flags=re.M)
    control["control"] = (cb, mode)
    control_gz = tar_gz(control, mtime)
    ipk = tar_gz({"debian-binary": (b"2.0\n", 0o644), "data.tar.gz": (data_gz, 0o644),
                  "control.tar.gz": (control_gz, 0o644)}, mtime, dirs=False)
    name = f"{pkg}_{ver}_{arch}.ipk"
    digest = hashlib.sha256(ipk).hexdigest()
    # every package's newest .ipk also goes to dist/all-ipks/ (one folder to copy to the
    # router); older versions are dropped there and next to the new one
    outs = [dist, ALL_IPKS] if dist == std else [dist]
    for d in outs:
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, f"{pkg}_*_{arch}.ipk*")):
            if os.path.basename(old) not in (name, name + ".sha256"):
                os.remove(old)
        with open(os.path.join(d, name), "wb") as f:
            f.write(ipk)
        with open(os.path.join(d, name + ".sha256"), "w", newline="\n") as f:
            f.write(f"{digest}  {name}\n")
    path = os.path.join(dist, name)
    files = os.path.join(dist, "files")
    shutil.rmtree(files, ignore_errors=True)
    for p, (b, mode) in data.items():
        dst = os.path.join(files, *p.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(b)
    if not quiet:
        print(f"built {path} ({len(ipk)} bytes)\n{digest}  {name}")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pkgdir", nargs="?", default=os.path.join(ROOT, "themes", "luci-theme-rack21"))
    ap.add_argument("--dist")
    a = ap.parse_args()
    build(a.pkgdir, a.dist)
