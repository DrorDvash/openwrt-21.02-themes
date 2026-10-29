#!/usr/bin/env python3
"""List the Design options under System > System > Language and Style and
optionally select one and Save & Apply.   usage: ui-theme.py [--select LABEL]"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import login, settle
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:18180")
ap.add_argument("--select")
a = ap.parse_args()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    login(pg, a.url, os.environ["LUCI_USER"], os.environ["LUCI_PASS"])
    pg.goto(a.url + "/cgi-bin/luci/admin/system/system"); settle(pg)
    pg.click("li[data-tab='language'] a"); time.sleep(.4)
    sel = pg.locator("select[id$='_mediaurlbase']")
    opts = sel.evaluate("s => [...s.options].map(o => o.textContent + '=' + o.value + (o.selected ? ' [selected]' : ''))")
    print("Design options:", opts)
    if a.select:
        sel.select_option(label=a.select)
        pg.click(".cbi-page-actions .cbi-button-apply")
        pg.wait_for_function("!document.querySelector('#modal_overlay .modal') || !document.body.classList.contains('modal-overlay-active')", timeout=60000)
        time.sleep(2)
        pg.goto(a.url + "/cgi-bin/luci/admin/status/overview"); settle(pg)
        print("stylesheet now:", pg.eval_on_selector("link[rel=stylesheet]", "l => l.getAttribute('href')"))
    b.close()
