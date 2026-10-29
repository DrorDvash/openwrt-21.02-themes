# Building the themes

How the packages are made, tested and published. To just use the themes, see the README.

## What's where

| Folder | What |
|---|---|
| `themes/` | one folder per package (`luci-theme-<name>`): its CSS, templates and scripts |
| `tools/` | the generator and the tests (`port-theme.py` is the one you run) |
| `testenv/` | scripts that start a test router (OpenWrt 21.02 in Docker) on your own computer, for the tests; the website doesn't use it |
| `docs/` | the website: gallery and playground |

## Set up (once)

```sh
tools/fetch-sources.sh                               # the upstream themes, at the versions used here
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
.venv/bin/playwright install chromium                # only needed for the tests
```

## Build a package

```sh
.venv/bin/python tools/port-theme.py glass                      # Glass on the Bootstrap layout
.venv/bin/python tools/port-theme.py glass --baseline argon     # ... on the Argon layout
.venv/bin/python tools/port-theme.py glass --baseline aurora    # ... on the Aurora layout
.venv/bin/python tools/port-theme.py edge                       # a ported theme: aurora, alpha, edge, noobwrt, uniwrt
```

The package lands in `dist/ports/<name>/`, and every package also in `dist/all-ipks/`.
`--force` regenerates a theme's folder; its own fixes in `css/35-*.css` are kept.

## Test it

The tests run in a local, offline OpenWrt 21.02 container (Linux, Docker). Put a password for
it in `testenv/test-root-password.env` first: `LUCI_PASS='something'`.

```sh
sudo sh testenv/up.sh                                           # test router on http://127.0.0.1:18180
SUDO=sudo .venv/bin/python tools/port-theme.py glass --test     # everything, ~5 min
cat dist/ports/glass21/TEST-SUMMARY.txt
sudo sh testenv/down.sh                                         # stop it
```

`--test` installs the package, checks the pages on a phone and a desktop (layout, menus,
contrast in light and dark), compares saving settings against the default theme, and removes
it again. `--quick` checks only contrast, for fixing colours:

```sh
.venv/bin/python tools/port-theme.py glass --quick              # measure
.venv/bin/python tools/contrast-fix.py glass                    # writes fixes into css/35-*.css
```

Look at the screenshots after a contrast fix: when no text colour works, the tool darkens the
background instead, and on a broad selector that can recolour a whole table. Replace such a rule
with a narrow one written by hand, above the tool's block in `css/35-*.css`.

`tools/test-matrix.py` tests every package at once (on test routers 1-5) and writes a results
table to `dist/ports/MATRIX.md`.

## A new theme upstream

```sh
git -C src/themes pull
.venv/bin/python tools/port-theme.py <new-theme> --test
```

## The website

```sh
.venv/bin/python tools/showcase/capture.py --workers 5          # record every package on test routers 1-5
.venv/bin/python tools/showcase/build.py --base /openwrt-21.02-themes --refresh-static   # the playground
.venv/bin/python tools/showcase/gallery.py --base /openwrt-21.02-themes                  # the gallery
.venv/bin/python tools/showcase/readme.py                       # README.md
```

The playground needs no server: it runs LuCI's pages in the visitor's browser with answers
recorded once from the test router. `tools/showcase/overlay.json` holds the made-up device it
shows.
