/*
 * Playground runtime: answers LuCI's ubus, menu and other XHR/fetch calls from the recording
 * (window.__pgRPC / __pgHTTP, from pg-data.js) so the pages run with no router. Loaded right
 * after <head>, before luci.js makes its first request. Nothing here reaches a network.
 * Idea from luci-theme-footstrap's playground (VizzleTF, Apache-2.0); written anew for 21.02.
 */
(function () {
	'use strict';

	var PG = window.__pg || {};
	var RPC = window.__pgRPC || {}, HTTP = window.__pgHTTP || {};
	var login = PG.base + '/' + PG.theme + '/cgi-bin/luci/';
	window.__pgMiss = [];

	/* a static site has no session: a flag in sessionStorage stands in for one */
	try {
		if (PG.page == 'logout') {
			sessionStorage.removeItem('pg-auth');
			location.replace(login);
			return;
		}
		if (PG.page != 'login' && !sessionStorage.getItem('pg-auth')) {
			sessionStorage.setItem('pg-return', location.pathname);
			location.replace(login);
			return;
		}
		/* as on a router: /cgi-bin/luci/ (the logo's link) opens the Overview when logged in */
		if (PG.page == 'login' && sessionStorage.getItem('pg-auth')) {
			location.replace(PG.base + '/' + PG.theme + '/cgi-bin/luci/admin/status/overview/');
			return;
		}
	} catch (e) {}

	/* any user name and password log in */
	if (PG.page == 'login') {
		var enter = function () {
			var back;
			try {
				sessionStorage.setItem('pg-auth', '1');
				back = sessionStorage.getItem('pg-return');
				sessionStorage.removeItem('pg-return');
			} catch (e) {}
			if (!back || back.indexOf(PG.base + '/' + PG.theme + '/') != 0 || /\/cgi-bin\/luci\/?$/.test(back))
				back = PG.base + '/' + PG.theme + '/cgi-bin/luci/admin/status/overview/';
			location.replace(back);
		};
		HTMLFormElement.prototype.submit = enter;
		document.addEventListener('submit', function (ev) { ev.preventDefault(); enter(); }, true);
	}

	function stable(v) {
		if (Array.isArray(v)) return '[' + v.map(stable).join(',') + ']';
		if (v && typeof v == 'object')
			return '{' + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ':' + stable(v[k]); }).join(',') + '}';
		return JSON.stringify(v === undefined ? null : v);
	}

	/* writes "succeed" and change nothing; anything else unrecorded is an error, as on a router */
	var WRITES = /^uci\.(set|add|delete|rename|order|commit|revert|confirm|apply)$/;

	/* Realtime Graphs: series computed from the clock (smooth, the same for every call), so the
	   graphs move as on a router; a recording would stand still. Formats as luci-bwc's. */
	function realtime(args) {
		var now = Math.floor(Date.now() / 1000), out = [];
		var wave = function (t, a, b) { return 1 + .45 * Math.sin(t / a) + .25 * Math.sin(t / b); };
		/* bytes so far for a rate r * wave(t): its integral, so consecutive calls agree */
		var total = function (t, r, a, b) { return Math.round(r * (t - .45 * a * Math.cos(t / a) - .25 * b * Math.cos(t / b))); };
		for (var t = now - 179; t <= now; t++) {
			switch (args.mode) {
			case 'interface':
				var s = (args.device == 'wlan0') ? .6 : 1;
				out.push([t, total(t, 2.4e6 * s, 23, 7.3), total(t, 1900 * s, 23, 7.3), total(t, 6.1e5 * s, 31, 5.1), total(t, 1100 * s, 31, 5.1)]);
				break;
			case 'wireless':
				out.push([t, Math.round(1.2e6 * (0.85 + .1 * Math.sin(t / 17))), Math.round(256 - 45 + 4 * Math.sin(t / 9)), 256 - 92]);
				break;
			case 'load':
				out.push([t, Math.round(38 * wave(t, 41, 11)), Math.round(28 * wave(t, 97, 23)), 20]);
				break;
			case 'conntrack':
				out.push([t, Math.round(18 * wave(t, 29, 9)), Math.round(64 * wave(t, 53, 13)), 3]);
				break;
			}
		}
		return [0, { result: out }];
	}

	/* byte counters that grow with the clock, so live speeds (NoobWRT's Overview cards) move;
	   a recording would show 0 */
	var T0 = Date.now() / 1000 - 2.5 * 86400;   /* as if counting for 2.5 days */
	function counters(res) {
		var t = Date.now() / 1000, out = JSON.parse(JSON.stringify(res)), devs = out[1] || {};
		var grow = function (r, a, b) { return Math.round(r * (t - T0 - .45 * a * Math.cos(t / a) - .25 * b * Math.cos(t / b))); };
		Object.keys(devs).forEach(function (n, i) {
			var st = devs[n] && devs[n].stats, s = 1 / (1 + i);
			if (!st || !st.rx_bytes) return;
			st.rx_bytes += grow(2.4e5 * s, 23, 7.3); st.tx_bytes += grow(6.1e4 * s, 31, 5.1);
			if (st.rx_packets != null) { st.rx_packets += grow(180 * s, 23, 7.3); st.tx_packets += grow(60 * s, 31, 5.1); }
		});
		return out;
	}

	/* after Save & Apply: a newly chosen theme opens the same page in it */
	function applied() {
		var next = null;
		try { next = sessionStorage.getItem('pg-next'); sessionStorage.removeItem('pg-next'); } catch (x) {}
		if (next && next != PG.theme && (window.__pgThemes || []).some(function (t) { return t.id == next; }))
			setTimeout(function () {
				location.href = PG.base + '/' + next + location.pathname.slice((PG.base + '/' + PG.theme).length);
			}, 1500);
	}

	/* The Overview starts its status boxes as soon as LuCI's ui module is loaded, without waiting
	   for the router's feature list (luci.getFeatures). On a router the list is usually in first;
	   here every answer is instant, a warm cache can win the race and hasSystemFeature() throws.
	   Until LuCI has its list, answer from the recording. */
	var features = (RPC['luci.getFeatures({})'] || [])[1] || {}, luciObj = null;
	Object.defineProperty(window, 'L', {
		configurable: true,
		get: function () { return luciObj; },
		set: function (v) {
			luciObj = v;
			var proto = v && Object.getPrototypeOf(v), has = proto && proto.hasSystemFeature;
			if (!has || has.pg) return;
			proto.hasSystemFeature = function (name, sub) {
				try { return has.apply(this, arguments); }
				catch (e) {
					var ft = features[name];
					if (arguments.length == 2) return (ft && typeof ft == 'object') ? ft[sub] : null;
					return ft != null && ft != false;
				}
			};
			proto.hasSystemFeature.pg = true;
		}
	});

	function answer(e) {
		var key = e.method + '()', obj, fn;
		if (e.method == 'call' && Array.isArray(e.params)) {
			obj = e.params[1]; fn = e.params[2];
			if (obj == 'luci' && fn == 'getRealtimeStats')
				return { jsonrpc: '2.0', id: e.id, result: realtime(e.params[3] || {}) };
			/* paths the pages built from LuCI's env carry the playground's base: drop it */
			key = (obj + '.' + fn + '(' + stable(e.params[3] || {}) + ')').split(PG.base + '/').join('/');
		}
		/* Language and Style: the page's theme is the active one, and Save & Apply of another
		   opens the same page in it */
		if (key == 'uci.get({"config":"luci"})' && RPC[key]) {
			var luci = JSON.parse(JSON.stringify(RPC[key]));
			luci[1].values.main.mediaurlbase = '/luci-static/' + PG.theme;
			return { jsonrpc: '2.0', id: e.id, result: luci };
		}
		if (obj == 'uci' && fn == 'set' && (e.params[3] || {}).config == 'luci') {
			var base = ((e.params[3] || {}).values || {}).mediaurlbase;
			try { if (base) sessionStorage.setItem('pg-next', base.replace('/luci-static/', '')); } catch (x) {}
		}
		if (obj == 'uci' && /^apply/.test(fn))
			applied();
		if (key == 'luci-rpc.getNetworkDevices({})' && RPC[key])
			return { jsonrpc: '2.0', id: e.id, result: counters(RPC[key]) };
		if (RPC.hasOwnProperty(key))
			return { jsonrpc: '2.0', id: e.id, result: RPC[key] };
		if (obj == 'session' && fn == 'access')
			return { jsonrpc: '2.0', id: e.id, result: [0, { access: true }] };
		if (WRITES.test(obj + '.' + fn))
			return { jsonrpc: '2.0', id: e.id, result: [0, {}] };
		if (obj == 'uci' && fn == 'changes')
			return { jsonrpc: '2.0', id: e.id, result: [0, { changes: {} }] };
		window.__pgMiss.push(key);
		return { jsonrpc: '2.0', id: e.id, result: [6] };  /* UBUS_STATUS_PERMISSION_DENIED */
	}

	function ubus(body) {
		var req;
		try { req = JSON.parse(body || 'null'); } catch (e) { req = null; }
		return JSON.stringify(Array.isArray(req) ? req.map(answer) : answer(req || {}));
	}

	/* the recorded request a URL stands for: "GET /cgi-bin/luci/admin/menu" (query ignored) */
	function route(method, url, body) {
		var path;
		try { path = new URL(url, location.href).pathname; } catch (e) { return null; }
		if (method == 'POST' && /\/ubus\/?$/.test(path))
			return { type: 'application/json', body: null, ubus: true };
		var m = path.match(/\/cgi-bin\/(luci\/.*|cgi-[a-z]+)$/);
		if (!m) return null;
		var key = method + ' /cgi-bin/' + m[1].replace(/\/$/, '');
		if (m[1] == 'cgi-exec')  /* fs.exec_direct: which command */
			key += ' ' + (new URLSearchParams(typeof body == 'string' ? body : '').get('command') || '');
		var r = HTTP[key];
		if (r) return { type: r.type, body: r.body };
		if (method == 'POST' && /^luci\/admin\/uci\//.test(m[1])) {
			if (/\/apply/.test(m[1])) applied();
			return { type: 'application/json', body: '{}' };
		}
		window.__pgMiss.push(key);
		return { type: 'text/plain', body: '', status: 404 };
	}

	var realFetch = window.fetch;
	window.fetch = function (input, init) {
		var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase(),
		    r = route(method, typeof input == 'string' ? input : input.url, init && init.body);
		if (!r) return realFetch.apply(window, arguments);
		var body = r.ubus ? ubus(init && init.body) : r.body;
		return Promise.resolve(new Response(body, { status: r.status || 200, headers: { 'content-type': r.type } }));
	};

	/* XHR: re-point a matched request at a blob URL so the browser's own XHR drives the events */
	var X = XMLHttpRequest.prototype, open = X.open, send = X.send, tag = new WeakMap();
	X.open = function (method, url) {
		tag.set(this, { method: String(method).toUpperCase(), url: String(url) });
		return open.apply(this, arguments);
	};
	X.send = function (body) {
		var t = tag.get(this), r = t && route(t.method, t.url, body);
		if (!r) return send.apply(this, arguments);
		var text = r.ubus ? ubus(body) : r.body;
		if (r.status == 404) text = '';
		var url = URL.createObjectURL(new Blob([text], { type: r.type }));
		this.addEventListener('loadend', function () { URL.revokeObjectURL(url); }, { once: true });
		open.call(this, 'GET', url, true);
		return send.call(this);
	};
})();
