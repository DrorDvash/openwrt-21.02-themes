#!/usr/bin/env python3
"""The gallery page (dist/showcase/site/index.html), photographed from the built playground.

Per theme: Status > Overview on a 1440x900 desktop and a 390x844 phone, light and dark (dark only
when the theme changes with the browser's colour scheme), and the login page. Each pair is put on
a monitor and a phone (drawn in CSS) and saved as WebP under site/img/.

usage: gallery.py [--base /repo-name] [--repo owner/name] [--shots-only | --page-only] [theme ...]
"""
import argparse, functools, glob, html, http.server, io, json, os, socketserver, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from qa import CHROMIUM
from build import SITE, theme_info

SHOTS = os.path.join(os.path.dirname(SITE), "shots")
IMG = os.path.join(SITE, "img")

UPSTREAM = {
    "aurora21": ("eamonxg", "https://github.com/eamonxg/luci-theme-aurora"),
    "alpha21": ("derisamedia", "https://github.com/derisamedia/luci-theme-alpha"),
    "edge21": ("kiddin9 and GaryPang", "https://github.com/kiddin9/luci-theme-edge"),
    "noobwrt21": ("nooblk-98", "https://github.com/nooblk-98/luci-theme-noobwrt"),
    "uniwrt21": ("ox1d3x3", "https://github.com/ox1d3x3/uniwrt-luci"),
}
RESKINS = ("vistrocity", "https://github.com/vistrocity/openwrt-luci-themes")
LAYOUTS = {
    "Bootstrap": ("OpenWrt LuCI", "https://github.com/openwrt/luci"),
    "Argon": ("jerrykuku", "https://github.com/jerrykuku/luci-theme-argon"),
    "Aurora": ("eamonxg", "https://github.com/eamonxg/luci-theme-aurora"),
}
SKIN_NOTES = {
    "Rack": "the shared base of the reskins: a server-rack look",
}

FRAME = """<!doctype html><html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; }
body { width: 1920px; height: 1080px; overflow: hidden; position: relative; background: %(bg)s; }
.monitor { position: absolute; left: 80px; top: 76px; width: 1320px; }
.bezel { background: #0e0f12; border-radius: 26px; padding: 20px; border: 1px solid #2b2e35;
         box-shadow: 0 60px 120px rgba(0,0,0,.42), 0 0 0 2px #1a1c21 inset; }
.screen { width: 1280px; height: 800px; border-radius: 6px; overflow: hidden; background: #000; }
.screen img { width: 100%%; display: block; }
.chin { height: 38px; margin: 0 2px; background: linear-gradient(#2a2d33, #1b1d22); border-radius: 0 0 20px 20px; }
.neck { width: 190px; height: 70px; margin: 0 auto; background: linear-gradient(90deg, #1d1f24, #3a3d44 50%%, #1d1f24);
        clip-path: polygon(14%% 0, 86%% 0, 100%% 100%%, 0 100%%); }
.foot { width: 420px; height: 14px; margin: 0 auto; border-radius: 8px 8px 4px 4px;
        background: linear-gradient(#3a3d44, #1d1f24); box-shadow: 0 18px 40px rgba(0,0,0,.3); }
.phone { position: absolute; left: 1388px; top: 270px; width: 360px; height: 760px; border-radius: 60px; padding: 14px;
         background: #0d0e11; border: 2px solid #3a3d44; box-shadow: 0 40px 100px rgba(0,0,0,.5), 0 0 0 7px #1b1d22; }
.phone .scr { width: 100%%; height: 100%%; border-radius: 46px; overflow: hidden; position: relative; background: #000; padding-top: 52px; }
.phone .scr img { width: 100%%; display: block; }
.island { position: absolute; top: 12px; left: 50%%; transform: translateX(-50%%); width: 110px; height: 32px;
          border-radius: 20px; background: #000; z-index: 2; }
</style></head><body>
<div class="monitor"><div class="bezel"><div class="screen"><img src="%(desk)s"></div></div>
  <div class="chin"></div><div class="neck"></div><div class="foot"></div></div>
<div class="phone"><div class="scr"><div class="island"></div><img src="%(phone)s"></div></div>
</body></html>"""

