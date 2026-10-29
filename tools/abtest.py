#!/usr/bin/env python3
"""Functional A/B test: run the same LuCI user flows with bootstrap (A) and a
theme (B), on a touch phone (390x844) and a desktop (1280x800), and compare
what actually got saved in the router config.

A theme may only change how things look, so for every flow the resulting uci
state must be identical between A and B. Also recorded: per-step pass/fail,
console errors, and the phone-keyboard case for "-- custom --" entries
(keyboard closed with "Done" / tap elsewhere instead of Enter).

usage: abtest.py --theme /luci-static/rack21 --out DIR
       [--url http://127.0.0.1:18180] [--container luci21-opt]
env:   LUCI_USER, LUCI_PASS, SUDO (command prefix for docker, default "sudo")
exit 0 = A and B equivalent (B may only be better on the phone-keyboard case)
"""
import argparse, json, os, re, shlex, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import login, settle, VIEWPORTS, CHROMIUM
from playwright.sync_api import sync_playwright

A_THEME = "/luci-static/bootstrap"


class Box:
    def __init__(self, container):
        self.c = container
        self.sudo = shlex.split(os.environ.get("SUDO", "sudo"))

    def sh(self, script):
        r = subprocess.run(self.sudo + ["docker", "exec", self.c, "sh", "-c", script],
                           capture_output=True, text=True)
        return r.stdout

    def snapshot(self, fresh=False):
        if fresh:
            self.sh("mkdir -p /root/ab-snap && cp -a /etc/config/. /root/ab-snap/")
        self.sh("[ -d /root/ab-snap ] || cp -a /etc/config /root/ab-snap")

    def restore(self, theme):
        # only the configs the flows change; luci (theme registration) is left alone
        self.sh("for c in firewall dhcp luci; do uci revert $c; done; cp /root/ab-snap/firewall /root/ab-snap/dhcp /etc/config/; "
                f"uci set luci.main.mediaurlbase={theme}; uci commit luci; rm -rf /tmp/luci-*")

    def state(self):
        out = self.sh("uci show firewall | grep '@redirect'; uci show dhcp | grep '@host'")
        return sorted(out.strip().splitlines())


class Flows:
    def __init__(self, page, phone, log):
        self.p, self.phone, self.log = page, phone, log

    def tap(self, loc):
        loc.scroll_into_view_if_needed()
        (loc.tap if self.phone else loc.click)()
        time.sleep(.25)

    def fill(self, scope, field, value):
        inp = self.p.locator(f"{scope} [id$='-{field}'] input[type='text']").first
        inp.scroll_into_view_if_needed()
        inp.fill(value)

    def custom_entry(self, scope, field, value, how):
        """Type a value into a dropdown's '-- custom --' entry.
        how: enter (hardware/desktop Enter) | button (theme '+' button) | done (phone keyboard closed)"""
        dd = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown").first
        self.tap(dd)
        inp = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown[open] input.create-item-input").first
        self.tap(inp)
        self.p.keyboard.type(value)
        if how == "enter":
            self.p.keyboard.press("Enter")
        elif how == "button":
            btn = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown[open] > ul.dropdown .p21-create-add")
            if btn.count() == 0:
                return "no-button"
            self.tap(btn.first)
        elif how == "invalid":
            btn = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown[open] > ul.dropdown .p21-create-add")
            if btn.count() == 0:
                return "no-button"
            self.tap(btn.first)
            time.sleep(.3)
            msg = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown > ul.dropdown .p21-create-error")
            return "error-shown" if msg.count() and msg.first.inner_text().strip() else "silent"
        elif how == "done":
            # the phone keyboard's Done closes the keyboard = the input loses focus
            inp.evaluate("e => e.blur()")
        time.sleep(.3)
        ok = self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown li[selected][data-value='{value}']").count() > 0
        # close the list again (tap the dropdown's arrow)
        if self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown[open]").count():
            self.tap(self.p.locator(f"{scope} [id$='-{field}'] .cbi-dropdown[open] > span.open").first)
        return "added" if ok else "lost"

    def modal_closed(self):
        # LuCI's own state; themes may hide the dialog by moving it instead of display:none
        self.p.wait_for_function("!document.body.classList.contains('modal-overlay-active')")
        time.sleep(.3)

    def save_apply(self):
        self.tap(self.p.locator(".cbi-page-actions .cbi-button-apply").first)
        self.p.wait_for_function("""() => /Configuration changes applied|No changes to apply|rolled back/i.test(document.body.innerText)""",
                                 timeout=120000)
        txt = self.p.evaluate("document.body.innerText")
        time.sleep(1)
        return "applied" if re.search("applied|No changes", txt) else "ROLLED-BACK"

    def goto(self, url, path):
        self.p.goto(f"{url}/cgi-bin/luci/{path}")
        settle(self.p)

    # --- flows ---------------------------------------------------------------
    def add_forward(self, url, tag):
        self.goto(url, "admin/network/firewall/forwards")
        self.tap(self.p.locator(".cbi-section-create .cbi-button-add").first)
        self.p.wait_for_selector("#modal_overlay .modal", state="visible")
        m = "#modal_overlay .modal"
        self.fill(m, "name", f"ab-fwd-{tag}")
        self.fill(m, "src_dport", "9001")
        r1 = self.custom_entry(m, "dest_ip", "10.213.0.77", "enter")
        self.fill(m, "dest_port", "91")
        self.tap(self.p.locator(f"{m} li[data-tab='advanced'] a"))
        r2 = self.custom_entry(m, "src_ip", "203.0.113.7", "enter")
        self.tap(self.p.locator(f"{m} .right > .cbi-button-positive").first)
        self.modal_closed()
        return {"dest_ip custom (Enter)": r1, "src_ip custom (Enter)": r2, "apply": self.save_apply()}

    def phone_keyboard(self, url):
        out = {}
        for how, val in (("done", "198.51.100.9"), ("button", "198.51.100.9"), ("invalid", "999.1.1.1")):
            self.goto(url, "admin/network/firewall/forwards")
            self.tap(self.p.locator(".cbi-section-create .cbi-button-add").first)
            self.p.wait_for_selector("#modal_overlay .modal", state="visible")
            m = "#modal_overlay .modal"
            self.tap(self.p.locator(f"{m} li[data-tab='advanced'] a"))
            out[f"src_ip custom ({how})"] = self.custom_entry(m, "src_ip", val, how)
            self.tap(self.p.locator(f"{m} .right > .cbi-button:not(.cbi-button-positive)").first)
            time.sleep(.4)
        return out

    def edit_forward(self, url):
        self.goto(url, "admin/network/firewall/forwards")
        # 21.02 shows the rule name via CSS (data-title), so match the row by its port
        row = self.p.locator("tr.cbi-section-table-row", has_text="port 8001").first
        self.tap(row.locator(".cbi-button-edit").first)
        self.p.wait_for_selector("#modal_overlay .modal", state="visible")
        m = "#modal_overlay .modal"
        self.fill(m, "src_dport", "8101")
        self.tap(self.p.locator(f"{m} .right > .cbi-button-positive").first)
        self.modal_closed()
        return {"apply": self.save_apply()}

    def delete_forward(self, url):
        self.goto(url, "admin/network/firewall/forwards")
        row = self.p.locator("tr.cbi-section-table-row", has_text="port 8002").first
        self.tap(row.locator(".cbi-button-remove").first)
        return {"apply": self.save_apply()}

    def add_lease(self, url, tag):
        self.goto(url, "admin/network/dhcp")
        self.tap(self.p.locator("li[data-tab='leases'] a").first)
        self.tap(self.p.locator("[data-tab='leases'] .cbi-section-create .cbi-button-add").first)
        self.p.wait_for_selector("#modal_overlay .modal", state="visible")
        m = "#modal_overlay .modal"
        self.fill(m, "name", f"ab-host-{tag}")
        r1 = self.custom_entry(m, "mac", "02:00:00:00:ab:01", "enter")
        r2 = self.custom_entry(m, "ip", "10.213.0.150", "enter")
        self.tap(self.p.locator(f"{m} .right > .cbi-button-positive").first)
        self.modal_closed()
        return {"mac custom (Enter)": r1, "ip custom (Enter)": r2, "apply": self.save_apply()}


