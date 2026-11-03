"""UniWRT: uniwrt-luci (ox1d3x3, Apache-2.0, src/uniwrt-luci) on 21.02.

  generate("uniwrt") -> luci-theme-uniwrt21/

UniWRT is a standalone "network controller" shell: a dark icon rail with an accordion menu,
a sticky top bar with live CPU/RAM/throughput/uptime chips, a tab sub-nav and a light/dark/
auto switch. Its stylesheets are used as they are (no web fonts, no images but its SVG logo),
its templates are translated to Lua (uniwrt-template/), its menu script is vendored.
The status bar script is folded into menu-uniwrt21.js: a package may add only that one file
to /www/luci-static/resources. Dropped: /etc/config/uniwrt and the settings page (defaults
fixed), the uci-defaults script that made it the active theme. The Overview dashboard needs a
menu entry, an ACL file and a view outside the theme's directories, so it is folded into the
menu script too and shown on top of Status > Overview (21.02's sections stay below it).
21.02's ACLs do not let the browser read /proc/cpuinfo, so the CPU chip and card show the
load average instead of a percentage of the cores.

UniWRT's colours come from its own --u-* tokens, but its frame is unlike bootstrap's: it is
not a reskin baseline for vistrocity themes (yet).
"""
import os, re, shutil
from baselines import ROOT, VERSION, PortError, read, write, MAINTAINER, PKGS
from baselines.aurora import custom_entry_js

SUFFIX = "-uniwrt"
NATIVE = "uniwrt"
UW = os.path.join(ROOT, "src/uniwrt-luci/luci-theme-uniwrt")
TPL = os.path.join(ROOT, "tools/baselines/uniwrt-template")
CONTROL_TPL = os.path.join(ROOT, "tools/baselines/bootstrap-template")
COMMON = os.path.join(ROOT, "tools/baselines/common-21.02.css")
# WCAG AA in the light palette: same hues, darker (muted text 3.3:1, status chips 2:1, red buttons 3.9:1)
LIGHT = {"text-3": ("#808893", "#676f79"), "ok": ("#38cc65", "#207e3d"),
         "warn": ("#f5a623", "#9e6507"), "crit": ("#f0383b", "#d0292c")}


NETDEVS_JS = """/* 21.02 port: LuCI 21.02 grants no network.device to the browser, so the counters come from
   luci-rpc getNetworkDevices, reshaped like network.device status */
var callLuciNetDevs = rpc.declare({ object: 'luci-rpc', method: 'getNetworkDevices', expect: { '': {} } });
function netDevStatus() {
	return L.resolveDefault(callLuciNetDevs(), {}).then(function(m) {
		var out = {};
		Object.keys(m || {}).forEach(function(n) {
			var d = m[n] || {};
			out[n] = { type: d.bridge ? 'bridge' : d.devtype, devtype: d.devtype, 'bridge-members': d.ports,
			           statistics: d.stats, speed: (d.link && d.link.speed > 0) ? d.link.speed + 'F' : null };
		});
		return out;
	});
}
function callDeviceStatus(name) {
	return netDevStatus().then(function(all) { return all[name] || {}; });
}"""


def uw_version():
    return read(f"{UW}/ucode/template/themes/uniwrt/version").strip()


def sub(s, old, new, what):
    if s.count(old) != 1:
        raise PortError([f"UniWRT {what}: expected one {old[:50]!r}, found {s.count(old)}"])
    return s.replace(old, new)


