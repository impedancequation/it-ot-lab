# IT/OT Segmentation Lab

A GNS3 lab I'm building in stages to practice multi-vendor routing, IT/OT segmentation and network automation. Done so far: OSPF between two routers from different vendors, an IT zone and an OT zone separated by a firewall, and a Python script that backs up both routers. Monitoring is still to do.

## Current state

- R1: MikroTik CHR 7.23.7 (RouterOS)
- R2: VyOS 2026.09.30-1921-rolling
- One link between them, 10.0.0.0/30, both routers in OSPF area 0
- Each router advertises a loopback

| Device | Interface    | Address     |
| ------ | ------------ | ----------- |
| R1     | ether1       | 10.0.0.1/30 |
| R1     | lo0 (bridge) | 1.1.1.1/32  |
| R2     | eth0         | 10.0.0.2/30 |
| R2     | dum0         | 2.2.2.2/32  |

## Verification

Screenshots will be added to `screenshots/`. They show:

- OSPF neighbor state Full on both routers
- An OSPF route to the other router's loopback on both routers
- Ping between the loopbacks in both directions, 0% packet loss

## Config files

`configs/r1-mikrotik.rsc` is the output of `/export` on R1. `configs/r2-vyos.txt` is the output of `show configuration commands` on R2. Both were produced by the backup script from Phase 2. On R2 the interface, OSPF, VLAN, firewall and SSH lines are mine. The NTP, syslog and console lines are VyOS defaults. Password lines are removed from both files.

## Environment

GNS3 2.2.61 on Windows, with the GNS3 VM in VirtualBox (2 vCPU, 4 GB RAM). KVM is not available in the VM. `systeminfo` reported a hypervisor running on Windows, which probably blocks it. The nodes run in plain QEMU and take a few minutes to boot.

## Problems I ran into

- Starting a node failed with "/dev/kvm doesn't exist". I set `enable_kvm = false` under `[Qemu]` in `gns3_server.conf` on the GNS3 VM.
- The GNS3 CHR appliance wizard did not list 7.23.7. I added it as a custom version based on 7.22.1.
- Importing the VyOS appliance from the online registry failed with "appliance_id is a required property". I made a QEMU template by hand and installed VyOS from the ISO onto a blank 4 GB disk with `install image`.
- Pasting config into the telnet console cut off a few lines. I re-entered them and checked the result with `print` and `show` commands.
- The default CHR config had a DHCP client on ether1. I removed it because the link uses a static address.

## Phase 2: IT/OT segmentation and config backup script

Phase 1 left me with two routers running OSPF: MikroTik CHR (R1) and VyOS (R2). In Phase 2 I split the network into an IT zone and an OT zone with a firewall between them, and wrote a Python script that backs up both routers.

Everything runs in GNS3 on a laptop, with KVM disabled, so boot times and SSH logins are slow.

### What I added to the topology

- **SW1**: GNS3 Ethernet switch. Port 0 is a trunk to R2 eth1, port 1 is access VLAN 10, port 2 is access VLAN 20.
- **ENG-WS** (VPCS): stands in for an engineering workstation in the IT zone.
- **PLC1** (VPCS): stands in for a PLC in the OT zone. It is only a simulated host. No PLC or Modbus software runs on it.
- **SW-MGMT and Cloud1**: a small management network so my Windows PC can reach both routers over SSH.

| Device | Interface | Address | Purpose |
|---|---|---|---|
| R2 (VyOS) | eth1.10 | 10.10.10.1/24 | IT zone gateway (VLAN 10) |
| R2 (VyOS) | eth1.20 | 10.20.20.1/24 | OT zone gateway (VLAN 20) |
| ENG-WS | | 10.10.10.10/24 | IT host |
| PLC1 | | 10.20.20.10/24 | OT host |
| R1 (MikroTik) | ether2 | 192.168.56.11/24 | management |
| R2 (VyOS) | eth2 | 192.168.56.12/24 | management |

### Segmentation

R2 is both the router and the firewall for the two zones. I used the VyOS zone-based firewall: zone IT is eth1.10 and zone OT is eth1.20.

IT to OT:
1. Accept established and related traffic.
2. Accept TCP port 502 from 10.10.10.10 to 10.20.20.10.
3. Accept ICMP from 10.10.10.10 to 10.20.20.10.
4. Everything else is dropped and logged.

OT to IT:
1. Accept established and related traffic (replies only).
2. Everything else is dropped and logged.

What I tested:

- Before the firewall, ENG-WS could ping PLC1 through R2.
- After the firewall, ENG-WS can still ping PLC1. PLC1 pinging ENG-WS times out, and `show log firewall` shows those packets dropped by the OT-to-IT rule set.
- I did not test the TCP 502 rule. I never ran a Modbus client, so that rule is configured and visible in the config, but untested.

### Config backup script

`scripts/backup_configs.py` uses Netmiko to connect to R1 (`mikrotik_routeros`) and R2 (`vyos`) over SSH. It runs `/export` on R1 and `show configuration commands` on R2, and saves each result in `backups/<date>_<time>/`.

Passwords are not stored in the script. It asks for them when it starts, or reads them from the environment variables `LAB_R1_PASS` and `LAB_R2_PASS`. Lines that contain `password` or `system id` are removed before the file is written.

### Timing

I measured the manual way with a stopwatch: from opening the console session and logging in until the command finished printing. This does not include copying the output into a file, so the real manual time is longer than shown.

| Method | R1 | R2 | Both |
|---|---|---|---|
| Manual (login to command done) | 26.86 s | 18.22 s | about 45 s |
| Script, run 1 (login to files saved) | | | 34.2 s |
| Script, run 2 (login to files saved) | | | 26.3 s |

For two devices the script is only a little faster. The difference is that nobody has to sit at the console, and nothing is copied by hand. I expect the gap to grow with more devices because the manual steps repeat for each one, but I only measured two.

### Problems I ran into in Phase 2

- My Windows PC could not reach the routers until I set Promiscuous Mode to Allow All on Adapter 1 of the GNS3 VM in VirtualBox.
- Windows OpenSSH to MikroTik failed with "message authentication code incorrect" until I forced the `aes128-ctr` cipher. Netmiko connected without any change.
- The first backup showed duplicate OSPF entries and a leftover DHCP client on R1. I found it by reading the backup file, removed the extra entries, and ran the backup again. I do not know how the duplicates got there.

### Not done yet

- Monitoring (Grafana with LibreNMS or PRTG)
- Pushing a config change to several devices at once
- Log anomaly detection
- A third vendor (I do not have a legal Cisco or Juniper image)
- A real Modbus test for the TCP 502 rule
- Screenshots for Phase 2