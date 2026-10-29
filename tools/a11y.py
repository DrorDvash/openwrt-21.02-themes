#!/usr/bin/env python3
"""Interaction + accessibility checks for a LuCI theme (Phase 5).
- phone hamburger: open, expand a submenu, navigate through it
- keyboard focus ring visible on desktop
- prefers-reduced-motion stops animations
- WCAG AA text contrast on several pages
usage: a11y.py --out DIR      (LUCI_USER / LUCI_PASS in env)"""
import argparse, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import login, settle, VIEWPORTS, PAGES, CHROMIUM
from playwright.sync_api import sync_playwright

CONTRAST_JS = r"""
(cardFallback) => {
  // any CSS colour (rgb(), lab(), oklch(), color-mix() results...) -> sRGB via a 1px canvas
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true}), cache = {};
  const parse = c => { if (!c || c === 'transparent') return c === 'transparent' ? {r: 0, g: 0, b: 0, a: 0} : null;
    const m = c.match(/^rgba?\(([^)]+)\)$/);
    if (m) { const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(x => parseFloat(x)); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; }
    if (!(c in cache)) { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#0000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
      const d = cx.getImageData(0, 0, 1, 1).data; cache[c] = {r: d[0], g: d[1], b: d[2], a: d[3] / 255}; }
    return cache[c]; };
  const COLOR = /(?:rgba?|hsla?|lab|lch|oklab|oklch|color)\([^()]*(?:\([^()]*\)[^()]*)*\)/g;
  const css = c => `rgb${c.a < 1 ? 'a' : ''}(${Math.round(c.r)}, ${Math.round(c.g)}, ${Math.round(c.b)}${c.a < 1 ? ', ' + +c.a.toFixed(3) : ''})`;
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
    return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b); };
  const blend = (fg, bg) => ({r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a), b: fg.b*fg.a + bg.b*(1-fg.a), a: 1});
  const bgOf = el => {
    let layers = [];
    for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none' && !/^url/.test(s.backgroundImage)) {
        // buttons/badges: test against the gradient's own colour stops (worst one wins later)
        if (e.matches('.btn, .cbi-button, button, .label, input[type=submit], input[type=button]')) {
          const stops = (s.backgroundImage.match(COLOR) || []).map(parse).filter(c => c && c.a > 0);
          if (stops.length) return {stops};
        }
        // other gradients: test against the bottom layer's opaque colour stops (the panel
        // base; upper layers are decorations such as rack screws). Without opaque stops the
        // gradient is a texture over the element's own background-color: fall through.
        const bi = s.backgroundImage, last = bi.slice(bi.lastIndexOf('gradient('));
        const stops = (last.match(COLOR) || []).map(parse).filter(c => c && c.a >= 1);
        if (stops.length) return {stops: stops.map(st => layers.slice().reverse().reduce((acc, l) => blend(l, acc), st))};
      }
      const c = parse(s.backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) return layers.reverse().reduce((acc, l) => blend(l, acc)); }
    }
    // nothing opaque: the browser canvas (dark when the page uses color-scheme: dark)
    const dark = /dark/.test(getComputedStyle(document.documentElement).colorScheme || '');
    return layers.reverse().reduce((acc, l) => blend(l, acc), dark ? {r: 18, g: 18, b: 18, a: 1} : {r: 255, g: 255, b: 255, a: 1});
  };
  const ctxOf = el => { const c = el.closest('header, footer, .modal, #tabmenu, .cbi-tabmenu, .cbi-dropdown, .zonebadge, .ifacebox, .ifacebadge, .cbi-page-actions, .cbi-section-table-titles, .cbi-map-descr, .cbi-section-descr, .cbi-value-title, .cbi-value-description, .cbi-section > h3, h2, .alert-message, .table, table, .cbi-section');
    return c ? (c.id ? '#' + c.id : c.tagName.toLowerCase() + (c.classList.length ? '.' + [...c.classList].slice(0, 2).join('.') : '')) : 'page'; };
  const out = []; let min = 99;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (seen.has(el)) continue; seen.add(el);
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (s.visibility === 'hidden' || s.display === 'none' || r.width === 0 || r.height === 0 || +s.opacity === 0) continue;
    if (el.closest('svg')) continue;
    // paints no glyphs: a 0px font (CSS-mask icons), the screen-reader-only clip, text indented out of its box
    if (parseFloat(s.fontSize) === 0 || (s.position === 'absolute' && r.width <= 1 && r.height <= 1)) continue;
    if (s.overflow === 'hidden' && Math.abs(parseFloat(s.textIndent) || 0) >= r.width) continue;
    if (document.body.classList.contains('modal-overlay-active') && !el.closest('#modal_overlay')) continue;  // inert behind the modal  // SVG text is painted with fill, not color (graphs checked visually)
    if (el.closest('[disabled], .cbi-button[disabled], option, script, style, [hidden], body:not(.modal-overlay-active) #modal_overlay')) continue;
    if (r.right < 0 || r.bottom < 0) continue;
    const fg0 = parse(s.color); if (!fg0) continue;
    const bgr = bgOf(el); const bgs = bgr.stops || [bgr];
    let ratio = 99, bg = bgs[0];
    for (const b0 of bgs) { const fg = blend(fg0, b0); const L1 = lum(fg), L2 = lum(b0);
      const r0 = (Math.max(L1, L2) + .05) / (Math.min(L1, L2) + .05); if (r0 < ratio) { ratio = r0; bg = b0; } }
    const px = parseFloat(s.fontSize), bold = parseInt(s.fontWeight) >= 700;
    const large = px >= 24 || (bold && px >= 18.66);
    const need = large ? 3 : 4.5;
    if (ratio >= need) min = Math.min(min, ratio);
    if (ratio < need) { el.setAttribute('data-a11y-i', out.length); out.push({idx: out.length, text: t.textContent.trim().slice(0, 40), ratio: +ratio.toFixed(2), need, color: css(fg0),
      bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`, sel: el.tagName.toLowerCase() + '.' + [...el.classList].join('.'), ctx: ctxOf(el)}); }
  }
  return {min: +min.toFixed(2), fails: out.slice(0, 150), nfail: out.length};
}
"""
def _rgba(v):
    import re
    m = re.match(r"rgba?\(([^)]+)\)", v)
    p = [float(x) for x in m.group(1).split(",")] if m else [0, 0, 0, 0]
    return p[:3], (p[3] if len(p) > 3 else 1.0)


