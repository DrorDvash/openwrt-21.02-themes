#!/usr/bin/env python3
"""Turn the capture.py recording (dist/showcase/rec/) into the static playground.

  dist/showcase/site/playground/
    luci-static/                 router 0's /www/luci-static (LuCI 21.02 + all 53 themes)
    <theme>/cgi-bin/luci/...     each recorded page, links and LuCI's env pointed here
    pg-data.js                   ubus answers, menu, theme list (one file for every page)
    replay.js, picker.js         the runtime (tools/showcase/)

Every page and answer gets overlay.json (the test VM's model, kernel, CPU and container names
replaced; DHCP leases added), the session token zeroed, and the menu cut down to the recorded
pages. The build fails if the VM's identity or the test password is still in the output.

usage: build.py [--base /repo-name] [--refresh-static]
  --base: the URL path the site is served under (default: /)
"""
import argparse, glob, html, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
REC = os.path.join(ROOT, "dist/showcase/rec")
SITE = os.path.join(ROOT, "dist/showcase/site")
STATIC = os.path.join(ROOT, "dist/showcase/static")

NATIVE = {"aurora21": "Aurora", "alpha21": "Alpha", "edge21": "Edge", "noobwrt21": "NoobWRT", "uniwrt21": "UniWRT"}
NAMES = {"mission": "Mission Control", "sumie": "Sumi-e", "brutal": "Neobrutalism", "pixel": "8-bit"}
# never on the site: the test setup's names (more, e.g. the build machine's, one regex per line in
# tools/showcase/leakguard.local, not in the repository)
FORBIDDEN = [r"luci21-opt", r"luci21opt", r"testtest123", r"docker", r"/home/", r"/root/\w", r"/opt/"]
_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leakguard.local")
if os.path.exists(_local):
    FORBIDDEN += [l.strip() for l in open(_local) if l.strip() and not l.startswith("#")]


def theme_info(tid):
    if tid in NATIVE:
        return {"id": tid, "name": NATIVE[tid], "layout": "", "group": "native"}
    m = re.match(r"(.+?)21(?:-(argon|aurora))?$", tid)
    skin, layout = m.group(1), m.group(2) or "bootstrap"
    return {"id": tid, "name": NAMES.get(skin, skin.capitalize()), "layout": layout.capitalize(), "group": "reskin"}


def pull_static(sudo, refresh):
    """router 0's /www/luci-static, streamed out with tar (docker cp would leave root-owned files)"""
    if os.path.isdir(STATIC):
        if not refresh:
            return
        shutil.rmtree(STATIC)
    os.makedirs(STATIC)
    pre = sudo.split() if sudo else []
    tar = subprocess.Popen(pre + ["docker", "exec", "luci21-opt", "tar", "-C", "/www", "-cf", "-", "luci-static"],
                           stdout=subprocess.PIPE)
    subprocess.run(["tar", "-xf", "-", "-C", STATIC], stdin=tar.stdout, check=True)
    if tar.wait():
        raise SystemExit("could not read /www/luci-static from luci21-opt")


def deep_merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **{k: deep_merge(a.get(k), v) for k, v in b.items()}}
    return b


def scrub(text, replace):
    for pat, rep in replace.items():
        text = re.sub(pat, rep, text)
    return text


def prune(node, path, keep):
    """the menu with only the recorded pages (and their parents) and Logout"""
    kids = {}
    for name, child in (node.get("children") or {}).items():
        p = f"{path}/{name}".lstrip("/")
        if p in keep or any(k.startswith(p + "/") for k in keep):
            kids[name] = prune(child, p, keep)
    return {**node, "children": kids} if "children" in node else node


