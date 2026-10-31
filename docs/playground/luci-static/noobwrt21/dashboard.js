/*
 * NoobWRT, OpenWrt 21.02 port (luci-theme-noobwrt21): the row of stat cards on top of
 * Status > Overview, as NoobWRT's screenshots show it (that strip comes from NoobWRT's own
 * firmware, not from the theme: written for the port). Loaded by footer.htm on
 * admin/status/overview only. Read-only ubus calls an admin session has on stock 21.02:
 *   system info                  load average, uptime, memory, root filesystem
 *   luci-rpc getNetworkDevices   rx/tx byte counters (speed = delta over the poll interval)
 *   network.getWANNetworks() / getWAN6Networks()  (LuCI's network.js, state shared with the
 *                                Overview: network.interface dump etc.) WAN, its device, its IP
 * NoobWRT's CPU temperature line shows the 1-minute load average instead: 21.02 gives the
 * browser no temperature. A failed or denied call leaves its card at "—".
 * Polls every 3 s while the page is visible.
 */
(function() {
	'use strict';

	var POLL = 3000, SPARK = 30;
	var view = document.getElementById('view');
	if (!view || !window.L || document.getElementById('noob-dash'))
		return;

	var SVGNS = 'http://www.w3.org/2000/svg';
	var DASH = '—';

	function el(tag, cls, kids) {
		var n = document.createElement(tag);
		if (cls) n.className = cls;
		(kids || []).forEach(function(k) { n.appendChild(typeof k == 'string' ? document.createTextNode(k) : k); });
		return n;
	}
	function icon(paths) {
		var s = document.createElementNS(SVGNS, 'svg');
		s.setAttribute('viewBox', '0 0 24 24');
		s.setAttribute('class', 'nd-icon');
		s.setAttribute('aria-hidden', 'true');
		s.innerHTML = paths;
		return s;
	}
	var ICONS = {
		gauge: '<path d="M4.5 18a9 9 0 1 1 15 0"/><line x1="12" y1="14" x2="16" y2="9"/><circle cx="12" cy="14" r="1.5"/>',
		clock: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>',
		ram: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>',
		disk: '<path d="M22 12H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>'
	};

	function t(s) { return (typeof _ == 'function') ? _(s) : s; }

	/* ---- formatting ---- */
	function rate(bps) {   /* bits per second -> [number, unit] */
		if (bps == null || !isFinite(bps)) return [DASH, ''];
		var u = ['Kbit/s', 'Mbit/s', 'Gbit/s'], v = bps / 1000, i = 0;
		while (v >= 1000 && i < u.length - 1) { v /= 1000; i++; }
		return [v.toFixed(v >= 100 ? 0 : 1), u[i]];
	}
	function size(bytes) {   /* bytes -> [number, unit] */
		if (bytes == null || !isFinite(bytes)) return [DASH, ''];
		var gib = bytes / 1073741824;   /* at most three digits before the point */
		if (gib >= 1000) return [(gib / 1024).toFixed(2), 'TiB'];
		if (bytes >= 1000 * 1048576) return [gib.toFixed(2), 'GiB'];
		return [(bytes / 1048576).toFixed(2), 'MiB'];
	}
	function usage(used, total) {   /* "292 / 985 MiB", "9.1 / 15.6 GiB" */
		var g = total >= 10 * 1073741824, d = g ? 1073741824 : 1048576;
		return (used / d).toFixed(g ? 1 : 0) + ' / ' + (total / d).toFixed(g ? 1 : 0) + (g ? ' GiB' : ' MiB');
	}
	function uptime(s) {
		if (s == null) return DASH;
		var d = Math.floor(s / 86400), h = Math.floor(s / 3600) % 24, m = Math.floor(s / 60) % 60;
		return d ? d + 'd ' + h + 'h' : h + 'h ' + m + 'm';
	}

	/* ---- the cards ---- */
	function speedCard(cls, label) {
		var c = {}, spark = document.createElementNS(SVGNS, 'svg'), line = document.createElementNS(SVGNS, 'polyline');
		spark.setAttribute('viewBox', '0 0 100 30');
		spark.setAttribute('preserveAspectRatio', 'none');
		spark.setAttribute('class', 'nd-spark');
		spark.setAttribute('aria-hidden', 'true');
		line.setAttribute('vector-effect', 'non-scaling-stroke');
		spark.appendChild(line);
		c.line = line;
		c.num = el('span', 'nd-num', [DASH]);
		c.unit = el('span', 'nd-unit');
		c.trend = el('span', 'nd-trend');
		c.trend.setAttribute('aria-hidden', 'true');
		c.peak = el('div', 'nd-peak', [t('Peak') + ': ' + DASH]);
		c.label = el('div', 'nd-label', [label]);
		c.root = el('div', 'nd-card nd-speed ' + cls, [spark, el('div', 'nd-big', [c.num, ' ', c.unit, c.trend]), c.peak, c.label]);
		c.hist = [];
		c.max = 0;
		return c;
	}
	function totalCard(cls, label) {
		var c = { num: el('span', 'nd-num', [DASH]), unit: el('span', 'nd-unit'), label: el('div', 'nd-label', [label]) };
		c.root = el('div', 'nd-card nd-total ' + cls, [el('div', 'nd-big', [c.num, ' ', c.unit]), c.label]);
		return c;
	}
	function pill() {
		var p = { fill: el('div', 'nd-pill-fill'), text: el('span', 'nd-pill-text', [DASH]) };
		p.root = el('div', 'nd-pill', [p.fill, p.text]);
		p.root.setAttribute('role', 'meter');
		p.root.setAttribute('aria-valuemin', '0');
		p.root.setAttribute('aria-valuemax', '100');
		return p;
	}
	function line(ic, valueEl, cap) {
		return el('div', 'nd-line', [icon(ic), el('div', 'nd-line-body', [valueEl, el('div', 'nd-cap', [cap])])]);
	}

	var dl = speedCard('nd-dl', t('Download')), ul = speedCard('nd-ul', t('Upload'));
	var loadV = el('div', 'nd-val', [DASH]), upV = el('div', 'nd-val', [DASH]);
	var sys = el('div', 'nd-card nd-sys', [line(ICONS.gauge, loadV, t('Load')), el('div', 'nd-rule'), line(ICONS.clock, upV, t('Uptime'))]);
	var netState = el('div', 'nd-state', [DASH]), netIp = el('div', 'nd-ip', [DASH]);
	var net = el('div', 'nd-card nd-net', [el('div', 'nd-cap', [t('Internet')]), netState, el('div', 'nd-rule'), el('div', 'nd-cap', [t('IP')]), netIp]);
	var ram = pill(), disk = pill();
	var res = el('div', 'nd-card nd-res', [line(ICONS.ram, ram.root, t('RAM')), el('div', 'nd-rule'), line(ICONS.disk, disk.root, t('Storage'))]);
	var down = totalCard('nd-down', t('Downloaded')), up = totalCard('nd-up', t('Uploaded'));
	/* the pills sit above their caption, as in NoobWRT's screenshots */
	[ram, disk].forEach(function(p) { var b = p.root.parentNode; b.insertBefore(b.lastChild, p.root); });

	var dash = el('div', 'noob-dash', [el('div', 'nd-row', [dl.root, ul.root, sys, net, res, down.root, up.root])]);
	dash.id = 'noob-dash';
	dash.setAttribute('role', 'region');
	dash.setAttribute('aria-label', t('Router summary'));
	view.parentNode.insertBefore(dash, view);

	function setText(n, s) { if (n.textContent !== s) n.textContent = s; }
	function setPill(p, used, total) {
		if (!(total > 0) || used == null) { setText(p.text, DASH); p.fill.style.width = '0'; p.root.removeAttribute('aria-valuenow'); return; }
		var pc = Math.max(0, Math.min(100, Math.round(used / total * 100)));
		p.fill.style.width = pc + '%';
		p.root.setAttribute('aria-valuenow', pc);
		setText(p.text, usage(used, total) + ' (' + pc + '%)');
	}
	function setPair(c, v) { setText(c.num, v[0]); setText(c.unit, v[1]); }
	/* no WAN: the cards count the LAN's traffic, and say so */
	function setLabels(lan, dev) {
		[dl, ul, down, up].forEach(function(c) {
			var via = c.label.querySelector('.nd-via');
			if (lan && !via) {
				via = el('span', 'nd-via', [t('via LAN')]);
				c.label.appendChild(via);
			}
			else if (!lan && via)
				c.label.removeChild(via);
			c.root.title = lan ? t('No WAN: traffic of the LAN interface') + (dev ? ' (' + dev + ')' : '') : (dev || '');
		});
	}
	function pushSpeed(c, bps) {
		var prev = c.hist.length ? c.hist[c.hist.length - 1] : null;
		c.hist.push(bps);
		if (c.hist.length > SPARK) c.hist.shift();
		c.max = Math.max(c.max, bps);
		setPair(c, rate(bps));
		setText(c.peak, t('Peak') + ': ' + rate(c.max).join(' '));
		var tr = prev == null || bps == prev ? ['', 'nd-trend'] : bps > prev ? ['▲', 'nd-trend nd-trend-up'] : ['▼', 'nd-trend nd-trend-down'];
		setText(c.trend, tr[0]);
		c.trend.className = tr[1];
		var top = Math.max.apply(null, c.hist) || 1, n = c.hist.length, pts = [];
		for (var i = 0; i < n; i++)
			pts.push((i / Math.max(n - 1, 1) * 100).toFixed(1) + ',' + (28 - c.hist[i] / top * 26).toFixed(1));
		c.line.setAttribute('points', n > 1 ? pts.join(' ') : '');
	}
	function clearSpeed(c) {
		setPair(c, [DASH, '']); setText(c.trend, ''); c.line.setAttribute('points', '');
	}

	/* ---- data ---- */
	Promise.all([L.require('rpc'), L.require('network')]).then(function(mods) {
		var rpc = mods[0], network = mods[1];
		var callInfo = rpc.declare({ object: 'system', method: 'info', expect: { '': {} } });
		var callDevices = rpc.declare({ object: 'luci-rpc', method: 'getNetworkDevices', expect: { '': {} } });
		var last = null, timer = null, busy = false;

		/* which device carries the traffic: the WAN's (default route; LuCI's own choice), else the
		   configured 'wan' interface's, else the LAN's, where the directions swap (what the router
		   sends to the LAN is what the clients download) */
		function wan() {
			return Promise.all([
				L.resolveDefault(network.getWANNetworks(), []),
				L.resolveDefault(network.getWAN6Networks(), [])
			]).then(function(r) {
				var w4 = r[0][0], w6 = r[1][0], w = w4 || w6, ip = null;
				if (w4) ip = w4.getIPAddr();
				if (!ip && w6) ip = w6.getIP6Addr && w6.getIP6Addr();
				if (w)
					return { up: true, ip: ip, dev: devName(w), lan: false };
				return Promise.all([L.resolveDefault(network.getNetwork('wan'), null), L.resolveDefault(network.getNetwork('lan'), null)])
					.then(function(n) {
						var d = n[0] ? devName(n[0]) : null;
						if (d) return { up: false, dev: d, lan: false };
						return { up: false, dev: n[1] ? devName(n[1]) : null, lan: true };
					});
			});
		}
		function devName(n) {
			var d = (n.getL3Device && n.getL3Device()) || (n.getDevice && n.getDevice());
			return d ? d.getName() : (n.getIfname ? n.getIfname() : null);
		}

		function tick() {
			timer = null;
			if (document.hidden || busy) return;
			busy = true;
			Promise.all([
				L.resolveDefault(callInfo(), {}),
				L.resolveDefault(callDevices(), {}),
				L.resolveDefault(wan(), null)
			]).then(function(r) {
				var info = r[0] || {}, devs = r[1] || {}, w = r[2], now = Date.now();

				var ld = Array.isArray(info.load) ? info.load : null;
				setText(loadV, ld && ld[0] != null ? (ld[0] / 65536).toFixed(2) : DASH);
				loadV.title = ld ? t('Load Average') + ': ' + ld.map(function(l) { return (l / 65536).toFixed(2); }).join(', ') + ' (1 / 5 / 15 min)' : '';
				setText(upV, info.uptime != null ? uptime(info.uptime) : DASH);
				var m = info.memory;
				if (m && m.total)
					setPill(ram, m.total - (m.available != null ? m.available : (m.free || 0) + (m.buffered || 0) + (m.cached || 0)), m.total);
				else
					setPill(ram, null, 0);
				if (info.root && info.root.total)   /* KB */
					setPill(disk, (info.root.total - info.root.free) * 1024, info.root.total * 1024);
				else
					setPill(disk, null, 0);

				if (w) {
					setText(netState, w.up ? t('Connected') : t('Not connected'));
					net.classList.toggle('nd-on', !!w.up);
					net.classList.toggle('nd-off', !w.up);
					setText(netIp, w.ip || DASH);
					setLabels(w.lan, w.dev);
				}
				var st = w && w.dev && devs[w.dev] && devs[w.dev].stats;
				if (st && st.rx_bytes != null) {
					var rx = w.lan ? st.tx_bytes : st.rx_bytes, tx = w.lan ? st.rx_bytes : st.tx_bytes;
					setPair(down, size(rx));
					setPair(up, size(tx));
					if (last && last.dev == w.dev && now > last.t && rx >= last.rx && tx >= last.tx) {
						var s = (now - last.t) / 1000;
						pushSpeed(dl, (rx - last.rx) * 8 / s);
						pushSpeed(ul, (tx - last.tx) * 8 / s);
					}
					else if (last && last.dev != w.dev) {
						dl.hist = []; ul.hist = []; dl.max = ul.max = 0;
						clearSpeed(dl); clearSpeed(ul);
					}
					last = { dev: w.dev, t: now, rx: rx, tx: tx };
				}
				else {
					setPair(down, [DASH, '']); setPair(up, [DASH, '']);
					clearSpeed(dl); clearSpeed(ul);
					last = null;
				}
			}).catch(function() {}).then(function() {
				busy = false;
				schedule();
			});
		}
		function schedule() {
			if (!timer && !document.hidden)   /* the first speed one second after the first reading */
				timer = window.setTimeout(tick, last && !dl.hist.length ? 1000 : POLL);
		}
		document.addEventListener('visibilitychange', function() {
			if (document.hidden) {
				if (timer) window.clearTimeout(timer);
				timer = null;
				last = null;   /* no speed averaged over the time away */
			}
			else if (!busy) tick();
		});
		tick();
	}).catch(function() {});
})();