def _lum(c):
    f = lambda x: x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4
    return .2126 * f(c[0] / 255) + .7152 * f(c[1] / 255) + .0722 * f(c[2] / 255)


def _ratio(a, b):
    x, y = sorted((_lum(a), _lum(b)))
    return (y + .05) / (x + .05)


def verify(pg, res, cap=80):
    """Re-measure computed-style failures against the rendered pixels behind the text:
    hide the element's text, screenshot its box (inset to skip borders) and take the
    worst-case 10th/90th luminance percentile pixel as the background."""
    import io
    from PIL import Image
    kept, skipped, ok = [], [], 0
    for f in res["fails"][:cap]:
        fg, alpha = _rgba(f["color"])
        loc = pg.locator(f'[data-a11y-i="{f["idx"]}"]').first
        if alpha == 0:
            skipped.append(f["text"] + " (gradient-clipped text, not measurable)")
            continue
        try:
            box = loc.bounding_box()
        except Exception:
            box = None
        if not box or box["width"] < 6 or box["height"] < 6:
            kept.append(f); continue
        loc.evaluate("e => { e.style.setProperty('color', 'transparent', 'important'); e.style.setProperty('text-shadow', 'none', 'important'); }")
        sx, sy = pg.evaluate("[window.scrollX, window.scrollY]")
        x0, y0 = max(box["x"] + sx + 2, 0), max(box["y"] + sy + 2, 0)
        clip = {"x": x0, "y": y0, "width": box["x"] + sx + box["width"] - 2 - x0, "height": box["y"] + sy + box["height"] - 2 - y0}
        png = None
        try:
            if clip["width"] >= 2 and clip["height"] >= 2:
                png = pg.screenshot(clip=clip, full_page=True, animations="disabled")
        except Exception:
            png = None
        finally:
            loc.evaluate("e => { e.style.removeProperty('color'); e.style.removeProperty('text-shadow'); }")
        if png is None:
            kept.append(f); continue
        px = list(Image.open(io.BytesIO(png)).convert("RGB").getdata())
        px.sort(key=_lum)
        med = px[len(px) // 2]
        worst = px[int(len(px) * .9)] if _lum(fg) < _lum(med) else px[int(len(px) * .1)]
        bg = [worst[i] if alpha >= 1 else worst[i] for i in range(3)]
        fgb = [fg[i] * alpha + bg[i] * (1 - alpha) for i in range(3)]
        r = _ratio(fgb, bg)
        if r >= f["need"]:
            ok += 1
            res["min"] = min(res["min"], round(r, 2))
            continue
        f.update(ratio=round(r, 2), bg="rgb(%d,%d,%d)" % tuple(bg), measured="pixels")
        kept.append(f)
    res["fails"] = kept + res["fails"][cap:]
    res["nfail"] = len(res["fails"])
    res["pixel_ok"], res["unmeasurable"] = ok, skipped
    if res["fails"]:
        res["min"] = min(res["min"], min(x["ratio"] for x in res["fails"]))
    return res


# representative backgrounds behind gradient-painted elements (rack faceplate / header)
FALLBACK = {"card": "rgb(32,38,44)", "head": "rgb(31,36,42)", "bg": "rgb(16,18,21)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18180")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timezone", help="browser time zone, e.g. to test time-of-day themes (circadian)")
    ap.add_argument("--color-scheme", default="light", choices=("light", "dark"),
                    help="the browser's prefers-color-scheme (themes that follow the device)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    res = {}
    user, pw = os.environ["LUCI_USER"], os.environ["LUCI_PASS"]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])

        # 1. phone hamburger
        ctx = b.new_context(**VIEWPORTS["390"], **({"timezone_id": a.timezone} if a.timezone else {}), color_scheme=a.color_scheme); pg = ctx.new_page()
        login(pg, a.url, user, pw)
        pg.goto(a.url + "/cgi-bin/luci/admin/status/overview"); settle(pg)
        # phone menus: bootstrap ports .p21-burger + #topmenu accordion; argon variants .showSide +
        # sidebar; aurora variants #navigation-toggle + overlay accordion
        layout = ("bootstrap" if pg.locator(".p21-burger").count() else "argon" if pg.locator(".showSide").count()
                  else "aurora" if pg.locator("#navigation-toggle").count()
                  else "uniwrt" if pg.locator("#u-burger").count() else "unknown")
        burger, top, sub = {
            "bootstrap": (".p21-burger", "#topmenu > li > a.menu", "#topmenu li.p21-sub-open .dropdown-menu a"),
            "argon": (".showSide", ".main-left .nav li > a.menu",   # Argon marks the open list, Alpha its <li>
                      ".main-left .nav li.slide .slide-menu.active a, .main-left .nav li.slide.active > .slide-menu a"),
            "aurora": ("#navigation-toggle", "#mobile-nav-list button.nav-row", "#mobile-nav-list li.is-expanded .mobile-nav-sublink"),
            "uniwrt": ("#u-burger", "#u-rail-nav .u-nav-group > a.u-nav-item", "#u-rail-nav .u-nav-sub.open > a.u-nav-item"),
        }.get(layout, (".p21-burger", "#topmenu > li > a.menu", "#topmenu li.p21-sub-open .dropdown-menu a"))
        if layout == "argon" and pg.locator("#noob-menu-fab").is_visible():
            burger = "#noob-menu-fab"   # NoobWRT: no header on phones, a floating button opens the sidebar
        pg.click(burger); time.sleep(.5)
        pg.screenshot(path=f"{a.out}/menu-open_390.png")
        pg.locator(top).filter(has_text=re.compile(r"^\s*Network\s*$")).first.click(); time.sleep(.5)
        pg.screenshot(path=f"{a.out}/menu-network-expanded_390.png")
        vis = pg.evaluate("""(sub) => { const l = [...document.querySelectorAll(sub)].filter(x => x.getBoundingClientRect().height > 0);   // collapsed groups do not count
            return l.map(x => { const r = x.getBoundingClientRect(); return {t: x.textContent, inView: r.left >= 0 && r.right <= document.documentElement.clientWidth && r.height > 0}; }); }""", sub)
        pg.locator(", ".join(f"{x.strip()}[href$='/admin/network/firewall']" for x in sub.split(","))).first.click()
        try:   # some menus animate before they navigate (UniWRT: 170 ms)
            pg.wait_for_url(re.compile(r"/admin/network/firewall"), timeout=5000)
        except Exception:
            pass
        pg.wait_for_load_state("networkidle")
        res["burger"] = {"layout": layout, "expanded_items": vis, "navigated_to": pg.url,
                         "aria_expanded_after_nav": pg.get_attribute(burger, "aria-expanded") if layout not in ("argon", "uniwrt") else None}
        ctx.close()

        # 2. keyboard focus + 3. reduced motion + 4. contrast (desktop)
        ctx = b.new_context(**VIEWPORTS["1280"], **({"timezone_id": a.timezone} if a.timezone else {}), color_scheme=a.color_scheme, reduced_motion="reduce"); pg = ctx.new_page()
        login(pg, a.url, user, pw)
        pg.goto(a.url + "/cgi-bin/luci/admin/network/firewall"); settle(pg)
        pg.keyboard.press("Tab"); pg.keyboard.press("Tab")
        res["focus"] = pg.evaluate("""() => { const e = document.activeElement, s = getComputedStyle(e);
            return {el: e.tagName + '.' + [...e.classList].join('.') + ' ' + e.textContent.trim().slice(0, 20), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor}; }""")
        pg.screenshot(path=f"{a.out}/keyboard-focus_1280.png", clip={"x": 0, "y": 0, "width": 1280, "height": 300})
        res["reduced_motion"] = pg.evaluate("""() => ({brandLed: document.querySelector('header .brand') ? getComputedStyle(document.querySelector('header .brand'), '::before').animationName : 'none',
            buttonTransition: getComputedStyle(document.querySelector('.cbi-button, .btn')).transitionDuration})""")
        res["contrast"] = {}
        for path in sorted({pp for _, pp, _ in PAGES}):
            pg.goto(f"{a.url}/cgi-bin/luci/{path}"); settle(pg)
            res["contrast"][path] = verify(pg, pg.evaluate(CONTRAST_JS, FALLBACK))
        # Save & Apply's open list (Argon's port once painted its items in the button's text colour)
        pg.goto(f"{a.url}/cgi-bin/luci/admin/system/system"); settle(pg)
        if pg.locator(".cbi-page-actions .cbi-dropdown .open").count():
            pg.locator(".cbi-page-actions .cbi-dropdown .open").first.click(); time.sleep(.5)
            res["contrast"]["save-apply-list"] = verify(pg, pg.evaluate(CONTRAST_JS, FALLBACK))
        pg.goto(f"{a.url}/cgi-bin/luci/admin/network/firewall/forwards"); settle(pg)
        pg.click(".cbi-button-add"); pg.wait_for_selector("#modal_overlay .modal"); time.sleep(.5)
        res["contrast"]["port-forward-modal"] = verify(pg, pg.evaluate(CONTRAST_JS, FALLBACK))
        ctx.close()
        # login page (logged out)
        ctx = b.new_context(**VIEWPORTS["1280"], **({"timezone_id": a.timezone} if a.timezone else {}), color_scheme=a.color_scheme); pg = ctx.new_page()
        pg.goto(a.url + "/cgi-bin/luci/"); pg.wait_for_selector("input[name=luci_password]", state="visible"); time.sleep(.5)
        res["contrast"]["login"] = verify(pg, pg.evaluate(CONTRAST_JS, FALLBACK))
        ctx.close()
        b.close()
    json.dump(res, open(f"{a.out}/a11y.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "contrast"}, indent=1))
    for k, v in res["contrast"].items():
        print(f"contrast {k}: min={v['min']} fails={v['nfail']}")
        for f in v["fails"][:8]:
            print("    ", f)


if __name__ == "__main__":
    main()
