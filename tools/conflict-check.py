#!/usr/bin/env python3
"""Hard rule 3: prove the .ipk only adds files under paths it owns and does not
overwrite anything that exists in the router's LuCI tree (ref bundle) or in an
installed package's file list.

usage: conflict-check.py PKG.ipk REF_TREE_DIR [OPKG_INFO_DIR]
exit 0 = clean, 1 = conflicts.
"""
import io, os, sys, tarfile

ipk, ref = sys.argv[1], sys.argv[2]
info = sys.argv[3] if len(sys.argv) > 3 else None

outer = tarfile.open(ipk, "r:gz")
data = tarfile.open(fileobj=io.BytesIO(outer.extractfile("./data.tar.gz").read()), mode="r:gz")
ctrl = tarfile.open(fileobj=io.BytesIO(outer.extractfile("./control.tar.gz").read()), mode="r:gz")
pkg = [l.split(": ", 1)[1] for l in ctrl.extractfile("./control").read().decode().splitlines()
       if l.startswith("Package: ")][0]
tid = pkg.replace("luci-theme-", "")
allowed = (f"/www/luci-static/{tid}/", f"/www/luci-static/resources/menu-{tid}.js",
           f"/usr/lib/lua/luci/view/themes/{tid}/")

bad = 0
files = [m for m in data.getmembers() if not m.isdir()]
print(f"{pkg}: {len(files)} files")
for m in files:
    path = m.name[1:] if m.name.startswith("./") else "/" + m.name
    issues = []
    if not any(path == a or path.startswith(a) for a in allowed):
        issues.append("OUTSIDE-ALLOWED-PATHS")
    if os.path.lexists(os.path.join(ref, path.lstrip("/"))):
        issues.append("EXISTS-IN-REF-TREE")
    if m.uid != 0 or m.gid != 0:
        issues.append(f"OWNER {m.uid}:{m.gid}")
    print(f"  {'OK  ' if not issues else 'FAIL'} {path} {' '.join(issues)}")
    bad += bool(issues)

# directories the package creates that the ref tree does not have must be theme-owned
for m in data.getmembers():
    if m.isdir():
        path = m.name[1:] if m.name.startswith("./") else "/" + m.name
        if path in ("", "/"):
            continue
        if not os.path.lexists(os.path.join(ref, path.lstrip("/"))) and not any(
                path.rstrip("/") + "/" == a for a in allowed if a.endswith("/")):
            print(f"  NOTE new dir {path} (not in ref tree)")

if info:
    owned = {}
    for f in os.listdir(info):
        if f.endswith(".list") and f != pkg + ".list":
            for line in open(os.path.join(info, f), errors="replace"):
                owned[line.split("\t")[0].strip()] = f[:-5]
    for m in files:
        path = m.name[1:]
        if path in owned:
            print(f"  FAIL {path} owned by installed package {owned[path]}")
            bad += 1
    print(f"checked against {len(owned)} files from installed opkg lists in {info}")

# names that the router already uses
for d in ("www/luci-static", "usr/lib/lua/luci/view/themes"):
    if os.path.lexists(os.path.join(ref, d, tid)):
        print(f"  FAIL theme id {tid} already present in ref {d}")
        bad += 1
print("RESULT:", "CLEAN" if not bad else f"{bad} CONFLICT(S)")
sys.exit(1 if bad else 0)
