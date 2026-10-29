/* luci-theme-sumie21-aurora: generated from luci-theme-rack21's menu-rack21.js initCustomEntry() */
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
(function() {
'use strict';
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
})();
