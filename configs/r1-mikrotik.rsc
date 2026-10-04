# 2026-10-04 07:59:10 by RouterOS 7.23.7
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
add address=192.168.56.11/24 interface=ether2 network=192.168.56.0
/routing ospf interface-template
add area=backbone networks=10.0.0.0/30
add area=backbone networks=1.1.1.1/32 passive
