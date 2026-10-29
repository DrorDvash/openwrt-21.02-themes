#!/usr/bin/env python3
"""Visual QA for a LuCI 21.02 theme (Phase 5).

Logs in, visits the page list at 390x844 (touch phone) and 1280x800, saves full-page
screenshots and writes report.json with layout checks and browser console errors.

usage: qa.py --url http://127.0.0.1:18180 --label rack21 --out dist/screenshots/rack21
credentials come from LUCI_USER / LUCI_PASS (env).
"""
import argparse, json, os, sys, time
from playwright.sync_api import sync_playwright

# a system Chromium if there is one (Kali/Debian), else Playwright's own (playwright install chromium)
CHROMIUM = os.environ.get("CHROMIUM") or next((c for c in ("/usr/bin/chromium", "/usr/bin/chromium-browser")
                                                if os.path.exists(c)), None)

PAGES = [
    # (slug, path, action)
    ("status-overview", "admin/status/overview", None),
    ("system-language-style", "admin/system/system", "tab:language"),
    ("system-software", "admin/system/opkg", None),
    ("network-interfaces", "admin/network/network", None),
    ("network-wireless", "admin/network/wireless", None),
    ("network-dhcp-dns", "admin/network/dhcp", None),
    ("firewall-zones", "admin/network/firewall/zones", None),
    ("firewall-forwards", "admin/network/firewall/forwards", None),
    ("firewall-forward-modal-general", "admin/network/firewall/forwards", "modal:general"),
    ("firewall-forward-modal-advanced", "admin/network/firewall/forwards", "modal:advanced"),
    ("save-apply-list", "admin/system/system", "split"),
    ("custom-entry", "admin/network/firewall/forwards", "custom"),
    ("status-realtime", "admin/status/realtime", None),
    ("long-table-processes", "admin/status/processes", None),
    ("long-table-routes", "admin/status/routes", None),
]

VIEWPORTS = {
    "390": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                device_scale_factor=2),
    "1280": dict(viewport={"width": 1280, "height": 800}),
}

