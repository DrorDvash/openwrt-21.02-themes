#!/usr/bin/env python3
"""Record the themes on the offline test routers, for the gallery and the playground.

Per theme (installed from dist/all-ipks/ and made active in test router N):
  - docs/<path>/index.html  the server-rendered page of every entry in LuCI's menu, and
                            login.html (the sysauth page, from a context without a session)
  - rpc.json                every ubus call the pages made: "object.method(args)" -> result
  - http.json               every other same-origin request (the menu, ...): "GET /path" -> body
The first theme on each router has every page opened in the browser (to record what each view
asks for); the others only BROWSE, the rest of their pages are fetched as HTML.

build.py turns dist/showcase/rec/ into the static site. The routers hold only seeded test
data; build.py still scrubs the session token and replaces the VM's model/kernel/CPU.

usage: capture.py [--workers W | --instance N] [theme ...]   (default: every ipk in dist/all-ipks)
"""
import argparse, glob, importlib.util, json, os, re, subprocess, sys, time
from urllib.parse import parse_qs, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from qa import CHROMIUM, login, settle

spec = importlib.util.spec_from_file_location("port_theme", os.path.join(TOOLS, "port-theme.py"))
port_theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port_theme)

IPKS = os.path.join(ROOT, "dist/all-ipks")
OUT = os.path.join(ROOT, "dist/showcase/rec")

# opened in the browser for every theme (a theme's own scripts may ask for more here)
BROWSE = ["admin/status/overview", "admin/network/network"]


def themes():
    return sorted(re.sub(r"^luci-theme-(.+)_[^_]+_all\.ipk$", r"\1", os.path.basename(p))
                  for p in glob.glob(os.path.join(IPKS, "luci-theme-*.ipk")))


def stable(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def ubus_key(entry):
    if entry.get("method") == "call" and isinstance(entry.get("params"), list):
        _, obj, method, args = (entry["params"] + [None] * 4)[:4]
        return f"{obj}.{method}({stable(args or {})})"
    return f"{entry.get('method')}()"


class Recorder:
    """collects every request a page made; read() files them once the page is quiet"""

    def __init__(self, base):
        self.base, self.reqs = base, []
        self.rpc, self.http = {}, {}

    def attach(self, page):
        page.on("requestfinished", lambda r: self.reqs.append(r))

    def read(self):
        for req in self.reqs:
            u = urlsplit(req.url)
            if not req.url.startswith(self.base) or u.path.startswith("/luci-static/"):
                continue
            if req.resource_type == "document":
                continue
            try:
                resp = req.response()
                body = resp.body() if resp else None
            except Exception:
                continue
            if body is None:
                continue
            if u.path == "/ubus/" and req.method == "POST":
                sent = json.loads(req.post_data or "null")
                got = json.loads(body)
                sent = sent if isinstance(sent, list) else [sent]
                got = {r.get("id"): r for r in (got if isinstance(got, list) else [got])}
                for e in sent:
                    r = got.get(e.get("id"))
                    if r and "result" in r:
                        self.rpc.setdefault(ubus_key(e), r["result"])
            else:
                key = f"{req.method} {u.path}" + (f"?{u.query}" if u.query else "")
                if u.path == "/cgi-bin/cgi-exec":  # fs.exec_direct: the command is in the body
                    key += " " + (parse_qs(req.post_data or "").get("command") or [""])[0]
                self.http.setdefault(key, {"status": resp.status, "type": resp.headers.get("content-type", ""),
                                           "body": body.decode("utf-8", "replace")})
        self.reqs = []


def menu_paths(node, path=""):
    """every page in LuCI's menu (as the logged-in user sees it), but Logout"""
    out = []
    for name, child in sorted((node.get("children") or {}).items()):
        p = f"{path}/{name}".lstrip("/")
        if child.get("satisfied") is False or name == "logout" or not child.get("title"):
            continue  # (untitled nodes are LuCI's internals: admin/uci, admin/menu, ...)
        if "/" in p:
            out.append(p)
        out += menu_paths(child, p)
    return out


def capture(theme, n, sudo, pw, full):
    """full: open every page in the browser (records what each view asks for); otherwise only
    BROWSE does, and the other pages' HTML is fetched directly (it is all a theme changes)"""
    from playwright.sync_api import sync_playwright
    box = port_theme.Router(n, sudo)
    ipk = glob.glob(os.path.join(IPKS, f"luci-theme-{theme}_*_all.ipk"))[0]
    box.sh(f"opkg install --force-reinstall {box.copy_in(ipk)} >/dev/null")
    box.active(f"/luci-static/{theme}")

    out = os.path.join(OUT, theme)
    os.makedirs(out, exist_ok=True)
    rec = Recorder(box.url)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])

        # the login page, without a session
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        rec.attach(page)
        r = page.goto(box.url + "/cgi-bin/luci/", wait_until="networkidle")
        time.sleep(0.8)
        open(os.path.join(out, "login.html"), "w").write(r.text())
        rec.read()
        ctx.close()

        # every menu page, logged in
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        rec.attach(page)
        login(page, box.url, "root", pw)
        rec.read()
        paths = menu_paths(page.request.get(box.url + "/cgi-bin/luci/admin/menu").json())
        n_pages = 0
        for path in paths:
            if full or path in BROWSE:
                try:
                    r = page.goto(f"{box.url}/cgi-bin/luci/{path}")
                except Exception:
                    continue
                settle(page)
                time.sleep(0.6)
                status, text = r.status, r.text()
                rec.read()  # before the next navigation discards the bodies
            else:
                r = page.request.get(f"{box.url}/cgi-bin/luci/{path}")
                status, text = r.status, r.text()
            if status != 200 or "<html" not in text[:2000].lower():
                continue
            d = os.path.join(out, "docs", path)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "index.html"), "w").write(text)
            n_pages += 1
        ctx.close()
        b.close()

    json.dump(rec.rpc, open(os.path.join(out, "rpc.json"), "w"), indent=0, sort_keys=True)
    json.dump(rec.http, open(os.path.join(out, "http.json"), "w"), indent=0, sort_keys=True)
    return n_pages, len(rec.rpc), len(rec.http)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("themes", nargs="*")
    ap.add_argument("--instance", type=int)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    sudo = port_theme.default_sudo()
    env = port_theme.child_env(sudo)
    pw = os.environ.get("LUCI_PASS") or env.get("LUCI_PASS") or env.get("ROOT_PASSWORD")
    todo = a.themes or themes()

    if a.instance is None:
        # one child per test router 1..W, the themes dealt round-robin
        procs = [subprocess.Popen([sys.executable, __file__, "--instance", str(i + 1), *todo[i::a.workers]], env=env)
                 for i in range(a.workers) if todo[i::a.workers]]
        sys.exit(max(p.wait() for p in procs))

    failed = 0
    for t in todo:
        t0 = time.time()
        try:
            full = t == todo[0]   # one theme per router opens every page: the views' data
            np_, nr, nh = capture(t, a.instance, sudo, pw, full)
            print(f"{t:28s} ok  ({np_} pages, {nr} ubus, {nh} other, router {a.instance}, "
                  f"{time.time() - t0:.0f}s{', every page opened' if full else ''})", flush=True)
        except Exception as e:
            failed += 1
            print(f"{t:28s} FAIL ({type(e).__name__}: {e})", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