BG = {
    "light": "radial-gradient(1200px 700px at 80% 10%, #dbe7ff 0%, transparent 60%), "
             "radial-gradient(900px 600px at 5% 95%, #efe3ff 0%, transparent 60%), #eef0f5",
    "dark": "radial-gradient(1200px 700px at 80% 10%, #1d3b6e 0%, transparent 60%), "
            "radial-gradient(900px 600px at 5% 95%, #3a1d5e 0%, transparent 60%), #0b0d12",
}

VIEW = {
    "desk": dict(viewport={"width": 1440, "height": 900}),
    "phone": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2),
}


class Quiet(http.server.SimpleHTTPRequestHandler):
    base = ""

    def translate_path(self, path):
        if self.base and path.startswith(self.base + "/"):
            path = path[len(self.base):]
        return super().translate_path(path)

    def log_message(self, *a):
        pass


def serve(base):
    """the site on 127.0.0.1, under the URL path it was built for"""
    handler = type("Handler", (Quiet,), {"base": base})
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(handler, directory=SITE))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}{base}"


def shoot(browser, url, tid):
    """overview (desk, phone) x (light, dark) + login; returns whether dark differs from light"""
    from PIL import Image, ImageChops
    out = os.path.join(SHOTS, tid)
    os.makedirs(out, exist_ok=True)
    pg = f"{url}/playground/{tid}/cgi-bin/luci/"
    hide = "#pg-picker { display: none !important; }"
    for scheme in ("light", "dark"):
        for name, opts in VIEW.items():
            ctx = browser.new_context(color_scheme=scheme, **opts)
            ctx.add_init_script("try { sessionStorage.setItem('pg-auth', '1'); } catch (e) {}")
            page = ctx.new_page()
            page.goto(pg + "admin/status/overview/", wait_until="networkidle")
            page.add_style_tag(content=hide)
            time.sleep(2.5)
            page.screenshot(path=os.path.join(out, f"{name}-{scheme}.png"), animations="disabled")
            ctx.close()
    ctx = browser.new_context(**VIEW["desk"])
    page = ctx.new_page()
    page.goto(pg, wait_until="networkidle")
    page.add_style_tag(content=hide)
    time.sleep(1.5)
    page.screenshot(path=os.path.join(out, "login.png"), animations="disabled")
    ctx.close()
    a, b = (Image.open(os.path.join(out, f"desk-{s}.png")).convert("L") for s in ("light", "dark"))
    diff = ImageChops.difference(a, b).point(lambda v: 255 if v > 40 else 0)
    return sum(diff.histogram()[255:]) / (a.width * a.height) > 0.05