def overview_js():
    """view/uniwrt/overview.js (the dashboard) as a class the menu script mounts at the top of
    Status > Overview: a package may not add a menu entry, ACL or view of its own"""
    ov = read(f"{UW}/htdocs/luci-static/resources/view/uniwrt/overview.js")
    for r in ("'use strict';\n", "'require view';\n", "'require rpc';\n", "'require poll';\n",
              "'require ui';\n", "'require fs';\n"):
        ov = sub(ov, r, "", "overview.js requires")
    # no /proc/cpuinfo on 21.02 (ACL): the CPU card shows the load averages instead of a percentage
    ov = sub(ov, "L.resolveDefault(fs.read('/proc/cpuinfo'), ''),", "Promise.resolve(''),", "overview.js cpuinfo")
    ov = sub(ov, """			var load1 = info.load[0] / 65536;
			var pct = Math.min(load1 / cores, 1) * 100;
			$('u-ov-cpu').textContent = pct.toFixed(0) + '%';
			var meter = $('u-ov-cpu-meter');
			if (meter) { meter.className = 'u-meter ' + level(pct); setMeter(meter, pct); }
			$('u-ov-cpu-sub').textContent = _('Load average') + ': ' + load1.toFixed(2) + ' (' + cores + (cores === 1 ? ' core)' : ' cores)');""",
             """			var loads = info.load.map(function(l) { return (l / 65536).toFixed(2); });
			$('u-ov-cpu').textContent = loads[0];
			$('u-ov-cpu-sub').textContent = _('Load average') + ': ' + loads.join(' · ') + ' (1 / 5 / 15 min)';""",
             "overview.js CPU card")
    ov = sub(ov, "metricCard(ICO.chip,  _('CPU Load'),'u-ov-cpu',  'u-ov-cpu-sub',  true),",
             "metricCard(ICO.chip,  _('Load Average'),'u-ov-cpu',  'u-ov-cpu-sub',  false),", "overview.js CPU card head")
    # system.info gives root/tmp in KB (memory and swap in bytes): upstream showed a 7 GB disk as 7 MB
    ov = sub(ov, "info.root.total - info.root.free), info.root.total));",
             "info.root.total - info.root.free) * 1024, info.root.total * 1024));", "overview.js root KB")
    ov = sub(ov, "info.tmp.total  - info.tmp.free),  info.tmp.total));",
             "info.tmp.total  - info.tmp.free) * 1024,  info.tmp.total * 1024));", "overview.js tmp KB")
    # 21.02's system.info has no root/tmp (later procd adds them): read the mount points once
    # (luci getMountPoints, bytes) and fill them in, /overlay being the disk a user fills
    ov = sub(ov, "var callInfo  = rpc.declare({ object: 'system', method: 'info' });",
             "var callInfo  = rpc.declare({ object: 'system', method: 'info' });\n"
             "var callMounts = rpc.declare({ object: 'luci', method: 'getMountPoints', expect: { result: [] } });",
             "overview.js mounts rpc")
    ov = sub(ov, """	updateStorage: function(info) {
		var box = (this.root || document).querySelector('#u-ov-storage');
		if (!box || !info) return;""", """	updateStorage: function(info) {
		var box = (this.root || document).querySelector('#u-ov-storage');
		if (!box || !info) return;
		var self = this;
		if (!info.root && !this._mounts) {
			this._mounts = [];
			L.resolveDefault(callMounts(), []).then(function(m) { self._mounts = m || []; self.updateStorage(info); });
		}
		if (!info.root && this._mounts && this._mounts.length) {
			var mnt = function(path) {
				var m = self._mounts.filter(function(x) { return x.mount === path; })[0];
				return m && m.size ? { total: m.size / 1024, free: m.free / 1024, used: (m.size - m.free) / 1024 } : null;
			};
			info = Object.assign({}, info, { root: mnt('/overlay') || mnt('/'), tmp: mnt('/tmp') });
		}""", "overview.js storage")
    # "Last 24 h" came from snapshots this page took while open: after a reboot it counted only
    # since the page was first opened (and said "24 h" for any window under an hour). Up for less
    # than a day, the counters cover the whole day; otherwise the label says the real window.
    ov = sub(ov, """	update: function(info) {
		if (!info) return;""", """	update: function(info) {
		if (!info) return;
		if (info.uptime) this._uptime = info.uptime;""", "overview.js uptime")
    ov = sub(ov, "var since = nowS - 86400, base = null;",
             "var since = nowS - 86400, base = null, fromBoot = this._uptime > 0 && this._uptime <= 86400;", "overview.js 24h boot")
    ov = sub(ov, "		if (!base && rec.s.length) base = rec.s[0];",
             "		if (!base && rec.s.length) base = rec.s[0];\n		if (fromBoot) base = [nowS - this._uptime, 0, 0];", "overview.js 24h base")
    ov = sub(ov, """			if (lbl) lbl.textContent = (winH >= 23.5) ? _('Last 24 h')""",
             """			if (lbl) lbl.textContent = (winH >= 23.5 || fromBoot) ? _('Last 24 h')""", "overview.js 24h label")
    ov = sub(ov, """				: _('Last 24 h');""", """				: _('Last') + ' ' + Math.max(1, Math.round(winH * 60)) + ' min';""", "overview.js 24h minutes")
    # a wireless network has no "up" of its own in 21.02's getWirelessDevices: up = its radio is up
    ov = sub(ov, "var up = !!i.up;", "var up = (i.up != null) ? !!i.up : !!(wifi[dev].up && i.ifname);",
             "overview.js wifi up")
    # no network.device on 21.02 (ACL): the throughput card reads luci-rpc getNetworkDevices
    ov = sub(ov, "var callNetDevs = rpc.declare({ object: 'network.device', method: 'status', expect: { '': {} } });",
             "var callNetDevs = netDevStatus;", "overview.js network.device")
    ov = sub(ov, "return view.extend({", "return baseclass.extend({", "overview.js class")
    return "var Overview = (function() {\n" + ov.strip() + "\n})();\n"