CHECK_JS = r"""
() => {
  const de = document.documentElement, vw = de.clientWidth;  // layout viewport (innerWidth grows when mobile zooms out)
  const r = {pageOverflowX: Math.max(de.scrollWidth, document.body.scrollWidth) - vw};
  // elements sticking out of the viewport that are not inside a horizontally scrollable box
  const off = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
    const b = el.getBoundingClientRect();
    if (b.width === 0 || b.height === 0) continue;
    // parked off-canvas (e.g. bootstrap submenus at left:-9999px) cannot cause scrolling
    if (b.right <= 0) continue;
    if (b.right > vw + 1 || b.left < -1) {
      let p = el.parentElement, clipped = false;
      while (p && p !== document.body) {
        const ps = getComputedStyle(p);
        if (/(auto|scroll|hidden)/.test(ps.overflowX)) { clipped = true; break; }
        p = p.parentElement;
      }
      const nm = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].join('.') : ''));
      if (!clipped) off.push(nm(el.parentElement) + ' > ' + nm(el) + ' ' + Math.round(b.left) + '..' + Math.round(b.right));
    }
  }
  r.offscreen = off.slice(0, 15);
  const m = document.querySelector('#modal_overlay .modal');
  if (m && getComputedStyle(document.body).overflow !== undefined && document.body.classList.contains('modal-overlay-active')) {
    const b = m.getBoundingClientRect();
    r.modal = {left: Math.round(b.left), right: Math.round(b.right), width: Math.round(b.width), vw};
    const btns = [...m.querySelectorAll('.right > button, .cbi-page-actions button, .button-row button')];
    r.modal.buttons = btns.map(x => { const bb = x.getBoundingClientRect(); return {t: x.textContent.trim(), left: Math.round(bb.left), right: Math.round(bb.right)}; });
  }
  const open = document.querySelector('.cbi-dropdown[open] > ul.dropdown');
  if (open) { const b = open.getBoundingClientRect(); r.openDropdown = {left: Math.round(b.left), right: Math.round(b.right), top: Math.round(b.top), bottom: Math.round(b.bottom), vh: window.innerHeight}; }
  // clipped text: a line of text cut through by an overflow:hidden box (e.g. a label inside a
  // bar thinner than its font). Whole lines out of view (collapsed panels) are not counted.
  const nm = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].join('.') : ''));
  const cs = new Map(), st = e => { if (!cs.has(e)) cs.set(e, getComputedStyle(e)); return cs.get(e); };
  const clips = el => {   // vertical client ranges of the overflow-hidden ancestors (incl. el)
    const out = [];
    for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
      if (/(hidden|clip)/.test(st(p).overflowY)) {
        const b = p.getBoundingClientRect();
        if (p.clientHeight <= 2 || p.clientWidth <= 2) return null;   // visually-hidden pattern
        out.push([b.top + p.clientTop, b.top + p.clientTop + p.clientHeight, p]);
      }
      if (st(p).position === 'fixed') break;   // e.g. the modal overlay: its ancestors do not clip it
    }
    return out;
  };
  for (const e of document.querySelectorAll('[data-qa-clip]')) e.removeAttribute('data-qa-clip');
  const clipped = [], seen = new Set();
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT,
    {acceptNode: n => /\S/.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT});
  for (let n; (n = tw.nextNode());) {
    const el = n.parentElement;
    if (!el || seen.has(el) || /^(SCRIPT|STYLE|OPTION|TEXTAREA)$/.test(el.tagName) || st(el).visibility === 'hidden') continue;
    if (document.body.classList.contains('modal-overlay-active') && !el.closest('#modal_overlay')) continue;   // behind the dialog
    // (hover tooltips hidden with opacity:0 stay in: a clipping box cuts them when they show)
    const rg = document.createRange(); rg.selectNodeContents(n);
    const lines = [...rg.getClientRects()].filter(b => b.height > 0 && b.width > 0);
    if (!lines.length) continue;
    const cl = clips(el); if (!cl || !cl.length) continue;
    for (const b of lines) {
      let top = b.top, bot = b.bottom, by = null;
      for (const [t, u, p] of cl) { if (t > top) { top = t; by = p; } if (u < bot) { bot = u; by = p; } }
      const frac = (bot - top) / b.height;
      if (frac > 0 && frac < .7) {
        seen.add(el);
        by.setAttribute('data-qa-clip', clipped.length);
        clipped.push({d: `${nm(el)} '${n.nodeValue.trim().slice(0, 24)}' ${Math.round(frac * 100)}% visible (cut by ${nm(by)})`, k: clipped.length, el: 0});
        break;
      }
    }
  }
  // generated labels (::before/::after text such as the progress bar title) in a box lower than the font
  for (const el of document.querySelectorAll('body *')) {
    for (const pe of ['::before', '::after']) {
      const ps = getComputedStyle(el, pe);
      let c = ps.content;
      if (!c || c === 'none' || c === 'normal' || ps.display === 'none') continue;
      c = c.replace(/attr\(([\w-]+)\)/g, (m, a) => el.getAttribute(a) || '').replace(/"/g, '');
      if (!/[A-Za-z0-9]{2}/.test(c) || st(el).display === 'none' || !el.getBoundingClientRect().height) continue;
      const fs = parseFloat(ps.fontSize);
      let lim = Infinity, by = el;
      // (height and overflow do not apply to an inline pseudo-element)
      if (ps.display !== 'inline' && /(hidden|clip)/.test(ps.overflowY) && parseFloat(ps.height) > 2) lim = parseFloat(ps.height);
      if (/(hidden|clip)/.test(st(el).overflowY) && el.clientHeight > 2 && el.clientHeight < lim) lim = el.clientHeight;
      if (lim < fs * 1.1) {
        el.setAttribute('data-qa-clip', clipped.length);
        clipped.push({d: `${nm(el)}${pe} '${c.slice(0, 24)}' in a ${Math.round(lim)}px box, font ${Math.round(fs)}px (cut by ${nm(by)})`, k: clipped.length});
      }
    }
  }
  r.clipped = clipped.slice(0, 30);
  // invisible text: a transparent text colour that no background-clip:text gradient paints (a
  // "background" shorthand over gradient text resets the clip and leaves an empty box)
  const inv = [], name = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].join('.') : ''));
  for (const el of document.querySelectorAll('body *')) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim())) continue;
    const cs = getComputedStyle(el), b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2 || cs.visibility === 'hidden' || +cs.opacity === 0 || parseFloat(cs.fontSize) < 2) continue;
    if (!/rgba\([^)]*,\s*0\)$/.test(cs.webkitTextFillColor || cs.color)) continue;
    if (/text/.test(cs.webkitBackgroundClip + ' ' + cs.backgroundClip) && cs.backgroundImage !== 'none') continue;
    if (cs.textShadow !== 'none') continue;  // painted by its shadow
    inv.push(`${name(el)} '${el.textContent.trim().slice(0, 24)}'`);
  }
  r.invisible = inv.slice(0, 10);
  // focus ring visible on first text input
  return r;
}
"""


