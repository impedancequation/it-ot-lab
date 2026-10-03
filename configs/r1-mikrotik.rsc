[admin@CHR] > /export
# 2026-10-03 08:15:30 by RouterOS 7.23.7
#
/interface bridge
add name=lo0
/interface ethernet
set [ find default-name=ether1 ] disable-running-check=no
set [ find default-name=ether2 ] disable-running-check=no
set [ find default-name=ether3 ] disable-running-check=no
set [ find default-name=ether4 ] disable-running-check=no
/routing ospf instance
add name=ospf1 router-id=1.1.1.1
/routing ospf area
add instance=ospf1 name=backbone
/ip address
add address=10.0.0.1/30 interface=ether1 network=10.0.0.0
add address=1.1.1.1 interface=lo0 network=1.1.1.1
/ip dhcp-client
add interface=ether1 name=client1
/routing ospf interface-template
add area=backbone networks=10.0.0.0/30
add area=backbone networks=1.1.1.1/32 passive
[admin@CHR] > /ip dhcp-client remove client 1
bad parameter 1 (line 1 column 32)
[admin@CHR] > /ip dhcp-client remove client1
[admin@CHR] > /ip dhcp-client print