def run_variant(browser, box, url, theme, vpname, out):
    box.restore(theme)
    ctx = browser.new_context(**VIEWPORTS[vpname])
    page = ctx.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("console", lambda m: m.type == "error" and "403" not in m.text and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
    login(page, url, os.environ["LUCI_USER"], os.environ["LUCI_PASS"])
    f = Flows(page, vpname == "390", errors)
    steps = {}
    tag = vpname
    for name, fn in (("add_forward", lambda: f.add_forward(url, tag)),
                     ("edit_forward", lambda: f.edit_forward(url)),
                     ("delete_forward", lambda: f.delete_forward(url)),
                     ("add_lease", lambda: f.add_lease(url, tag)),
                     ("phone_keyboard", lambda: f.phone_keyboard(url) if vpname == "390" else {})):
        try:
            steps[name] = fn()
        except Exception as e:
            steps[name] = {"ERROR": str(e).splitlines()[0]}
            page.screenshot(path=f"{out}/fail-{os.path.basename(theme)}-{vpname}-{name}.png")
    state = box.state()
    ctx.close()
    return {"steps": steps, "state": state, "console": errors}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:18180")
    ap.add_argument("--container", default="luci21-opt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resnapshot", action="store_true", help="re-take the config baseline from the current /etc/config")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    box = Box(a.container)
    box.snapshot(a.resnapshot)
    res = {"A": a.__dict__ | {"theme": A_THEME}, "B": {"theme": a.theme}, "vp": {}}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        for vp in ("390", "1280"):
            res["vp"][vp] = {"A": run_variant(b, box, a.url, A_THEME, vp, a.out),
                             "B": run_variant(b, box, a.url, a.theme, vp, a.out)}
        b.close()
    box.restore(a.theme)

    ok = True
    for vp, r in res["vp"].items():
        A, B = r["A"], r["B"]
        same_state = A["state"] == B["state"]
        print(f"[{vp}] uci state A==B: {same_state}  ({len(B['state'])} lines)")
        if not same_state:
            ok = False
            for l in sorted(set(A["state"]) ^ set(B["state"])):
                print("    ", "A only" if l in A["state"] else "B only", l)
        for flow in A["steps"]:
            sa, sb = A["steps"][flow], B["steps"].get(flow)
            for k in sorted(set(sa) | set(sb or {})):
                va, vb = sa.get(k), (sb or {}).get(k)
                flag = "same" if va == vb else ("B better" if flow == "phone_keyboard" and vb in ("added", "error-shown") else "DIFF")
                if flag == "DIFF" or "ERROR" in k or (va not in ("added", "applied", None) and flow != "phone_keyboard"):
                    ok = ok and flag != "DIFF" and k != "ERROR"
                print(f"    {flow:15} {k:28} A={va!s:12} B={vb!s:12} {flag}")
        for side in ("A", "B"):
            if r[side]["console"]:
                print(f"    console errors {side}: {r[side]['console'][:3]}")
                ok = ok and side == "A"
    json.dump(res, open(f"{a.out}/abtest.json", "w"), indent=1)
    print("RESULT:", "EQUIVALENT" if ok else "DIFFERENCES FOUND")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
