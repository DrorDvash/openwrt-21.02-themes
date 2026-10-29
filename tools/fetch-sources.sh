#!/bin/sh
# Fetch the upstream sources the generators read (into src/) and the OpenWrt 21.02.7 rootfs
# the test routers run (into work/dl/), at the exact versions the packages were made from.
# Read-only use: nothing from these trees is run, only their CSS, templates and scripts are read.
#   tools/fetch-sources.sh            everything
#   tools/fetch-sources.sh themes     one source (by its src/ name)
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/src" "$ROOT/work/dl"

# name  repository  commit  [sparse path]
SOURCES='
themes             https://github.com/vistrocity/openwrt-luci-themes.git  a407f7c5ea601ef1fd6d5013fceaf287981d0346
argon-2.3.1        https://github.com/jerrykuku/luci-theme-argon.git      f2eb62b34b6be806297ec69dbda7ffb96e16a566
luci-theme-aurora  https://github.com/eamonxg/luci-theme-aurora.git       84c27b66952e6fc4be60128067a6b88bfd34afb5
luci-theme-alpha   https://github.com/derisamedia/luci-theme-alpha.git    16e0c038c09421236319a4cc369a1f3fc98e1ef4
luci-theme-edge    https://github.com/kiddin9/luci-theme-edge.git         d72259a1ddcfc2741eb7223564db9f95fb9a0e2d
luci-theme-noobwrt https://github.com/nooblk-98/luci-theme-noobwrt.git    f227ad60bb555722be8f003d400a5a8b2169c350
uniwrt-luci        https://github.com/ox1d3x3/uniwrt-luci.git             22ff458ffbaeb424cac1a947a68f0fa26adc15e3
luci-21.02         https://github.com/openwrt/luci.git                    e4c46338b196e486a88b1a75b78e283708c82bc4 themes/luci-theme-bootstrap
luci-master        https://github.com/openwrt/luci.git                    4bfd1102236f7f737da4257ca7f6e56146fc80f6 themes/luci-theme-bootstrap
'

ROOTFS=openwrt-21.02.7-x86-64-rootfs.tar.gz
ROOTFS_URL=https://downloads.openwrt.org/releases/21.02.7/targets/x86/64/$ROOTFS
ROOTFS_SHA256=876f179f0bfde1f3e578814856a0e3518b1a7b6892090f7e855b94f61dbcd5e9

fetch() {   # name url commit [sparse]
	dir="$ROOT/src/$1"
	if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD)" = "$3" ]; then
		echo "src/$1: up to date"; return
	fi
	mkdir -p "$dir"
	git -C "$dir" init -q
	git -C "$dir" remote remove origin 2>/dev/null || true
	git -C "$dir" remote add origin "$2"
	if [ -n "${4:-}" ]; then
		git -C "$dir" sparse-checkout set "$4"
		git -C "$dir" fetch -q --depth 1 --filter=blob:none origin "$3"
	else
		git -C "$dir" fetch -q --depth 1 origin "$3"
	fi
	git -C "$dir" checkout -q FETCH_HEAD
	echo "src/$1: $3"
}

echo "$SOURCES" | while read -r name url commit sparse; do
	[ -n "$name" ] || continue
	[ $# -eq 0 ] || [ "$1" = "$name" ] || continue
	fetch "$name" "$url" "$commit" "$sparse"
done

if [ $# -eq 0 ]; then
	f="$ROOT/work/dl/$ROOTFS"
	[ -f "$f" ] || curl -fsSL -o "$f" "$ROOTFS_URL"
	echo "$ROOTFS_SHA256  $f" | sha256sum -c -
fi