def menu_js(tid):
    """menu-uniwrt.js with status-uniwrt.js folded in (as a class the menu starts)"""
    menu = read(f"{UW}/htdocs/luci-static/resources/menu-uniwrt.js")
    st = read(f"{UW}/htdocs/luci-static/resources/status-uniwrt.js")
    # status: no /proc/cpuinfo (no ACL on 21.02): load average instead of a CPU percentage
    st = sub(st, "'require fs';\n", "", "status-uniwrt.js")
    st = sub(st, """		var self = this;
		L.resolveDefault(fs.read('/proc/cpuinfo'), '').then(function(text) {
			var m = text.match(/^processor\\s*:/gm);
			self.numCores = (m && m.length) || 1;
		});
		this.setup();""", "		this.setup();", "status-uniwrt.js __init__")
    st = sub(st, """			var load1 = info.load[0] / 65536;
			var pct = Math.min(load1 / this.numCores, 1) * 100;
			var s = pct.toFixed(0) + '%';
			this.cpuEl.querySelector('.indicator-value').textContent = s;
			try { sessionStorage.setItem('uniwrt-stat-cpu', s); } catch(e) {}
			this.cpuEl.title = 'CPU: ' + s + ' (load ' + load1.toFixed(2) + ' on ' + this.numCores + (this.numCores === 1 ? ' core)' : ' cores)');
			this.setLevel(this.cpuEl, pct < 60 ? 'ok' : pct < 85 ? 'warn' : 'crit');""",
             """			var load1 = info.load[0] / 65536;
			var s = load1.toFixed(2);
			this.cpuEl.querySelector('.indicator-value').textContent = s;
			try { sessionStorage.setItem('uniwrt-stat-cpu', s); } catch(e) {}
			this.cpuEl.title = _('Load Average') + ': ' + (info.load.map(function(l) { return (l / 65536).toFixed(2); }).join(', '));
			this.setLevel(this.cpuEl, 'ok');""", "status-uniwrt.js load")
    # 21.02's ACLs do not grant network.device (later LuCI does): the throughput chip and the
    # Overview's throughput card read luci-rpc getNetworkDevices, reshaped like network.device status
    st = sub(st, "var callDeviceStatus = rpc.declare({ object: 'network.device', method: 'status', params: ['name'] });",
             NETDEVS_JS, "status-uniwrt.js network.device")
    st = sub(st, "this.cpuEl = this.chip('cpu', 'CPU Load');", "this.cpuEl = this.chip('cpu', _('Load Average'));", "status chip")
    st = st.replace("'require baseclass';\n", "")
    st = sub(st, "return baseclass.extend({", "var Status = baseclass.extend({", "status-uniwrt.js class")
    body = st.split("'use strict';", 1)[1].strip()
    if not body.rstrip().endswith("});"):
        raise PortError(["status-uniwrt.js: unexpected end"])
    body = body.rstrip()[:-1] + ";\n"     # "});" -> "};" : a statement now, not the module's return
    body = body.replace("'require rpc';\n", "").replace("'require poll';\n", "")
    menu = sub(menu, "'require ui';\n", "'require ui';\n'require rpc';\n'require poll';\n\n" + body + "\n"
               + overview_js() + "\n", "menu-uniwrt.js requires")
    menu = sub(menu, "ui.menu.load().then(L.bind(this.render, this));",
               "ui.menu.load().then(L.bind(this.render, this));\n\t\tif (document.getElementById('u-stats')) new Status();"
               "\n\t\tif (L.env.dispatchpath.join('/') == 'admin/status/overview') this.mountOverview();",
               "menu-uniwrt.js __init__")
    menu = sub(menu, "\trender: function(tree) {", """\t/* 21.02 port: UniWRT's dashboard on top of Status > Overview (21.02's own sections
\t   stay below it) instead of a menu entry of its own */
\tmountOverview: function() {
\t\tvar view = document.getElementById('view');
\t\tif (!view) return;
\t\tvar ov = new Overview();
\t\tov.load().then(function(data) {
\t\t\tview.parentNode.insertBefore(E('div', { 'class': 'u-dash' }, [ ov.render(data) ]), view);
\t\t});
\t},

\trender: function(tree) {""", "menu-uniwrt.js render")
    return (f"/* menu-uniwrt.js + status-uniwrt.js of uniwrt-luci {uw_version()} (ox1d3x3, Apache-2.0), "
            f"folded into one module for the 21.02 port ({tid}) */\n" + menu)


