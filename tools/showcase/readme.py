#!/usr/bin/env python3
"""README.md for the public repository, and a GitHub-like preview of it.

The repository is laid out as: README.md, the packages under Releases, and the website (gallery +
playground, dist/showcase/site/) in docs/ for GitHub Pages. So the README's pictures are
docs/img/*.webp and its links go to the Pages site.

  readme.py --repo owner/name     -> dist/showcase/repo/README.md + preview.html (+ img/ link)
"""
import argparse, glob, html, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build import SITE, theme_info
from gallery import UPSTREAM, RESKINS, LAYOUTS, ipk_kb

OUT = os.path.join(os.path.dirname(SITE), "repo")


def readme(themes, repo):
    owner, name = repo.split("/")
    pages = f"https://{owner.lower()}.github.io/{name}"
    pg = f"{pages}/playground"
    rel = f"https://github.com/{repo}/releases/latest"
    img = "docs/img"
    natives = [t for t in themes if t["group"] == "native"]
    skins = {}
    for t in themes:
        if t["group"] == "reskin":
            skins.setdefault(t["name"], {})[t["layout"]] = t

    out = [f"""<h1 align="center">LuCI themes for OpenWrt 21.02</h1>

<p align="center">Modern LuCI themes for routers that are still on LuCI 21.02, such as the GL.iNet Flint 2
(GL-MT6000) with GL firmware 4.x: {len(themes)} packages, five complete themes ported from newer OpenWrt
and {len(skins)} reskins on three layouts.</p>

<p align="center">
  <a href="{pages}/"><b>Gallery</b></a> ·
  <a href="{pg}/"><b>Live playground</b></a> ·
  <a href="{rel}"><b>Download</b></a>
</p>

<p align="center"><a href="{img}/uniwrt21-dark.webp"><img src="{img}/uniwrt21-dark.webp" alt="UniWRT in dark mode on a monitor and a phone" width="100%"></a></p>

> The [gallery]({pages}/) shows every theme bigger, in light and dark, with its login page.

## Why this exists

Many GL.iNet routers run GL firmware 4.x built on **OpenWrt 21.02** and its LuCI web
interface, for example the **Flint 2 (GL-MT6000)**, **Beryl AX (GL-MT3000)**, **Brume 2
(GL-MT2500)** and **Flint (GL-AX1800)**. GL.iNet's
[firmware versions](https://www.gl-inet.com/en-us/pages/firmware-versions) page lists which
OpenWrt each model is built on. Most LuCI themes made in the last few years need
LuCI 23.05 or newer, so on these routers they don't install or they break the pages. Flashing
plain OpenWrt to get them means giving up GL's own firmware.

This repository brings those themes to LuCI 21.02: each one rewritten for 21.02, tested on a
phone and a desktop, and packaged so that installing never changes your current theme and
removing it leaves nothing behind. It is for anyone who has to stay on LuCI 21.02 (GL.iNet 4.x
firmware, or OpenWrt 21.02 itself) and wants a nicer interface.

## Try before you install

The [playground]({pg}/) runs LuCI's own pages in your browser, in any of the themes (a recording
of a test router: nothing is real, nothing is saved, nothing leaves your browser). Pick a theme
with the button at the bottom left, or under System → System → Language and Style; any user name
and password log in.

## Ported themes

Complete themes from newer OpenWrt releases, rewritten for 21.02's Lua templates. Themes with
a dark mode show it in the upper-left half of the picture and light in the lower-right. Click a
picture to enlarge it.

<table>"""]
    for i in range(0, len(natives), 2):
        out.append("<tr>")
        for t in natives[i:i + 2]:
            who, url = UPSTREAM[t["id"]]
            pic = f'{img}/{t["id"]}-split.webp' if os.path.exists(os.path.join(SITE, "img", f'{t["id"]}-split.webp')) else f'{img}/{t["id"]}-light.webp'
            out.append(f'<td width="50%" valign="top"><b>{t["name"]}</b> · {ipk_kb(t["id"])} · '
                       f'<a href="{pg}/{t["id"]}/cgi-bin/luci/">try it</a><br>'
                       f'<sub>Port of <a href="{url}">{url.split("github.com/")[1]}</a> by {html.escape(who)}'
                       + ('. Dark mode added in this port.' if t["id"] == "edge21" else '') + '</sub><br>'
                       f'<a href="{pic}"><img src="{pic}" alt="{t["name"]}"></a></td>')
        out.append("</tr>")
    lay = {l: u for l, (_, u) in LAYOUTS.items()}
    lay["Bootstrap"] = "https://github.com/openwrt/luci/tree/openwrt-21.02/themes/luci-theme-bootstrap"
    out.append(f"""</table>

## Reskins on three layouts

Sixteen designs by [vistrocity]({RESKINS[1]}), each on three layouts: 21.02's own
[**Bootstrap**]({lay["Bootstrap"]}) (top menu), [**Argon**]({lay["Argon"]}) (sidebar, the
layout GL firmware uses) and [**Aurora**]({lay["Aurora"]}) (top bar with a large menu). Click
a picture to enlarge it, or "try it" to open it in the playground.

<table>
<tr><th>Bootstrap</th><th>Argon</th><th>Aurora</th></tr>""")
    for name in sorted(skins):
        cells = "".join(
            f'<td width="33%" valign="top"><a href="{img}/{t["id"]}-light.webp"><img src="{img}/{t["id"]}-light.webp" alt="{name} on {l}"></a>'
            f'<br><sub><a href="{pg}/{t["id"]}/cgi-bin/luci/">try it</a> · {ipk_kb(t["id"])}</sub></td>'
            if (t := skins[name].get(l)) else '<td width="33%"></td>' for l in ("Bootstrap", "Argon", "Aurora"))
        out.append(f'<tr><td colspan="3"><b>{name}</b></td></tr><tr>{cells}</tr>')   # the name on its own row: wider pictures
    out.append(f"""</table>

## Install

1. Download the packages you want from [Releases]({rel}): each `luci-theme-*.ipk` on its own,
   or all of them in one zip.
2. Copy them to the router (`-O` because the router has no SFTP):
   ```sh
   scp -O luci-theme-*.ipk root@192.168.8.1:/tmp/
   ```
3. On the router, install them:
   ```sh
   opkg install /tmp/luci-theme-*.ipk
   ```
4. Choose the theme in LuCI under **System → System → Language and Style**.

- Installing never changes your current theme. Install as many as you like and switch between
  them.
- To update, install the newer files the same way. To remove one: `opkg remove luci-theme-<name>`
  (if it was the active theme, LuCI goes back to Bootstrap).
- A package only adds its own files and needs nothing from the internet.
- Tested on a GL.iNet Flint 2 (GL-MT6000) with GL firmware 4.x and on OpenWrt 21.02.7. Other
  routers with LuCI 21.02 should work the same. On OpenWrt 23.05 or newer, use the original
  themes instead.

## Make your own port

Everything that made these packages is here: `tools/port-theme.py` ports a theme and builds its
package, and the tests check it on an offline OpenWrt 21.02 test router.
[BUILDING.md](BUILDING.md) explains the steps.

## How this was made

These ports were made with the help of an AI coding assistant. If that makes you careful about
putting them on your router, that is fair. You don't have to take my word for anything: all the
source is here, and you can try every theme in the playground before installing it.

What is in a package:

- **Mostly CSS and LuCI page templates.** They change how LuCI looks, not what it does. The
  designs are the original authors'; the work here was making them fit LuCI 21.02.
- **Some JavaScript**, the same kind the original themes ship:
  - each layout's menu script, taken from the original theme and adapted to 21.02;
  - jQuery 3.5.1, which the original Argon and Edge themes use;
  - a small fix so that "custom" entries in drop-down lists can be added with a phone keyboard;
  - UniWRT's status dashboard, which reads system, network and Wi-Fi status through the same
    read-only LuCI calls that the Status page uses;
  - Edge's light/dark switch, which remembers your choice in the browser.
- **Nothing else.** No package runs commands on the router, changes its settings or loads
  anything from the internet. The install script only adds the theme to LuCI's list, and
  removing the package takes it off again.

To check a package yourself: an `.ipk` is a tar archive (`tar -xzf file.ipk`), and its source is
in [`themes/`](themes/).

## Credits

All credit for the designs goes to their authors: these are ports, and every package keeps its
upstream licence and a NOTICE that says what was changed. Ported, tested and maintained for LuCI
21.02 by [@DrorDvash](https://github.com/DrorDvash).

| Theme | Author | Upstream |
|---|---|---|""")
    for t in natives:
        who, url = UPSTREAM[t["id"]]
        out.append(f"| {t['name']} | {who} | [{url.split('github.com/')[1]}]({url}) |")
    out.append(f"| The 16 reskins | {RESKINS[0]} | [{RESKINS[1].split('github.com/')[1]}]({RESKINS[1]}) |")
    for l, (who, url) in LAYOUTS.items():
        out.append(f"| {l} layout | {who} | [{url.split('github.com/')[1]}]({url}) |")
    out.append("""
The playground's idea comes from [luci-theme-footstrap](https://github.com/VizzleTF/luci-theme-footstrap)'s.

## Licence

Each package carries its upstream licence (Apache-2.0; fonts under the SIL Open Font
License 1.1) and a NOTICE. The tools in this repository are Apache-2.0.
""")
    return "\n".join(out)


