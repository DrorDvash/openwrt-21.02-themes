#!/bin/sh
# Start an OpenWrt 21.02.7 x86-64 test container (Option A: Docker).
# Fully offline: the subnet is DROPped in DOCKER-USER, ports are bound to 127.0.0.1 only.
#   INSTANCE=0 (default): luci21-opt    10.213.0.2   http://127.0.0.1:18180  ssh 2322
#   INSTANCE=N:           luci21-opt-N  10.213.0.2+N http://127.0.0.1:18180+N ssh 2322+N
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
N=${INSTANCE:-0}
IMG=luciport-opt:21.02.7
NAME=luci21-opt; [ "$N" = 0 ] || NAME=luci21-opt-$N
NET=luci21opt
SUBNET=10.213.0.0/24
IP=10.213.0.$((2 + N))
HTTP=$((18180 + N))
SSH=$((2322 + N))
ROOTFS=${ROOTFS:-$HERE/../work/dl/openwrt-21.02.7-x86-64-rootfs.tar.gz}

docker image inspect $IMG >/dev/null 2>&1 || docker import "$ROOTFS" $IMG
docker network inspect $NET >/dev/null 2>&1 || \
	docker network create --subnet $SUBNET -o com.docker.network.bridge.name=br-$NET $NET
# Hard rule 1: nothing from the test subnet may be forwarded anywhere (incl. 192.168.8.0/24).
iptables -C DOCKER-USER -s $SUBNET -j DROP 2>/dev/null || iptables -I DOCKER-USER -s $SUBNET -j DROP
iptables -C DOCKER-USER -s $SUBNET -d 192.168.8.0/24 -j DROP 2>/dev/null || \
	iptables -I DOCKER-USER -s $SUBNET -d 192.168.8.0/24 -j DROP

docker rm -f $NAME >/dev/null 2>&1 || true
docker create --name $NAME --hostname OpenWrt --network $NET --ip $IP \
	--cap-add NET_ADMIN --cap-add NET_RAW --cap-add SYS_ADMIN \
	--tmpfs /tmp:exec --tmpfs /run \
	-p 127.0.0.1:$HTTP:80 -p 127.0.0.1:$SSH:22 \
	$IMG /sbin/init >/dev/null
# LAN = the container's docker address on plain eth0, so netifd keeps the published ports working.
sed "s/10\.213\.0\.2'/$IP'/" "$HERE/network" > "$HERE/.network.$N"
docker cp "$HERE/.network.$N" $NAME:/etc/config/network
docker cp "$HERE/90-testenv" $NAME:/etc/uci-defaults/90-testenv
docker start $NAME >/dev/null
sleep 8
docker cp "$HERE/seed.sh" $NAME:/root/seed.sh && docker exec $NAME sh /root/seed.sh
if [ -f "$HERE/test-root-password.env" ]; then
	. "$HERE/test-root-password.env"
	# on stdin, not inside a command line: any character in the password is fine
	printf '%s\n%s\n' "$LUCI_PASS" "$LUCI_PASS" | docker exec -i $NAME passwd root >/dev/null 2>&1
fi
echo "started $NAME on http://127.0.0.1:$HTTP"
