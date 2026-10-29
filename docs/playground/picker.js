/*
 * Playground theme picker: a small floating button that opens a panel with every theme; picking
 * one opens the same page in that theme. Styles are inline in a shadow root, so no theme's CSS
 * reaches it and it reaches none.
 */
(function () {
	'use strict';

	var PG = window.__pg || {}, THEMES = window.__pgThemes || [];
	if (!document.body || PG.page == 'logout') return;

	var here = location.pathname.slice((PG.base + '/' + PG.theme).length) || '/cgi-bin/luci/';
	var cur = THEMES.filter(function (t) { return t.id == PG.theme; })[0] || { name: PG.theme, layout: '' };

	var css = ':host{all:initial}' +
		'*{box-sizing:border-box;font:13px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
		'button{cursor:pointer}' +
		'.fab{position:fixed;left:14px;bottom:14px;z-index:2147483647;display:flex;align-items:center;gap:8px;' +
		'padding:8px 14px 8px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.18);background:#14161c;color:#f2f4f8;' +
		'box-shadow:0 6px 24px rgba(0,0,0,.35);font-weight:600}' +
		'.fab:focus-visible,.pick a:focus-visible,.x:focus-visible{outline:2px solid #6aa8ff;outline-offset:2px}' +
		'.dot{width:18px;height:18px;border-radius:50%;background:conic-gradient(#ff5f6d,#ffc371,#47e891,#4facfe,#a66cff,#ff5f6d)}' +
		'.panel{position:fixed;left:14px;bottom:62px;z-index:2147483647;width:min(560px,calc(100vw - 28px));' +
		'max-height:min(72vh,640px);overflow:auto;border-radius:14px;background:#14161c;color:#e8ebf1;' +
		'border:1px solid rgba(255,255,255,.14);box-shadow:0 18px 60px rgba(0,0,0,.5);padding:14px 16px 16px}' +
		'.panel[hidden]{display:none}' +
		'.head{display:flex;justify-content:space-between;align-items:start;gap:12px;margin-bottom:10px}' +
		'.head b{font-size:15px;display:block}.head small{color:#a3abb9}' +
		'.x{background:none;border:0;color:#a3abb9;font-size:20px;line-height:1;padding:2px 6px}' +
		'h4{margin:12px 0 6px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#a3abb9;font-weight:700}' +
		'table{border-collapse:collapse;width:100%}td,th{padding:2px 0}th{font-size:11px;color:#a3abb9;text-align:left;font-weight:600}' +
		'.pick{display:flex;flex-wrap:wrap;gap:6px}' +
		'.pick a,td a{display:inline-block;padding:4px 10px;border-radius:999px;background:#232733;color:#e8ebf1;text-decoration:none}' +
		'.pick a:hover,td a:hover{background:#30364a}' +
		'a[aria-current]{background:#2f6fe4!important;color:#fff!important}' +
		'td:first-child{color:#e8ebf1;padding-right:8px;white-space:nowrap}' +
		'.note{margin-top:12px;color:#a3abb9;font-size:12px}' +
		'@media (max-width:600px){.fab span{display:none}.fab{padding:10px}}';

	function href(id) { return PG.base + '/' + id + here; }
	function link(t, label) {
		var a = document.createElement('a');
		a.href = href(t.id);
		a.textContent = label;
		if (t.id == PG.theme) a.setAttribute('aria-current', 'true');
		return a;
	}

	var host = document.createElement('div');
	host.id = 'pg-picker';
	var root = host.attachShadow({ mode: 'open' });
	var style = document.createElement('style');
	style.textContent = css;
	root.appendChild(style);

	var fab = document.createElement('button');
	fab.className = 'fab';
	fab.type = 'button';
	fab.setAttribute('aria-expanded', 'false');
	fab.innerHTML = '<i class="dot"></i><span></span>';
	fab.querySelector('span').textContent = cur.name + (cur.layout ? ' · ' + cur.layout : '');
	fab.setAttribute('aria-label', 'Theme: ' + fab.querySelector('span').textContent + '. Choose another theme');

	var panel = document.createElement('div');
	panel.className = 'panel';
	panel.hidden = true;
	panel.setAttribute('role', 'dialog');
	panel.setAttribute('aria-label', 'Choose a theme');
	panel.innerHTML = '<div class="head"><div><b>LuCI 21.02 theme playground</b>' +
		'<small>Same page, every theme. Recorded from a test router: nothing here is a real device, and nothing is saved.</small></div>' +
		'<button class="x" type="button" aria-label="Close">×</button></div>';

	var natives = THEMES.filter(function (t) { return t.group == 'native'; });
	var h = document.createElement('h4');
	h.textContent = 'Ported themes';
	var pick = document.createElement('div');
	pick.className = 'pick';
	natives.forEach(function (t) { pick.appendChild(link(t, t.name)); });
	panel.appendChild(h);
	panel.appendChild(pick);

	var layouts = ['Bootstrap', 'Argon', 'Aurora'], skins = {};
	THEMES.forEach(function (t) {
		if (t.group == 'reskin') (skins[t.name] = skins[t.name] || {})[t.layout] = t;
	});
	h = document.createElement('h4');
	h.textContent = 'Reskins, on three layouts';
	var table = document.createElement('table');
	table.innerHTML = '<tr><th></th>' + layouts.map(function (l) { return '<th>' + l + '</th>'; }).join('') + '</tr>';
	Object.keys(skins).sort().forEach(function (name) {
		var tr = document.createElement('tr'), td = document.createElement('td');
		td.textContent = name;
		tr.appendChild(td);
		layouts.forEach(function (l) {
			td = document.createElement('td');
			if (skins[name][l]) td.appendChild(link(skins[name][l], l));
			tr.appendChild(td);
		});
		table.appendChild(tr);
	});
	panel.appendChild(h);
	panel.appendChild(table);

	var note = document.createElement('div');
	note.className = 'note';
	note.innerHTML = 'Log in with any user name and password. <a style="color:#8ab8ff" href="' + PG.home + '">Gallery and downloads</a>';
	panel.appendChild(note);

	function toggle(open) {
		panel.hidden = !open;
		fab.setAttribute('aria-expanded', open ? 'true' : 'false');
		if (open) (panel.querySelector('a[aria-current]') || panel.querySelector('a')).focus();
	}
	fab.addEventListener('click', function () { toggle(panel.hidden); });
	panel.querySelector('.x').addEventListener('click', function () { toggle(false); fab.focus(); });
	root.addEventListener('keydown', function (ev) {
		if (ev.key == 'Escape' && !panel.hidden) { toggle(false); fab.focus(); }
	});

	root.appendChild(fab);
	root.appendChild(panel);
	document.body.appendChild(host);
})();
