#!/bin/sh
# Stop all test containers (luci21-opt, luci21-opt-N), the network and the iptables rules.
for c in $(docker ps -a --format '{{.Names}}' | grep -E '^luci21-opt(-[0-9]+)?$'); do
	docker rm -f "$c" >/dev/null && echo "removed $c"
done
docker network rm luci21opt >/dev/null 2>&1
iptables -D DOCKER-USER -s 10.213.0.0/24 -j DROP 2>/dev/null
iptables -D DOCKER-USER -s 10.213.0.0/24 -d 192.168.8.0/24 -j DROP 2>/dev/null
true