UNCLIP_JS = r"""
(k) => {
  const e = document.querySelector(`[data-qa-clip="${k}"]`);
  if (!e) return null;
  e.scrollIntoView({block: 'center'});
  const b = e.getBoundingClientRect(), pad = 24;
  return {x: Math.max(0, b.left - pad), y: Math.max(0, b.top - pad),
          w: Math.min(document.documentElement.clientWidth, b.right + pad) - Math.max(0, b.left - pad),
          h: Math.min(window.innerHeight, b.bottom + pad) - Math.max(0, b.top - pad)};
}
"""


# floating panels (the open main menu, dialogs, open dropdown lists) must be opaque, or the
# page shows through them (a missing colour token made Aurora reskins' mega menu transparent):
# an almost opaque background colour, a background image (gradient) or a working backdrop blur
FLOAT_SEL = ("#modal_overlay .modal, .cbi-dropdown[open] > ul.dropdown, .desktop-menu-sheet, "
             ".desktop-nav.active:not(.desktop-menu-sheet .desktop-nav), #topmenu .dropdown-menu, .mobile-menu-overlay.mobile-menu-open")
FLOAT_JS = r"""
(sel) => {
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const c = getComputedStyle(el), b = el.getBoundingClientRect();
    if (!b.width || !b.height || c.display === 'none' || c.visibility === 'hidden' || +c.opacity === 0) continue;
    if (b.right <= 0 || b.bottom <= 0 || b.left >= innerWidth || b.top >= innerHeight) continue;   // parked off-screen
    const m = c.backgroundColor.match(/[\d.]+/g) || [], alpha = m.length > 3 ? +m[3] : m.length ? 1 : 0;
    // a backdrop blur only blurs the page when no ancestor starts its own backdrop (a blurred
    // header around a blurred dropdown: the dropdown then shows the page unblurred)
    let blur = c.backdropFilter && c.backdropFilter !== 'none';
    for (let p = el.parentElement; blur && p && p !== document.documentElement; p = p.parentElement) {
      const q = getComputedStyle(p);
      if ((q.backdropFilter && q.backdropFilter !== 'none') || q.filter !== 'none' || +q.opacity < 1) blur = false;
    }
    if (alpha < .95 && c.backgroundImage === 'none' && !blur)
      out.push((el.id ? '#' + el.id : el.tagName.toLowerCase()) + (el.classList.length ? '.' + [...el.classList].join('.') : '')
               + ' background ' + c.backgroundColor);
  }
  return out;
}
"""


# an open list must show whole and must not move the page. LuCI fits the list into the space
# up to its scroll parent (the nearest overflow auto/scroll box), so an overflow:hidden box in
# between cuts it (Argon's #view cut Save & Apply's list). Moving the mouse over an item focuses
# it, and the browser then scrolls a clipping box or the page to bring it into view (a jump).
LIST_JS = r"""
() => {
  const ul = document.querySelector('.cbi-dropdown[open] > ul.dropdown');
  if (!ul) return [];
  const nm = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].join('.') : ''));
  const b = ul.getBoundingClientRect(), out = [];
  for (let p = ul.parentElement; p && p !== document.documentElement; p = p.parentElement) {
    const c = getComputedStyle(p);
    if (/(hidden|clip)/.test(c.overflowY)) {
      const q = p.getBoundingClientRect(), top = q.top + p.clientTop, bottom = top + p.clientHeight;
      const cut = Math.max(0, top - b.top) + Math.max(0, b.bottom - bottom);
      if (cut > 1) out.push(nm(p) + ' cuts ' + Math.round(cut) + 'px off the open list');
    }
    if (/(auto|scroll)/.test(c.overflowY) || c.position === 'fixed') break;   // LuCI's scroll parent
  }
  return out;
}
"""
SCROLLS_JS = r"""
() => {
  const nm = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (e.classList.length ? '.' + [...e.classList].join('.') : ''));
  const r = {window: Math.round(scrollY)};
  for (const e of document.querySelectorAll('body *'))
    if (e.scrollTop && !e.closest('.cbi-dropdown')) r[nm(e)] = Math.round(e.scrollTop);
  return r;
}
"""