def js_data(v):
    return json.dumps(v, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")


def page_html(doc, tid, page, base, home):
    pg = f"{base}/playground"
    head = (f'<script>window.__pg={js_data({"base": pg, "theme": tid, "page": page, "home": home})}</script>'
            f'<script src="{pg}/pg-data.js"></script><script src="{pg}/replay.js"></script>')
    doc = re.sub(r'"sessionid":"[0-9a-f]+"', '"sessionid":"' + "0" * 32 + '"', doc)
    doc = re.sub(r'"token":"[0-9a-f]+"', '"token":"' + "0" * 32 + '"', doc)
    doc = re.sub(r'name="token" value="[0-9a-f]+"', 'name="token" value="' + "0" * 32 + '"', doc)
    doc = doc.replace("/cgi-bin/luci/admin/translations/en", f"{pg}/translations-en.js")
    doc = doc.replace('href="/"', f'href="{pg}/{tid}/cgi-bin/luci/"')   # the logo: "/" on a router, the theme here
    doc = doc.replace("\\/cgi-bin\\/luci", f"{pg}/{tid}/cgi-bin/luci".replace("/", "\\/"))
    doc = re.sub(r'(?<![\w/])/cgi-bin/luci', f"{pg}/{tid}/cgi-bin/luci", doc)
    doc = doc.replace("\\/luci-static\\/", f"{pg}/luci-static/".replace("/", "\\/"))
    doc = re.sub(r'(?<![\w/])/luci-static/', f"{pg}/luci-static/", doc)
    doc, n = re.subn(r"(<head[^>]*>)", lambda m: m.group(1) + head, doc, count=1, flags=re.I)
    if not n:
        raise SystemExit(f"{tid}: no <head> in a {page} page")
    picker = f'<script src="{pg}/picker.js"></script>'
    doc, n = re.subn(r"(</body>)", picker + r"\1", doc, count=1, flags=re.I)
    return doc if n else doc + picker


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--refresh-static", action="store_true", help="read luci-static from router 0 again")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    home = base + "/"
    overlay = json.load(open(os.path.join(HERE, "overlay.json")))
    replace = overlay["replace"]

    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("port_theme", os.path.join(os.path.dirname(HERE), "port-theme.py"))
    pt = module_from_spec(spec)
    spec.loader.exec_module(pt)
    pull_static(pt.default_sudo(), a.refresh_static)

    tids = sorted(os.path.basename(d) for d in glob.glob(os.path.join(REC, "*")) if os.path.isfile(os.path.join(d, "rpc.json")))
    if not tids:
        raise SystemExit("nothing recorded: run capture.py first")

    # one set of answers for all themes (the router's data does not depend on the theme)
    rpc, http, pages = {}, {}, set()
    for tid in tids:
        d = os.path.join(REC, tid)
        for k, v in json.load(open(os.path.join(d, "rpc.json"))).items():
            rpc.setdefault(k, v)
        for k, v in json.load(open(os.path.join(d, "http.json"))).items():
            k = re.sub(r"\?\S*", "", k)  # (cache-busting query)
            if k != "POST /cgi-bin/cgi-exec":  # (recorded before the key carried the command)
                http.setdefault(k, v)
        pages |= {os.path.relpath(os.path.dirname(f), os.path.join(d, "docs"))
                  for f in glob.glob(os.path.join(d, "docs/**/index.html"), recursive=True)}
    # the recording machine's own values (model, CPU, kernel...) are replaced wherever they appear,
    # also in server-rendered pages (Aurora prints the model): read them from the recording itself
    board, made_up = rpc.get("system.board({})", [0, {}])[-1], overlay["merge"].get("system.board({})", {})
    for k in ("model", "system", "kernel", "board_name"):
        if board.get(k) and made_up.get(k) and board[k] != made_up[k]:
            replace = {re.escape(board[k]): made_up[k], **replace}
    if board.get("release", {}).get("target") and made_up.get("release", {}).get("target"):
        replace = {re.escape(board["release"]["target"]): made_up["release"]["target"], **replace}
    for k, v in overlay["merge"].items():
        if k in rpc and isinstance(rpc[k], list) and len(rpc[k]) > 1:
            rpc[k] = [rpc[k][0], deep_merge(rpc[k][1], v)]
    rpc.update(overlay.get("set", {}))

    # Language and Style lists every theme of the playground (each router had only some installed;
    # replay.js marks the page's own theme as the current one)
    key = 'uci.get({"config":"luci"})'
    names = {}
    for tid in tids:
        v = json.load(open(os.path.join(REC, tid, "rpc.json"))).get(key, [0, {}])
        for opt, path in ((v[1] if len(v) > 1 else {}).get("values", {}).get("themes") or {}).items():
            if not opt.startswith(".") and path.replace("/luci-static/", "") in tids:
                names[opt] = path
    if key in rpc and len(rpc[key]) > 1:
        th = rpc[key][1]["values"].get("themes", {})
        rpc[key][1]["values"]["themes"] = {**{k: v for k, v in th.items() if k.startswith(".")}, **dict(sorted(names.items()))}
    http.update(overlay.get("http", {}))
    # the router itself at 192.168.1.1 (the docker bridge, there, becomes a client): the test
    # routers sit at 10.213.0.2-7 and the one recorded first answered for all
    me = rpc["luci-rpc.getNetworkDevices({})"][1]["eth0"]["ipaddrs"][0]["address"]
    replace = {re.escape(me) + r"\b": "192.168.1.@ME@", r"10\.213\.0\.1\b": "192.168.1." + me.split(".")[-1],
               **replace, r"10\.213\.0\.": "192.168.1.", "@ME@": "1"}
    rpc = json.loads(scrub(json.dumps(rpc), replace))
    hints = rpc.get("luci-rpc.getHostHints({})", [0, {}])[1]
    for mac in [m for m, h in hints.items() if "192.168.1.1" in h.get("ipaddrs", [])]:
        del hints[mac]  # the router itself, seen by its neighbour
    rpc["luci-rpc.getDHCPLeases({})"] = [0, {"dhcp6_leases": [], "dhcp_leases": [
        {"hostname": h["name"], "ipaddr": h["ipaddrs"][0], "macaddr": mac.lower(), "expires": 43200 - 2711 * i}
        for i, (mac, h) in enumerate(sorted(hints.items(), key=lambda x: x[1].get("ipaddrs", [""])[:1]))
        if h.get("name") and h.get("ipaddrs") and not h["name"].startswith("test-host")]}]
    http = json.loads(scrub(json.dumps(http), replace))  # (with the address swap above)

    menu = http.get("GET /cgi-bin/luci/admin/menu")
    if menu:
        tree = prune(json.loads(menu["body"]), "", pages | {"admin/logout"})
        menu["body"] = json.dumps(tree)
    tr = http.pop("GET /cgi-bin/luci/admin/translations/en", None)

    out = os.path.join(SITE, "playground")
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(STATIC, "luci-static"), os.path.join(out, "luci-static"))
    # absolute url(/luci-static/...) in stylesheets (Argon's loading.gif) would miss the site's base
    for f in glob.glob(os.path.join(out, "luci-static/**/*.css"), recursive=True):
        css = open(f, encoding="utf-8").read()
        fixed = re.sub(r"""(url\(\s*["']?)/luci-static/""", lambda m: m.group(1) + f"{base}/playground/luci-static/", css)
        if fixed != css:
            write(f, fixed)
    for f in ("replay.js", "picker.js"):
        shutil.copy(os.path.join(HERE, f), os.path.join(out, f))
    write(os.path.join(out, "translations-en.js"), tr["body"] if tr else "")
    themes = [theme_info(t) for t in tids]
    write(os.path.join(out, "pg-data.js"),
          f"window.__pgRPC={js_data(rpc)};\nwindow.__pgHTTP={js_data(http)};\nwindow.__pgThemes={js_data(themes)};\n")

    for tid in tids:
        d = os.path.join(REC, tid)
        dest = os.path.join(out, tid, "cgi-bin/luci")
        login = scrub(open(os.path.join(d, "login.html"), encoding="utf-8").read(), replace)
        write(os.path.join(dest, "index.html"), page_html(login, tid, "login", base, home))
        for p in pages:
            src = os.path.join(d, "docs", p, "index.html")
            if os.path.exists(src):
                doc = scrub(open(src, encoding="utf-8").read(), replace)
                write(os.path.join(dest, p, "index.html"), page_html(doc, tid, "view", base, home))
        write(os.path.join(dest, "admin/logout/index.html"),
              page_html("<!doctype html><html><head><title>Logout</title></head><body></body></html>", tid, "logout", base, home))
        # folders with no page of their own (admin/, a category): to the overview, never a listing
        for d, _, files in os.walk(dest):
            if "index.html" not in files:
                write(os.path.join(d, "index.html"),
                      f'<!doctype html><link rel="icon" href="data:,"><meta http-equiv="refresh" content="0; url={base}/playground/{tid}/cgi-bin/luci/admin/status/overview/">')
        write(os.path.join(out, tid, "index.html"),
              f'<!doctype html><link rel="icon" href="data:,"><meta http-equiv="refresh" content="0; url=cgi-bin/luci/">')

    first = "uniwrt21" if "uniwrt21" in tids else tids[0]
    write(os.path.join(out, "index.html"),
          f'<!doctype html><link rel="icon" href="data:,"><meta http-equiv="refresh" content="0; url={first}/cgi-bin/luci/"><a href="{first}/cgi-bin/luci/">Playground</a>')
    write(os.path.join(SITE, "404.html"),
          f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
          f'<title>Not in the playground</title><body style="font:16px system-ui;padding:2rem;max-width:40rem;margin:auto">'
          f'<h1>Not in the playground</h1><p>The playground has the pages of a few menu entries, recorded from a test '
          f'router. <a href="javascript:history.back()">Go back</a> or <a href="{html.escape(home)}">see all themes</a>.</p>')

    # nothing of the test VM may leave: its identity, the test password
    pw = pt.child_env("").get("LUCI_PASS") or pt.child_env("").get("ROOT_PASSWORD")
    bad = FORBIDDEN + ([re.escape(pw)] if pw else [])
    leaks = []
    for f in glob.glob(os.path.join(out, "**/*.html"), recursive=True) + [os.path.join(out, "pg-data.js")]:
        text = open(f, encoding="utf-8").read()
        leaks += [f"{os.path.relpath(f, out)}: {p}" for p in bad if re.search(p, text, re.I)]
    if leaks:
        raise SystemExit("leaks in the playground:\n  " + "\n  ".join(sorted(set(leaks))[:20]))

    size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(out, "**"), recursive=True) if os.path.isfile(f))
    print(f"playground: {len(tids)} themes x {len(pages) + 1} pages, {len(rpc)} ubus answers, "
          f"{size / 1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    main()
