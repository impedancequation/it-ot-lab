# IT/OT Segmentation Lab

A GNS3 lab I'm building in stages to practice multi-vendor routing, IT/OT segmentation and network automation. So far only the routing base is done: two routers from different vendors running OSPF. The firewall, VLANs, automation scripts and monitoring are still to do.

## Current state

- R1: MikroTik CHR 7.23.7 (RouterOS)
- R2: VyOS 2026.09.30-1921-rolling
- One link between them, 10.0.0.0/30, both routers in OSPF area 0
- Each router advertises a loopback

| Device | Interface | Address |
|---|---|---|
| R1 | ether1 | 10.0.0.1/30 |
| R1 | lo0 (bridge) | 1.1.1.1/32 |
| R2 | eth0 | 10.0.0.2/30 |
| R2 | dum0 | 2.2.2.2/32 |

## Verification

Screenshots are in `screenshots/`. They show:

- OSPF neighbor state Full on both routers
- An OSPF route to the other router's loopback on both routers
- Ping between the loopbacks in both directions, 0% packet loss

## Config files

`configs/r1-mikrotik.rsc` is the output of `/export` on R1. `configs/r2-vyos.txt` is the output of `show configuration commands` on R2. On R2 the interface and OSPF lines are mine. The NTP, syslog and console lines are VyOS defaults. Password lines are removed from both files.

## Environment

GNS3 2.2.61 on Windows, with the GNS3 VM in VirtualBox (2 vCPU, 4 GB RAM). KVM is not available in the VM. `systeminfo` reported a hypervisor running on Windows, which probably blocks it. The nodes run in plain QEMU and take a few minutes to boot.

## Problems I ran into

- Starting a node failed with "/dev/kvm doesn't exist". I set `enable_kvm = false` under `[Qemu]` in `gns3_server.conf` on the GNS3 VM.
- The GNS3 CHR appliance wizard did not list 7.23.7. I added it as a custom version based on 7.22.1.
- Importing the VyOS appliance from the online registry failed with "appliance_id is a required property". I made a QEMU template by hand and installed VyOS from the ISO onto a blank 4 GB disk with `install image`.
- Pasting config into the telnet console cut off a few lines. I re-entered them and checked the result with `print` and `show` commands.
- The default CHR config had a DHCP client on ether1. I removed it because the link uses a static address.

## Next

VLANs, a firewall between the IT and OT zones, a Python script for config backup, and monitoring.
