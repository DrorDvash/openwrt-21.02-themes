#!/bin/sh
# Test-only seed data so list pages have rows (run inside the container).
cat > /etc/config/wireless <<'W'
config wifi-device 'radio0'
	option type 'mac80211'
	option path 'platform/test/radio0'
	option channel '36'
	option band '5g'
	option htmode 'HE80'

config wifi-iface 'default_radio0'
	option device 'radio0'
	option network 'lan'
	option mode 'ap'
	option ssid 'OpenWrt-Test-5G'
	option encryption 'sae-mixed'
	option key 'testtest123'
W
for i in 1 2 3 4; do
	uci add firewall redirect >/dev/null
	uci set firewall.@redirect[-1].name="Test forward $i"
	uci set firewall.@redirect[-1].target=DNAT
	uci set firewall.@redirect[-1].src=wan
	uci set firewall.@redirect[-1].dest=lan
	uci set firewall.@redirect[-1].proto='tcp udp'
	uci set firewall.@redirect[-1].src_dport=$((8000 + i))
	uci set firewall.@redirect[-1].dest_ip=10.213.0.$((10 + i))
	uci set firewall.@redirect[-1].dest_port=$((80 + i))
	uci add dhcp host >/dev/null
	uci set dhcp.@host[-1].name="test-host-$i"
	uci set dhcp.@host[-1].mac="02:00:00:00:00:0$i"
	uci set dhcp.@host[-1].ip=10.213.0.$((100 + i))
done
uci commit
/etc/init.d/rpcd reload
rm -rf /tmp/luci-*