def generate(t, out=None):
    if t != NATIVE:
        raise PortError([f"UniWRT is ported as itself only (no reskin baseline): {t}"])
    tid = "uniwrt21"
    ver = uw_version()
    out = out or os.path.join(PKGS, f"luci-theme-{tid}")
    keep35 = os.path.join(out, "css", "35-uniwrt-port.css")
    keep35 = read(keep35) if os.path.exists(keep35) else None
    if os.path.exists(out):
        shutil.rmtree(out)
    css = f"{out}/css"
    os.makedirs(css)
    src = f"{UW}/htdocs/luci-static/uniwrt"
    base = read(f"{src}/css/cascade.css")
    for name, (old, new) in LIGHT.items():
        base, n = re.subn(rf"(--u-{name}:\s*){old}\b", rf"\g<1>{new}", base, count=1)
        if n != 1:
            raise PortError([f"UniWRT cascade.css: token --u-{name}: {old} not found"])
    write(f"{css}/base-uniwrt-{ver}.css", f"/* uniwrt-luci {ver} cascade.css (ox1d3x3, Apache-2.0); light "
          f"tokens darkened for WCAG AA by tools/baselines/uniwrt.py */\n" + base)
    dark_keep = "".join(f"  --u-{name}: {old};\n" for name, (old, _) in LIGHT.items() if name in ("ok", "warn", "crit"))
    write(f"{css}/dark.css", f"/* uniwrt-luci {ver} dark.css (ox1d3x3, Apache-2.0); linked with a media "
          f"attribute by the 21.02 port */\n" + read(f"{src}/css/dark.css")
          + f"\n/* 21.02 port: UniWRT's own status colours on dark (the light ones were darkened) */\n:root {{\n{dark_keep}}}\n")
    write(f"{css}/30-uniwrt-port.css", read(f"{TPL}/30-uniwrt-port.css") + "\n" + read(COMMON))
    write(f"{css}/35-uniwrt-port.css", keep35 or "\n/* UniWRT on 21.02: theme-specific fixes */\n")

    st = f"{out}/htdocs/luci-static/{tid}"
    os.makedirs(f"{st}/img")
    shutil.copy(f"{src}/img/uniwrt-logo.svg", f"{st}/img/uniwrt-logo.svg")
    subs = {"@ID@": tid, "@KEY@": "UniWRT21", "@TITLE@": "UniWRT", "@VERSION@": VERSION, "@UWVER@": ver}

    def fill(s):
        for k, v in subs.items():
            s = s.replace(k, v)
        return s
    write(f"{st}/custom-entry.js", fill(custom_entry_js()))
    os.makedirs(f"{out}/htdocs/luci-static/resources")
    write(f"{out}/htdocs/luci-static/resources/menu-{tid}.js", menu_js(tid))
    for n in ("header", "footer", "sysauth"):
        write(f"{out}/luasrc/view/themes/{tid}/{n}.htm", fill(read(f"{TPL}/{n}.htm")))
    for n in ("postinst", "prerm", "postrm"):
        write(f"{out}/CONTROL/{n}", fill(read(f"{CONTROL_TPL}/{n}")), 0o755)
    write(f"{out}/CONTROL/control", (
        f"Package: luci-theme-{tid}\nVersion: {VERSION}\nDepends: luci-base\n"
        f"Source: https://github.com/ox1d3x3/uniwrt-luci\nLicense: Apache-2.0\nSection: luci\n"
        f"Maintainer: {MAINTAINER}\nArchitecture: all\nInstalled-Size: 0\n"
        f"Description: UniWRT (21.02 port) - network-controller style theme.\n"
        f" Port of uniwrt-luci {ver} (ox1d3x3, Apache-2.0) to OpenWrt 21.02 Lua templates:\n"
        f" icon rail, live status chips, light/dark/auto. Registers luci.themes.UniWRT21;\n"
        f" it does not change the active theme.\n"))
    shutil.copy(f"{UW}/../LICENSE", f"{out}/LICENSE")
    write(f"{out}/NOTICE", (
        f"luci-theme-{tid} - \"UniWRT (21.02 port)\"\n\n"
        f"Port of UniWRT Portal (luci-theme-uniwrt) {ver} by ox1d3x3,\n"
        f"https://github.com/ox1d3x3/uniwrt-luci (Apache-2.0). Stylesheets, menu and status bar\n"
        f"scripts and the UniWRT logo are UniWRT's.\n\n"
        f"Port changes (2026, Dror Dvash): ucode templates rewritten as OpenWrt 21.02 Lua\n"
        f"templates; /etc/config/uniwrt and the settings page removed (defaults fixed); the\n"
        f"uci-defaults script that activated the theme removed; status bar and Overview\n"
        f"dashboard folded into the menu script, the dashboard shown on top of Status >\n"
        f"Overview; CPU chip and card show the load average (21.02 does not let the browser\n"
        f"read /proc/cpuinfo); light colours darkened for WCAG AA; dark.css linked instead of inlined;\n"
        f"reduced-motion support, 21.02 widget fixes, phone fix for \"-- custom --\" dropdown\n"
        f"entries.\n"))
    print(f"uniwrt: {os.path.relpath(out, ROOT)} (id {tid}, key UniWRT21, light/dark/auto)")
    return out
