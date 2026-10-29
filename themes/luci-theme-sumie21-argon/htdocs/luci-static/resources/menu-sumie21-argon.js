'use strict';
'require baseclass';
'require ui';

return baseclass.extend({
	/*
	 * "-- custom --" entries of dropdowns (e.g. Port Forward > Source IP).
	 * LuCI 21.02 only adds the typed value on a keydown with keyCode 13 and
	 * drops it on blur. Phone keyboards often report Enter as keyCode 229 or
	 * just close (blur), so the value never gets added. Without touching
	 * LuCI's ui.js this adds an explicit "+" button, maps the Android 229
	 * Enter to a real Enter, and on touch screens keeps the typed value when
	 * the keyboard is closed. All paths go through LuCI's own Enter handler,
	 * so its validation still applies. Desktop keyboard behaviour is unchanged.
	 */
	initCustomEntry: function() {
		var coarse = window.matchMedia('(pointer: coarse)'),
		    sel = '.cbi-dropdown input.create-item-input';

		/* LuCI only reports invalid values in a hover tooltip, which phones never show */
		var showError = function(input) {
			var li = input.parentNode,
			    msg = li.querySelector('.p21-create-error');

			if (!msg) {
				msg = E('div', { 'class': 'p21-create-error', 'role': 'alert' });
				li.appendChild(msg);
				input.addEventListener('input', function() { msg.textContent = ''; });
			}

			msg.textContent = input.getAttribute('data-tooltip') || _('Invalid value');
		};

		var commit = function(input) {
			if (!input.value.trim())
				return;

			if (input.classList.contains('cbi-input-invalid'))
				return showError(input);

			var ev = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
			Object.defineProperty(ev, 'keyCode', { value: 13 });
			Object.defineProperty(ev, 'which', { value: 13 });
			input.dispatchEvent(ev);
		};

		document.addEventListener('focusin', function(ev) {
			var input = ev.target;

			if (!input.matches || !input.matches(sel) || input.parentNode.querySelector('.p21-create-add'))
				return;

			var btn = E('button', {
				'type': 'button',
				'class': 'btn cbi-button cbi-button-add p21-create-add',
				'title': _('Add'),
				'aria-label': _('Add')
			}, [ '+' ]);

			/* keep the focus (and the phone keyboard) in the input */
			btn.addEventListener('mousedown', function(e) { e.preventDefault(); });
			btn.addEventListener('click', function(e) {
				e.preventDefault();
				e.stopPropagation();
				commit(input);
			});

			input.parentNode.classList.add('p21-create-li');
			input.parentNode.insertBefore(btn, input.nextSibling);

			/* the button makes the row taller: keep it whole inside the open list, which is
			   usually scrolled to its end here (else the input slides down out of view) */
			var ul = input.parentNode.parentNode;
			if (ul && ul.classList.contains('dropdown')) {
				var gap = input.parentNode.getBoundingClientRect().bottom - ul.getBoundingClientRect().bottom;
				if (gap > 0)
					ul.scrollTop += Math.ceil(gap) + 1;
			}
		});

		document.addEventListener('keydown', function(ev) {
			if (!ev.target.matches || !ev.target.matches(sel) || ev.key != 'Enter')
				return;

			if (ev.keyCode == 229) {
				ev.preventDefault();
				commit(ev.target);
			}
			else if (ev.isTrusted && ev.target.classList.contains('cbi-input-invalid')) {
				showError(ev.target);
			}
		}, true);

		document.addEventListener('focusout', function(ev) {
			if (coarse.matches && ev.target.matches && ev.target.matches(sel))
				commit(ev.target);
		});
	},


	__init__: function () {
		ui.menu.load().then(L.bind(this.render, this));
		this.initCustomEntry();
	},

	render: function (tree) {
		var node = tree,
			url = '',
			children = ui.menu.getChildren(tree);

		for (var i = 0; i < children.length; i++) {
			var isActive = (L.env.requestpath.length ? children[i].name == L.env.requestpath[0] : i == 0);

			if (isActive)
				this.renderMainMenu(children[i], children[i].name);
		}

		if (L.env.dispatchpath.length >= 3) {
			for (var i = 0; i < 3 && node; i++) {
				node = node.children[L.env.dispatchpath[i]];
				url = url + (url ? '/' : '') + L.env.dispatchpath[i];
			}

			if (node)
				this.renderTabMenu(node, url);
		}

		document.querySelector('a.showSide')
			.addEventListener('click', ui.createHandlerFn(this, 'handleSidebarToggle'));
		document.querySelector('.darkMask')
			.addEventListener('click', ui.createHandlerFn(this, 'handleSidebarToggle'));
	},

	handleMenuExpand: function (ev) {
		var a = ev.target, slide = a.parentNode, slide_menu = a.nextElementSibling;
		var collapse = false;

		document.querySelectorAll('.main .main-left .nav > li >ul.active').forEach(function (ul) {
			$(ul).stop(true).slideUp("fast", function () {
				ul.classList.remove('active');
				ul.previousElementSibling.classList.remove('active');
			});
			if (!collapse && ul === slide_menu) {
				collapse = true;
			}

		});

		if (!slide_menu)
			return;
		
		
		if (!collapse) {
			$(slide).find(".slide-menu").slideDown("fast",function(){
				slide_menu.classList.add('active');
				a.classList.add('active');
			});
			a.blur();
		}
		ev.preventDefault();
		ev.stopPropagation();
	},

	renderMainMenu: function (tree, url, level) {
		var l = (level || 0) + 1,
			ul = E('ul', { 'class': level ? 'slide-menu' : 'nav' }),
			children = ui.menu.getChildren(tree);

		if (children.length == 0 || l > 2)
			return E([]);

		for (var i = 0; i < children.length; i++) {
			var isActive = ((L.env.dispatchpath[l] == children[i].name) && (L.env.dispatchpath[l - 1] == tree.name)),
				submenu = this.renderMainMenu(children[i], url + '/' + children[i].name, l),
				hasChildren = submenu.children.length,
				slideClass = hasChildren ? 'slide' : null,
				menuClass = hasChildren ? 'menu' : 'food';
			if (isActive) {
				ul.classList.add('active');
				slideClass += " active";
				menuClass += " active";
			}

			ul.appendChild(E('li', { 'class': slideClass }, [
				E('a', {
					'href': L.url(url, children[i].name),
					'click': (l == 1) ? ui.createHandlerFn(this, 'handleMenuExpand') : null,
					'class': menuClass,
					'data-title': hasChildren ? children[i].title.replace(" ", "_") : children[i].title.replace(" ", "_"),
				}, [_(children[i].title)]),
				submenu
			]));
		}

		if (l == 1) {
			document.querySelector('#mainmenu').appendChild(ul);
			document.querySelector('#mainmenu').style.display = '';

		}
		return ul;
	},

	renderTabMenu: function (tree, url, level) {
		var container = document.querySelector('#tabmenu'),
			l = (level || 0) + 1,
			ul = E('ul', { 'class': 'tabs' }),
			children = ui.menu.getChildren(tree),
			activeNode = null;

		if (children.length == 0)
			return E([]);

		for (var i = 0; i < children.length; i++) {
			var isActive = (L.env.dispatchpath[l + 2] == children[i].name),
				activeClass = isActive ? ' active' : '',
				className = 'tabmenu-item-%s %s'.format(children[i].name, activeClass);

			ul.appendChild(E('li', { 'class': className }, [
				E('a', { 'href': L.url(url, children[i].name) }, [_(children[i].title)])
			]));

			if (isActive)
				activeNode = children[i];
		}

		container.appendChild(ul);
		container.style.display = '';

		if (activeNode)
			container.appendChild(this.renderTabMenu(activeNode, url + '/' + activeNode.name, l));

		return ul;
	},

	handleSidebarToggle: function (ev) {
		var showside = document.querySelector('a.showSide'),
			sidebar = document.querySelector('#mainmenu'),
			darkmask = document.querySelector('.darkMask'),
			scrollbar = document.querySelector('.main-right');

		if (showside.classList.contains('active')) {
			showside.classList.remove('active');
			sidebar.classList.remove('active');
			scrollbar.classList.remove('active');
			darkmask.classList.remove('active');
		}
		else {
			showside.classList.add('active');
			sidebar.classList.add('active');
			scrollbar.classList.add('active');
			darkmask.classList.add('active');
		}
	}
});