def compose(browser, tid, modes):
    from PIL import Image
    import base64
    uri = lambda p: "data:image/png;base64," + base64.b64encode(open(p, "rb").read()).decode()
    src = os.path.join(SHOTS, tid)
    os.makedirs(IMG, exist_ok=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    for mode in modes:
        page.set_content(FRAME % {"bg": BG[mode], "desk": uri(f"{src}/desk-{mode}.png"),
                                  "phone": uri(f"{src}/phone-{mode}.png")})
        page.wait_for_timeout(200)
        im = Image.open(io.BytesIO(page.screenshot())).convert("RGB").resize((1600, 900), Image.LANCZOS)
        im.save(os.path.join(IMG, f"{tid}-{mode}.webp"), "WEBP", quality=82, method=6)
    page.close()
    if "dark" in modes:   # for the README: dark above the diagonal, light below it
        from PIL import ImageDraw
        light, dark = (Image.open(os.path.join(IMG, f"{tid}-{m}.webp")) for m in ("light", "dark"))
        mask = Image.new("L", light.size, 0)
        ImageDraw.Draw(mask).polygon([(0, 0), (light.width, 0), (0, light.height)], fill=255)
        Image.composite(dark, light, mask).save(os.path.join(IMG, f"{tid}-split.webp"), "WEBP", quality=82, method=6)
    # full size for the viewer: the bare desktop and phone screenshots and the login page
    for mode in modes:
        Image.open(f"{src}/desk-{mode}.png").convert("RGB").save(
            os.path.join(IMG, f"{tid}-desk-{mode}.webp"), "WEBP", quality=82, method=6)
        Image.open(f"{src}/phone-{mode}.png").convert("RGB").save(
            os.path.join(IMG, f"{tid}-phone-{mode}.webp"), "WEBP", quality=82, method=6)
    Image.open(f"{src}/login.png").convert("RGB").save(
        os.path.join(IMG, f"{tid}-login.webp"), "WEBP", quality=82, method=6)


def a(href, text):
    return f'<a href="{html.escape(href)}">{html.escape(text)}</a>'


def ipk_kb(tid):
    f = glob.glob(os.path.join(os.path.dirname(os.path.dirname(SITE)), "all-ipks", f"luci-theme-{tid}_*_all.ipk"))
    return f"{os.path.getsize(f[0]) / 1024:.0f} KB" if f else ""


def card(t, dark, pg, extra=""):
    tid = t["id"]
    modes = ["light"] + (["dark"] if dark.get(tid) else [])
    toggle = ('<div class="seg" role="group" aria-label="Colour scheme">'
              '<button type="button" aria-pressed="true" data-mode="light">Light</button>'
              '<button type="button" aria-pressed="false" data-mode="dark">Dark</button></div>') if len(modes) > 1 else ""
    return (f'<figure class="shot" data-id="{tid}" data-modes="{" ".join(modes)}">'
            f'<button type="button" class="zoom" data-view="combo" aria-label="Enlarge">'
            f'<img loading="lazy" width="1600" height="900" src="img/{tid}-light.webp" '
            f'alt="{html.escape(t["name"])} {html.escape(t["layout"])}: Status page on a monitor and a phone"></button></figure>'
            f'<div class="row">{toggle}{extra}'
            f'<a class="btn" href="{pg}/{tid}/cgi-bin/luci/">Open in playground</a>'
            f'<button type="button" class="ghost" data-view="login">Login page</button>'
            f'<span class="size">luci-theme-{tid} · {ipk_kb(tid)}</span></div>')


def page(themes, dark, base, repo):
    pg = f"{base}/playground"
    rel = f"https://github.com/{repo}/releases/latest" if repo else "#install"
    gh = f"https://github.com/{repo}" if repo else "https://github.com/DrorDvash"
    natives = [t for t in themes if t["group"] == "native"]
    skins = {}
    for t in themes:
        if t["group"] == "reskin":
            skins.setdefault(t["name"], {})[t["layout"]] = t

    out = []
    for t in natives:
        who, url = UPSTREAM[t["id"]]
        out.append(f'<article class="theme" id="{t["id"]}"><header><h3>{html.escape(t["name"])}</h3>'
                   f'<p>Port of {a(url, url.split("github.com/")[1])} by {html.escape(who)}</p></header>'
                   + card(t, dark, pg) + '</article>')
    native_html = "\n".join(out)

    out = []
    for name in sorted(skins):
        lay = skins[name]
        first = lay.get("Bootstrap") or next(iter(lay.values()))
        tabs = "".join(f'<button type="button" role="tab" aria-selected="{"true" if t is first else "false"}" '
                       f'data-id="{t["id"]}" data-modes="{"light dark" if dark.get(t["id"]) else "light"}" '
                       f'data-size="{ipk_kb(t["id"])}">{l}</button>'
                       for l in ("Bootstrap", "Argon", "Aurora") if (t := lay.get(l)))
        out.append(f'<article class="theme skin" id="{first["id"]}"><header><h3>{html.escape(name)}</h3>'
                   f'<div class="tabs" role="tablist" aria-label="Layout">{tabs}</div></header>'
                   + card(first, dark, pg) + '</article>')
    skin_html = "\n".join(out)

    credits = "".join(f'<tr><td>{html.escape(t["name"])}</td><td>{html.escape(UPSTREAM[t["id"]][0])}</td>'
                      f'<td>{a(UPSTREAM[t["id"]][1], UPSTREAM[t["id"]][1].split("github.com/")[1])}</td></tr>' for t in natives)
    credits += (f'<tr><td>The 16 reskins</td><td>{RESKINS[0]}</td><td>{a(RESKINS[1], RESKINS[1].split("github.com/")[1])}</td></tr>'
                + "".join(f'<tr><td>{l} layout</td><td>{w}</td><td>{a(u, u.split("github.com/")[1])}</td></tr>'
                          for l, (w, u) in LAYOUTS.items()))
    n = len(themes)
    return TEMPLATE.format(n=n, nskins=len(skins), base=base, pg=pg, rel=rel, gh=gh, repo_name=gh.split("github.com/")[1], natives=native_html, skins=skin_html,
                           credits=credits, hero=f"img/uniwrt21-{'dark' if dark.get('uniwrt21') else 'light'}.webp")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LuCI 21.02 Themes</title>
<meta name="description" content="{n} LuCI themes for OpenWrt 21.02 (GL.iNet Flint 2 / GL-MT6000 and other 21.02 firmware): five ported themes and {nskins} reskins on three layouts. Live playground.">
<style>
:root {{ --bg:#f5f6f9; --card:#fff; --ink:#151821; --dim:#5b6472; --line:#e1e4ea; --acc:#2f6fe4; --acc-ink:#fff; --chip:#eceff4; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0d0f14; --card:#151821; --ink:#eef0f5; --dim:#a3abb9; --line:#262b36; --acc:#5b93ff; --acc-ink:#0b1220; --chip:#20242f; }} }}
:root[data-theme="dark"] {{ --bg:#0d0f14; --card:#151821; --ink:#eef0f5; --dim:#a3abb9; --line:#262b36; --acc:#5b93ff; --acc-ink:#0b1220; --chip:#20242f; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
a {{ color:var(--acc); }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 16px; }}
.hero {{ padding:56px 0 24px; display:grid; gap:28px; }}
.hero h1 {{ font-size:clamp(32px,5vw,54px); line-height:1.08; letter-spacing:-.02em; margin:0; }}
.hero p {{ font-size:19px; color:var(--dim); max-width:46rem; margin:0; }}
.cta {{ display:flex; flex-wrap:wrap; gap:10px; }}
.btn,.ghost {{ display:inline-flex; align-items:center; min-height:40px; padding:8px 16px; border-radius:10px; font-weight:600; text-decoration:none; }}
.btn {{ background:var(--acc); color:var(--acc-ink); }}
.ghost {{ background:var(--chip); color:var(--ink); }}
.gh {{ gap:8px; }} .gh svg {{ width:20px; height:20px; fill:currentColor; flex:none; }}
.hero img {{ width:100%; height:auto; border-radius:16px; display:block; }}
h2 {{ font-size:28px; margin:56px 0 6px; }}
.lead {{ color:var(--dim); margin:0 0 20px; max-width:50rem; }}
.grid {{ display:grid; gap:22px; grid-template-columns:repeat(auto-fill,minmax(min(100%,520px),1fr)); }}
.theme {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px; }}
.theme header {{ display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:8px 14px; margin-bottom:12px; }}
.theme h3 {{ margin:0; font-size:21px; }}
.theme header p {{ margin:0; color:var(--dim); font-size:14px; }}
.shot {{ margin:0; border-radius:10px; overflow:hidden; background:var(--chip); }}
.shot img {{ width:100%; height:auto; display:block; }}
.row {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; margin-top:12px; }}
.row .btn,.row .ghost {{ min-height:36px; padding:6px 12px; font-size:14px; }}
.size {{ color:var(--dim); font-size:13px; margin-left:auto; }}
.seg,.tabs {{ display:inline-flex; background:var(--chip); border-radius:10px; padding:3px; gap:2px; }}
.seg button,.tabs button {{ border:0; background:none; color:var(--ink); font:inherit; font-size:14px; padding:5px 12px; border-radius:8px; cursor:pointer; min-height:30px; }}
.seg button[aria-pressed="true"],.tabs button[aria-selected="true"] {{ background:var(--card); box-shadow:0 1px 3px rgba(0,0,0,.18); font-weight:600; }}
button:focus-visible,a:focus-visible {{ outline:2px solid var(--acc); outline-offset:2px; }}
button.ghost {{ border:0; font:inherit; cursor:pointer; }}
.zoom {{ display:block; width:100%; padding:0; border:0; background:none; cursor:zoom-in; }}
dialog.viewer {{ position:fixed; inset:0; width:auto; height:auto; max-width:none; max-height:none; margin:0; padding:0; border:0; overflow:hidden; background:#0b0d12; color:#eef0f5; }}
dialog.viewer::backdrop {{ background:rgba(0,0,0,.6); }}
.viewer .bar {{ position:absolute; top:0; left:0; right:0; display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; padding:12px 16px; }}
.viewer .bar b {{ font-size:17px; margin-right:auto; }}
.viewer .seg {{ background:#20242f; }} .viewer .seg button {{ color:#eef0f5; }} .viewer .seg button[aria-pressed="true"] {{ background:#3a4152; }}
.viewer .x,.viewer .nav {{ border:0; background:#20242f; color:#eef0f5; border-radius:10px; min-width:40px; height:40px; font-size:20px; cursor:pointer; }}
.viewer .stage {{ position:absolute; inset:64px 16px 16px; display:flex; align-items:center; justify-content:center; gap:12px; }}
.viewer .stage img {{ max-width:100%; max-height:100%; object-fit:contain; border-radius:8px; box-shadow:0 20px 60px rgba(0,0,0,.5); }}
.viewer .nav {{ flex:none; }}
@media (max-width:600px) {{ .viewer .stage {{ inset:112px 8px 8px; }} .viewer .nav {{ display:none; }} }}
pre {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; overflow:auto; font-size:14px; }}
ul.facts {{ padding-left:1.2em; color:var(--dim); }} ul.facts b {{ color:var(--ink); }}
table {{ border-collapse:collapse; width:100%; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; font-size:15px; }}
td,th {{ text-align:left; padding:9px 14px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:13px; color:var(--dim); font-weight:600; }}
footer {{ color:var(--dim); font-size:14px; padding:40px 0 60px; }}
@media (max-width:600px) {{ .hero {{ padding-top:32px; }} .size {{ margin-left:0; width:100%; }} td,th {{ padding:8px 10px; }} table {{ font-size:14px; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior:auto !important; }} }}
</style></head>
<body><div class="wrap">
<section class="hero">
  <div><h1>LuCI themes for OpenWrt&nbsp;21.02</h1></div>
  <p>{n} theme packages for routers still on LuCI 21.02, such as the GL.iNet Flint 2 (GL-MT6000) with GL firmware 4.x: five complete themes ported from newer OpenWrt, and {nskins} reskins on three layouts. Every one is tested on desktop and phone, light and dark.</p>
  <div class="cta"><a class="btn" href="{pg}/">Try the live playground</a><a class="ghost" href="{rel}">Download</a><a class="ghost gh" href="{gh}"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>GitHub</a><a class="ghost" href="#credits">Credits</a></div>
  <img src="{hero}" width="1600" height="900" alt="UniWRT theme, Status page on a monitor and a phone">
</section>

<h2 id="ported">Ported themes</h2>
<p class="lead">Complete themes from newer OpenWrt releases, rewritten for 21.02's Lua templates, each with its own look.</p>
<div class="grid">
{natives}
</div>

<h2 id="reskins">Reskins on three layouts</h2>
<p class="lead">Each colour design comes on three layouts: 21.02's own Bootstrap (top menu), Argon (sidebar, the layout GL firmware ships) and Aurora (top bar with a mega menu). Pick a layout on each card.</p>
<div class="grid">
{skins}
</div>

<h2 id="install">Install</h2>
<p class="lead">Download the packages you want (or the zip with all of them), copy them to the router and install them with opkg. Then choose the theme under System → System → Language and Style.</p>
<pre>scp -O luci-theme-*.ipk root@192.168.8.1:/tmp/
ssh root@192.168.8.1 'opkg install /tmp/luci-theme-*.ipk'</pre>
<ul class="facts">
  <li><b>Installing never changes your current theme.</b> Removing one brings LuCI's default back if it was active.</li>
  <li><b>Nothing else is touched:</b> a package only adds its own files.</li>
  <li><b>Nothing from the internet:</b> fonts and images are in the package (25 to 150 KB each).</li>
  <li>Tested on a GL.iNet Flint 2 (GL-MT6000) with GL firmware 4.x and on OpenWrt 21.02.7.</li>
</ul>

<h2 id="credits">Credits</h2>
<p class="lead">These are ports. The designs belong to their authors; every package keeps its upstream licence and a NOTICE that says what was changed. Ported, tested and maintained for LuCI 21.02 by <a href="https://github.com/DrorDvash">@DrorDvash</a>.</p>
<table><tr><th>Theme</th><th>Author</th><th>Upstream</th></tr>{credits}</table>

<footer>The playground runs LuCI's own pages with answers recorded from an offline test router: the device, clients and numbers are made up, and nothing is saved. Source and packages: <a href="{gh}">github.com/{repo_name}</a>.</footer>
</div>
<dialog class="viewer" aria-label="Screenshot viewer">
  <div class="bar"><b></b>
    <div class="seg views" role="group" aria-label="View">
      <button type="button" data-v="combo">Monitor + phone</button><button type="button" data-v="desk">Desktop</button><button type="button" data-v="phone">Phone</button><button type="button" data-v="login">Login</button>
    </div>
    <div class="seg modes" role="group" aria-label="Colour scheme"><button type="button" data-m="light">Light</button><button type="button" data-m="dark">Dark</button></div>
    <button type="button" class="x" aria-label="Close">×</button>
  </div>
  <div class="stage"><button type="button" class="nav prev" aria-label="Previous theme">‹</button><img alt=""><button type="button" class="nav next" aria-label="Next theme">›</button></div>
</dialog>
<script>
(function () {{
  function show(card, id, mode) {{
    var fig = card.querySelector('.shot'), img = fig.querySelector('img');
    fig.dataset.id = id;
    img.src = 'img/' + id + '-' + mode + '.webp';
    card.querySelector('.row .btn').href = '{pg}/' + id + '/cgi-bin/luci/';
  }}
  document.querySelectorAll('.theme').forEach(function (card) {{
    var mode = 'light';
    function seg() {{
      var row = card.querySelector('.row'), s = row.querySelector('.seg'), modes = card.querySelector('.shot').dataset.modes.split(' ');
      if (s) s.hidden = modes.length < 2;
      if (modes.indexOf(mode) < 0) mode = 'light';
      if (s) s.querySelectorAll('button').forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.mode == mode ? 'true' : 'false'); }});
    }}
    card.addEventListener('click', function (ev) {{
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.dataset.mode) {{
        mode = b.dataset.mode;
        show(card, card.querySelector('.shot').dataset.id, mode);
      }} else if (b.getAttribute('role') == 'tab') {{
        card.querySelectorAll('[role=tab]').forEach(function (t) {{ t.setAttribute('aria-selected', t === b ? 'true' : 'false'); }});
        var fig = card.querySelector('.shot');
        fig.dataset.modes = b.dataset.modes;
        if (fig.dataset.modes.split(' ').indexOf(mode) < 0) mode = 'light';
        show(card, b.dataset.id, mode);
        card.querySelector('.size').textContent = 'luci-theme-' + b.dataset.id + ' · ' + b.dataset.size;
      }}
      seg();
    }});
    if (!card.querySelector('.seg') && card.querySelector('[role=tab][data-modes="light dark"]')) {{
      var s = document.createElement('div');
      s.className = 'seg'; s.setAttribute('role', 'group'); s.setAttribute('aria-label', 'Colour scheme');
      s.innerHTML = '<button type="button" aria-pressed="true" data-mode="light">Light</button><button type="button" aria-pressed="false" data-mode="dark">Dark</button>';
      card.querySelector('.row').prepend(s);
    }}
    seg();
  }});

  /* the viewer: any card's picture, bigger; views, light/dark, previous/next card */
  var dlg = document.querySelector('dialog.viewer'), img = dlg.querySelector('.stage img'),
      cards = [].slice.call(document.querySelectorAll('.theme')), st = {{}};
  function src() {{
    var f = st.v == 'combo' ? '' : '-' + st.v;
    return 'img/' + st.id + f + (st.v == 'login' ? '' : '-' + st.m) + '.webp';
  }}
  function paint() {{
    var card = cards[st.i], fig = card.querySelector('.shot'), modes = fig.dataset.modes.split(' ');
    st.id = fig.dataset.id;
    if (modes.indexOf(st.m) < 0) st.m = 'light';
    var tab = card.querySelector('[role=tab][aria-selected=true]');
    dlg.querySelector('.bar b').textContent = card.querySelector('h3').textContent + (tab ? ' · ' + tab.textContent : '');
    dlg.querySelectorAll('.views button').forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.v == st.v ? 'true' : 'false'); }});
    var ms = dlg.querySelector('.modes');
    ms.hidden = modes.length < 2 || st.v == 'login';
    ms.querySelectorAll('button').forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.m == st.m ? 'true' : 'false'); }});
    img.src = src();
    img.alt = dlg.querySelector('.bar b').textContent + ': ' + {{combo: 'monitor and phone', desk: 'desktop', phone: 'phone', login: 'login page'}}[st.v];
  }}
  document.addEventListener('click', function (ev) {{
    var b = ev.target.closest('.theme [data-view]');
    if (!b) return;
    var card = b.closest('.theme'), on = card.querySelector('.seg:not(.views) [aria-pressed=true]');
    st = {{i: cards.indexOf(card), v: b.dataset.view, m: on ? on.dataset.mode : 'light'}};
    paint();
    dlg.showModal();
  }});
  dlg.addEventListener('click', function (ev) {{
    var b = ev.target.closest('button');
    if (!b) {{ if (ev.target === dlg || ev.target.classList.contains('stage')) dlg.close(); return; }}
    if (b.dataset.v) st.v = b.dataset.v;
    else if (b.dataset.m) st.m = b.dataset.m;
    else if (b.classList.contains('x')) return dlg.close();
    else if (b.classList.contains('prev')) st.i = (st.i + cards.length - 1) % cards.length;
    else if (b.classList.contains('next')) st.i = (st.i + 1) % cards.length;
    paint();
  }});
  dlg.addEventListener('keydown', function (ev) {{
    if (ev.key == 'ArrowLeft' || ev.key == 'ArrowRight') {{
      st.i = (st.i + (ev.key == 'ArrowLeft' ? cards.length - 1 : 1)) % cards.length;
      paint();
    }}
  }});
}})();
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("themes", nargs="*")
    ap.add_argument("--base", default="")
    ap.add_argument("--repo", default="DrorDvash/openwrt-21.02-themes")
    ap.add_argument("--shots-only", action="store_true")
    ap.add_argument("--page-only", action="store_true")
    ap.add_argument("--compose-only", action="store_true", help="re-frame the existing screenshots")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    from playwright.sync_api import sync_playwright

    pg = os.path.join(SITE, "playground")
    tids = sorted(d for d in os.listdir(pg) if os.path.isdir(os.path.join(pg, d, "cgi-bin")))
    darkf = os.path.join(os.path.dirname(SITE), "dark.json")
    dark = json.load(open(darkf)) if os.path.exists(darkf) else {}

    if not a.page_only:
        httpd, url = serve(base)
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
            for tid in a.themes or tids:
                if not a.compose_only:
                    dark[tid] = shoot(b, url, tid)
                compose(b, tid, ["light"] + (["dark"] if dark[tid] else []))
                print(f"{tid:28s} {'light+dark' if dark[tid] else 'light'}", flush=True)
            b.close()
        httpd.shutdown()
        json.dump(dark, open(darkf, "w"), indent=1, sort_keys=True)
    if not a.shots_only:
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
            f.write(page([theme_info(t) for t in tids], dark, base, a.repo))
        size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(IMG, "*")))
        print(f"gallery: {len(tids)} themes, images {size / 1e6:.1f} MB -> {SITE}/index.html")


if __name__ == "__main__":
    main()