def open_split_list(page):
    """scroll to the end of the page, open Save & Apply's list and move the mouse over its
    items; returns (action result, what scrolled meanwhile). On touch screens LuCI scrolls
    the list into view on purpose, so movement only counts with a mouse."""
    dd = page.locator(".cbi-page-actions .cbi-dropdown").first
    if not dd.count():
        return "none", []
    page.evaluate("""() => { for (const e of [document.scrollingElement, ...document.querySelectorAll('body *')])
        if (/(auto|scroll)/.test(getComputedStyle(e).overflowY) || e === document.scrollingElement) e.scrollTop = 1e6; }""")
    time.sleep(0.5)
    before = page.evaluate(SCROLLS_JS)
    dd.locator(".open").click()
    time.sleep(0.5)
    for x, y in page.evaluate("""() => [...document.querySelectorAll('.cbi-dropdown[open] > ul.dropdown > li')]
            .map(e => { const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + Math.min(6, r.height / 2)]; })"""):
        page.mouse.move(x, y)
        time.sleep(0.3)
    after = page.evaluate(SCROLLS_JS)
    if page.evaluate("'ontouchstart' in window"):
        return "opened", []
    return "opened", [f"{k} scrolled {after.get(k, 0) - before.get(k, 0):+d}px while the list was open"
                      for k in sorted(before.keys() | after.keys()) if after.get(k, 0) != before.get(k, 0)]


def click_custom_entry(page):
    """port forward dialog > Advanced: open a list that has a "-- custom --" input, scroll it to
    its end and click the input (the shared phone fix then adds its "+" button). The row must
    stay whole inside the list: once it slid out of view and had to be scrolled to again."""
    page.click(".cbi-section-create .cbi-button-add, .cbi-button-add")
    page.wait_for_selector("#modal_overlay .modal", state="visible", timeout=10000)
    time.sleep(0.6)
    page.click("#modal_overlay li[data-tab='advanced'] a")
    time.sleep(0.4)
    dd = page.locator("#modal_overlay [data-tab-active='true'] .cbi-dropdown:has(input.create-item-input)").first
    if not dd.count():
        return "none", []
    dd.scroll_into_view_if_needed()
    dd.click()
    time.sleep(0.6)
    ul = dd.locator("ul.dropdown")
    # the case that broke needs a list that scrolls (how long it is depends on the router's hosts)
    # (some layouts animate max-height, so scroll only once it has shrunk, with the wheel like a user)
    ul.evaluate("u => { if (u.scrollHeight <= u.clientHeight + 4) u.style.maxHeight = Math.max(60, u.clientHeight - 40) + 'px'; }")
    time.sleep(0.6)
    b = ul.bounding_box()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + min(b["height"] / 2, 40))
    page.mouse.wheel(0, 2000)
    time.sleep(0.4)
    inp = ul.locator("input.create-item-input")
    r = inp.bounding_box()
    page.mouse.click(r["x"] + 10, r["y"] + r["height"] / 2)
    time.sleep(0.6)
    out = page.evaluate("""() => { const i = document.querySelector('.cbi-dropdown[open] ul.dropdown input.create-item-input');
        if (!i) return ['the list closed when its custom entry was clicked'];
        const li = i.parentNode.getBoundingClientRect(), u = i.closest('ul.dropdown').getBoundingClientRect(), p = [];
        if (document.activeElement !== i) p.push('the custom entry did not keep the focus');
        if (li.bottom > u.bottom + 1) p.push(`the custom entry slid ${Math.round(li.bottom - u.bottom)}px out of its list when clicked`);
        if (li.top < u.top - 1) p.push(`the custom entry slid ${Math.round(u.top - li.top)}px above its list when clicked`);
        return p; }""")
    return "clicked", out


def open_main_menu(page):
    """hover the Network entry of a top menu (bootstrap dropdowns, Aurora mega menu);
    layouts with a fixed sidebar have no floating menu"""
    li = page.locator("#topmenu > li").filter(has_text="Network").first
    if not li.count() or not li.is_visible():
        return False
    li.hover()
    time.sleep(1.0)
    return True