PREVIEW = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>README preview</title><style>
:root {{ --bg:#fff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --link:#0969da; --code:#818b981f; --chrome:#f6f8fa; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --fg:#f0f6fc; --muted:#9198a1; --line:#3d444d; --link:#4493f8; --code:#656c7633; --chrome:#151b23; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif; }}
.top {{ background:var(--chrome); border-bottom:1px solid var(--line); padding:14px 16px; font-size:14px; }}
.top b {{ font-weight:600; }} .top span {{ color:var(--muted); }}
.box {{ max-width:1012px; margin:24px auto; border:1px solid var(--line); border-radius:6px; }}
.box > .hd {{ padding:8px 16px; border-bottom:1px solid var(--line); font-size:14px; font-weight:600; }}
article {{ padding:32px; }}
@media (max-width:600px) {{ article {{ padding:16px; }} .box {{ margin:0; border-radius:0; border-width:1px 0; }} }}
a {{ color:var(--link); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
h1,h2 {{ border-bottom:1px solid var(--line); padding-bottom:.3em; font-weight:600; }}
h1 {{ font-size:2em; }} h2 {{ font-size:1.5em; margin-top:24px; }}
img {{ max-width:100%; box-sizing:content-box; }}
table {{ border-collapse:collapse; display:block; width:max-content; max-width:100%; overflow:auto; margin:0 0 16px; }}
td,th {{ border:1px solid var(--line); padding:6px 13px; }} tr:nth-child(2n) {{ background:var(--chrome); }}
code {{ background:var(--code); border-radius:6px; padding:.2em .4em; font-size:85%; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
sub {{ color:var(--muted); }}
</style></head><body>
<div class="top"><span>{owner} /</span> <b>{name}</b> &nbsp; <span>· Public · preview of the repository's front page (README.md)</span></div>
<div class="box"><div class="hd">README</div><article>{body}</article></div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="DrorDvash/openwrt-21.02-themes", help="owner/name on GitHub")
    a = ap.parse_args()
    pg = os.path.join(SITE, "playground")
    tids = sorted(d for d in os.listdir(pg) if os.path.isdir(os.path.join(pg, d, "cgi-bin")))
    md = readme([theme_info(t) for t in tids], a.repo)
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "README.md"), "w").write(md)
    # preview: GitHub renders the same Markdown; images as they will sit in docs/img/
    docs = os.path.join(OUT, "docs")
    if not os.path.islink(docs):
        os.symlink(SITE, docs)
    body = subprocess.run(["/usr/bin/python3", "-I", "-c",
                           "import sys, markdown; sys.stdout.write(markdown.markdown(sys.stdin.read(), extensions=['tables']))"],
                          input=md, capture_output=True, text=True, check=True).stdout
    owner, name = a.repo.split("/")
    open(os.path.join(OUT, "preview.html"), "w").write(PREVIEW.format(owner=owner, name=name, body=body))
    print(f"{OUT}/README.md ({len(md) // 1024} KB), preview.html")


if __name__ == "__main__":
    main()