def verify_clipped(page, items):
    """keep only clipping that hides text pixels. For each clipping box: screenshot it as
    is and with its text made transparent (the difference = visible text pixels), then
    the same with the box's (and its ::before/::after) overflow visible. Text pixels that
    only appear once unclipped were cut off. LuCI polling is paused while measuring."""
    import io
    from PIL import Image, ImageChops
    page.evaluate("() => { try { L.Poll.stop(); } catch (e) {} }")
    def shot(clip):
        return Image.open(io.BytesIO(page.screenshot(clip=clip, animations="disabled"))).convert("L")
    def style(css):
        page.evaluate("""(css) => { let s = document.getElementById('qa-verify');
            if (!s) { s = document.createElement('style'); s.id = 'qa-verify'; document.head.appendChild(s); }
            s.textContent = css; }""", css)
    real = []
    for it in items:
        try:
            box = page.evaluate(UNCLIP_JS, it["k"])
            if not box or box["w"] < 2 or box["h"] < 2:
                real.append(it["d"]); continue
            clip = {"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]}
            sel = f'[data-qa-clip="{it["k"]}"]'
            unclip = f"{sel}, {sel}::before, {sel}::after {{ overflow: visible !important; }}"
            hide = (f"{sel}, {sel} *, {sel}::before, {sel}::after {{ color: transparent !important; "
                    f"text-shadow: none !important; -webkit-text-fill-color: transparent !important; }}")
            text = lambda a, b: ImageChops.difference(a, b).point(lambda v: 255 if v > 40 else 0)
            style(""); a = shot(clip); style(hide); a0 = shot(clip)
            style(unclip); b = shot(clip); style(unclip + hide); b0 = shot(clip)
            style("")
            extra = ImageChops.subtract(text(b, b0), text(a, a0))
            if extra.histogram()[255] > 6:
                real.append(it["d"])
        except Exception as e:   # unmeasurable: keep the finding
            real.append(it["d"] + f" (unverified: {type(e).__name__})")
    page.evaluate("() => { const s = document.getElementById('qa-verify'); s && s.remove(); window.scrollTo(0, 0); try { L.Poll.start(); } catch (e) {} }")
    return real


def login(page, base, user, pw, shot=None):
    page.goto(base + "/cgi-bin/luci/admin/status/overview", wait_until="networkidle")
    page.wait_for_selector("input[name=luci_password]", state="visible", timeout=15000)
    if shot:
        page.screenshot(path=shot, full_page=True)
    page.fill("input[name=luci_username]", user)
    page.fill("input[name=luci_password]", pw)
    page.click(".modal button, button.cbi-button-positive, .login-form .cbi-button-apply, button.login-submit, #do_login, "
               "input.u-login-btn")  # bootstrap / argon / uniwrt login
    page.wait_for_selector("#maincontent", state="attached", timeout=20000)
    page.wait_for_load_state("networkidle")


def settle(page):
    page.wait_for_load_state("networkidle")
    try:
        page.wait_for_function("!document.querySelector('#view > .spinning')", timeout=15000)
    except Exception:
        pass
    time.sleep(0.6)


def open_first_multi_dropdown(page, scope):
    dd = page.locator(scope + " .cbi-dropdown[multiple]:visible").first
    if dd.count() == 0:
        dd = page.locator(scope + " .cbi-dropdown:visible").first
    if dd.count() == 0:
        return "none"
    dd.scroll_into_view_if_needed()
    dd.click()
    time.sleep(0.4)
    return "opened" if page.locator(".cbi-dropdown[open]").count() else "not-opened"


def do_action(page, action):
    if not action:
        return None
    if action == "tab:language":
        page.click("li[data-tab='language'] a, a:text-is('Language and Style')")
        time.sleep(0.4)
        return "tab"
    if action.startswith("modal:"):
        page.click(".cbi-section-create .cbi-button-add, .cbi-button-add")
        page.wait_for_selector("#modal_overlay .modal", state="visible", timeout=10000)
        time.sleep(0.6)
        if action == "modal:advanced":
            page.click("#modal_overlay li[data-tab='advanced'] a")
            time.sleep(0.4)
        return open_first_multi_dropdown(page, "#modal_overlay .modal [data-tab-active='true']")


def run(args):
    user, pw = os.environ["LUCI_USER"], os.environ["LUCI_PASS"]
    os.makedirs(args.out, exist_ok=True)
    report = {"label": args.label, "url": args.url, "results": [], "console": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=["--no-sandbox"])
        for vpname, vp in VIEWPORTS.items():
            ctx = browser.new_context(**vp, reduced_motion="no-preference")
            page = ctx.new_page()
            cur = {"page": "login"}
            page.on("console", lambda m, cur=cur, vpname=vpname: m.type == "error" and report["console"].append(
                {"vp": vpname, "page": cur["page"], "text": m.text, "loc": m.location.get("url", "")}))
            page.on("pageerror", lambda e, cur=cur, vpname=vpname: report["console"].append(
                {"vp": vpname, "page": cur["page"], "text": "pageerror: " + str(e)}))
            shot = os.path.join(args.out, f"login_{vpname}.png")
            login(page, args.url, user, pw, shot)
            report["results"].append({"page": "login", "vp": vpname, "shot": os.path.basename(shot)})
            for slug, path, action in PAGES:
                if args.only and slug not in args.only:
                    continue
                cur["page"] = slug
                page.goto(f"{args.url}/cgi-bin/luci/{path}", wait_until="domcontentloaded")
                settle(page)
                moved = []
                try:
                    if action == "split":
                        act, moved = open_split_list(page)
                    elif action == "custom":
                        act, moved = click_custom_entry(page)
                    else:
                        act = do_action(page, action)
                except Exception as e:
                    act = "action-failed: " + str(e).splitlines()[0]
                checks = page.evaluate(CHECK_JS)
                checks["floating"] = page.evaluate(FLOAT_JS, FLOAT_SEL)
                checks["list"] = page.evaluate(LIST_JS) + moved
                if action in ("split", "custom") and act.startswith("action-failed"):
                    what = "Save & Apply's list" if action == "split" else "a list's custom entry"
                    checks["list"].append(f"could not open {what}: " + act[len("action-failed: "):][:100])
                checks["clipped"] = verify_clipped(page, checks["clipped"])[:15] if checks["clipped"] else []
                shot = os.path.join(args.out, f"{slug}_{vpname}.png")
                page.screenshot(path=shot, full_page=not action or not (action.startswith("modal") or action in ("split", "custom")))
                report["results"].append({"page": slug, "vp": vpname, "action": act, "checks": checks,
                                          "shot": os.path.basename(shot)})
                print(f"[{args.label}] {vpname} {slug}: overflowX={checks['pageOverflowX']} "
                      f"offscreen={len(checks['offscreen'])} clipped={len(checks['clipped'])} {act or ''}", flush=True)
                for c in checks["clipped"]:
                    print("    clipped:", c, flush=True)
                for c in checks["invisible"]:
                    print("    invisible text:", c, flush=True)
            if not args.only and vpname == "1280":
                # the opened main menu must be opaque
                cur["page"] = "menu-open"
                page.goto(f"{args.url}/cgi-bin/luci/admin/system/system", wait_until="domcontentloaded")
                settle(page)
                if open_main_menu(page):
                    shot = os.path.join(args.out, f"menu-open_{vpname}.png")
                    page.screenshot(path=shot)
                    report["results"].append({"page": "menu-open", "vp": vpname, "shot": os.path.basename(shot),
                                              "checks": {"pageOverflowX": 0, "offscreen": [], "clipped": [],
                                                         "floating": page.evaluate(FLOAT_JS, FLOAT_SEL)}})
                    page.mouse.move(5, 790)
            if not args.only:
                # menu check on phone: is the main menu reachable?
                cur["page"] = "menu"
                page.goto(f"{args.url}/cgi-bin/luci/admin/status/overview", wait_until="domcontentloaded")
                settle(page)
                report["menu_" + vpname] = page.evaluate("""() => {
                  const t = document.querySelector('#topmenu'); const b = t && t.getBoundingClientRect();
                  const h = document.querySelector('.p21-burger');
                  return {topmenu: b && {left: b.left, right: b.right, top: b.top, bottom: b.bottom, display: getComputedStyle(t).display},
                          burger: !!h && getComputedStyle(h).display !== 'none'};
                }""")
            ctx.close()
        browser.close()
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("console errors:", len(report["console"]))
    for c in report["console"]:
        print("  ", c)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18180")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chromium", default=CHROMIUM)
    ap.add_argument("--only", nargs="*")
    run(ap.parse_args())
