# Phase 3 log: pushing a config change to both routers

Date: 2026-10-05. This is the full step-by-step record of Phase 3 so far: every step, the commands I ran, what came back, the mistakes I made and the problems I hit. The short version is in the Phase 3 section of `README.md`.

All router console steps were done in Solar-PuTTY (telnet to the GNS3 VM) or over SSH from Windows PowerShell in `D:\it-ot-lab`. Passwords are not shown anywhere in this log.

## Contents

0. Starting point
1. Banner syntax test on R1
2. Banner syntax test on R2
3. First "before" backup
4. Second backup fails on R2
5. Manual SSH to R2
6. Removing the banner and testing again
7. Adding a config check to the backup script
8. First push script and its failure
9. Debug script for R2
10. Push with a longer timeout, and the before/after check
11. Cleaning up the debug files
12. Lab restart: kernel panic and port error
13. Manual timing
14. Script timing from a clean state
15. Prompt text at the end of the R1 backup
16. README block
17. Results table
18. What is still not done
19. My own mistakes during the session

---

## 0. Starting point

Phase 1 and 2 were finished: MikroTik CHR 7.23.7 (R1) and VyOS 2026.09.30-1921-rolling (R2), OSPF area 0, IT zone VLAN 10 and OT zone VLAN 20 behind the VyOS zone-based firewall, and `scripts/backup_configs.py` (commit `a9c6dc4`).

I decided to start Phase 3 with the repo cleanup (screenshots, topology diagram, README). I took one screenshot of the GNS3 canvas, then decided to do all screenshots and the diagram at the end when the whole project is finished. So I moved on to item 2 of Phase 3: pushing a config change to several devices from Python.

State of the lab when I started:

- GNS3 VM running, GNS3 stable, CPU low.
- Nodes started in this order: VyOS-1 first, MikroTik CHR after the CPU dropped, then ENG-WS and PLC1. I did not use Start All.
- Canvas: R1, R2, SW1, SW-MGMT, Cloud1, ENG-WS, PLC1 all green, all links green.
- Servers Summary at that moment: GNS3 VM CPU 41.3%, RAM 55.7%. Laptop CPU 22.6%, RAM 88.6%.
- Consoles: MikroTik telnet 192.168.56.101:5011, VyOS 192.168.56.101:5013, ENG-WS 5016, PLC1 5018.

The change I wanted to push had to be small and unable to touch routing or the firewall. First idea: a login banner on both routers.

## 1. Banner syntax test on R1

I tested the syntax by hand first, one router at a time, before putting anything in a script.

On the MikroTik console:

```
[admin@CHR] > /system note set note="Authorized access only. Lab device." show-at-login=yes
[admin@CHR] > /system note print
      show-at-login: yes
  show-at-cli-login: no
               note: Authorized access only. Lab device.
```

Result: accepted, `show-at-login: yes`.

## 2. Banner syntax test on R2

On the VyOS console I typed `configure` and got:

```
vyos@vyos# configure
vbash:
  Invalid command: [configure]
```

Reason: the console was still in configuration mode from an earlier session (the prompt was `vyos@vyos#`), so `configure` was rejected. Harmless.

I then set the banner and looked at the pending change:

```
vyos@vyos# compare | no-more
[system login]
+ banner {
+     pre-login "Authorized access only. Lab devicee."
+ }
```

The text has a double "e" (`devicee`). The paste into the telnet console added it. I committed anyway to confirm the syntax:

```
vyos@vyos# commit
vyos@vyos# save
vyos@vyos# exit
vyos@vyos:~$ show configuration commands | match banner
set system login banner pre-login 'Authorized access only. Lab devicee.'
```

Then I fixed the typo. I typed `configure`, set the correct text, and compared:

```
vyos@vyos# compare | no-more
[system login banner]
- pre-login "Authorized access only. Lab devicee."
+ pre-login "Authorized access only. Lab device."
```

After `commit`, `save` and `exit`:

```
vyos@vyos:~$ show configuration commands | match banner
set system login banner pre-login 'Authorized access only. Lab device.'
```

(The terminal echo was messy in that paste, but the config line itself was correct.)

Syntax confirmed on both vendors:

| Device | Command |
|---|---|
| R1 (RouterOS) | `/system note set note="..." show-at-login=yes` |
| R2 (VyOS) | `set system login banner pre-login "..."` |

## 3. First "before" backup

Plan: take a backup before the push so I have a before/after comparison.

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_072244\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_072244\r2-vyos.txt
2/2 devices backed up in 34.0 s
```

I typed the placeholder `<folder>` literally in the next command and PowerShell said the path does not exist. That was my mistake, not a lab problem. With the real folder name:

```
PS D:\it-ot-lab> Select-String -Path backups\2026-10-05_072244\* -Pattern "note|banner"

backups\2026-10-05_072244\r1-mikrotik.rsc:21:/system note
backups\2026-10-05_072244\r1-mikrotik.rsc:22:set note="Authorized access only. Lab device."
```

The R1 banner is in the file. There was nothing from R2, even though the banner was clearly on R2. I checked the R2 file directly:

```
PS D:\it-ot-lab> Select-String -Path backups\2026-10-05_072244\r2-vyos.txt -Pattern "banner"
(no output)
PS D:\it-ot-lab> (Get-Content backups\2026-10-05_072244\r2-vyos.txt).Count
5
PS D:\it-ot-lab> Get-Content backups\2026-10-05_072244\r2-vyos.txt
vyos@vyos:~$

vyos@vyos:~$

PS D:\it-ot-lab> Get-ChildItem backups\*\r2-vyos.txt | Select-Object FullName, Length

FullName                                           Length
--------                                           ------
D:\it-ot-lab\backups\2026-10-04_145908\r2-vyos.txt   3312
D:\it-ot-lab\backups\2026-10-05_072244\r2-vyos.txt     76
```

Finding: the R2 "backup" was 76 bytes and only held two prompts, but the script had printed `[ OK ]`. The script reported success on an empty result. This was a real weakness in my script.

(I opened Explorer screenshots of the backups folder at this point, but they only showed that the folder existed and did not answer the question.)

## 4. Second backup fails on R2

I ran the backup again to see whether it was a one-time glitch:

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_072706\r1-mikrotik.rsc
[FAIL] r2-vyos:
Pattern not detected: '\x1b\\[\\?2004hvyos@vyos:\\~\\$\\ set\\ terminal\\ length\\ 0' in output.
...
1/2 devices backed up in 83.7 s
```

This time the failure was visible. Netmiko connected to R2 but did not get the expected answer to `set terminal length 0`. The R2 file sizes did not change (3312 and 76). The previous run probably hit the same problem, but it got saved as OK with empty content.

The only thing I had changed on R2 since the last good backup (2026-10-04, 3312 bytes) was the pre-login banner. That was a suspect, not proof.

## 5. Manual SSH to R2

I checked that R2 itself was fine:

```
PS D:\it-ot-lab> ssh vyos@192.168.56.12
Authorized access only. Lab device.
vyos@192.168.56.12's password:
Welcome to VyOS!
...
vyos@vyos:~$ show configuration commands | head -5
set firewall ipv4 name IT-to-OT default-action 'drop'
set firewall ipv4 name IT-to-OT default-log
set firewall ipv4 name IT-to-OT rule 10 action 'accept'
set firewall ipv4 name IT-to-OT rule 10 state 'established'
set firewall ipv4 name IT-to-OT rule 10 state 'related'
vyos@vyos:~$ exit
```

The banner text shows before the password prompt, login works, and the full config comes back. So R2 is not broken and not extremely slow. The problem is in how Netmiko talks to it.

## 6. Removing the banner and testing again

Test of the banner idea: remove it and run the backup again.

```
vyos@vyos:~$ configure
vyos@vyos# delete system login banner pre-login
vyos@vyos# compare | no-more
[system login banner]
- pre-login "Authorized access only. Lab device."
vyos@vyos# commit
vyos@vyos# save
vyos@vyos# exit
```

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_073318\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_073318\r2-vyos.txt
2/2 devices backed up in 23.5 s

PS D:\it-ot-lab> Get-ChildItem backups\*\r2-vyos.txt | Select-Object FullName, Length
D:\it-ot-lab\backups\2026-10-04_145908\r2-vyos.txt   3312
D:\it-ot-lab\backups\2026-10-05_072244\r2-vyos.txt     76
D:\it-ot-lab\backups\2026-10-05_073318\r2-vyos.txt   3337
```

The R2 backup went back to normal size. I compared it with yesterday's file:

```
PS D:\it-ot-lab> Compare-Object (Get-Content backups\2026-10-04_145908\r2-vyos.txt) (Get-Content backups\2026-10-05_073318\r2-vyos.txt)

InputObject             SideIndicator
-----------             -------------
set system login banner =>
```

The 25-byte difference was one leftover line, `set system login banner`. `delete ... pre-login` removed the text but left an empty `banner` node. I removed it:

```
vyos@vyos# delete system login banner
vyos@vyos# compare | no-more
[system login]
- banner {
- }
vyos@vyos# commit
vyos@vyos# save
vyos@vyos# exit
vyos@vyos:~$ show configuration commands | match banner
(no output)
```

R2 was back to the same config as the 2026-10-04 backup. The R1 login note stayed in place, and Netmiko works fine with it.

What I can say: with the R2 pre-login banner, the backup failed twice; without it, the backup worked once. That is one test each way. I do not know the exact mechanism. My guess is that the banner text before the password prompt confuses how Netmiko reads the prompt.

## 7. Adding a config check to the backup script

To stop the script from calling an empty result a success, I added an `expect` text to each device and a check in `backup()`:

- R1: `"expect": "/interface"`
- R2: `"expect": "set interfaces"`

```python
    if dev["expect"] not in output:
        print(
            f"[FAIL] {dev['name']}: output does not look like a config "
            f"({len(output)} chars), file not saved"
        )
        return False
```

I made edits 1 and 2 myself and uploaded the file; the full file with edit 3 was then pasted in. First run with the check:

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_074840\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_074840\r2-vyos.txt
2/2 devices backed up in 25.8 s
```

I only tested the success path. The failure path (empty output rejected) did not trigger in this run.

Backup `2026-10-05_074840` is my "before" baseline: R1 with only the login note, R2 without a banner, nothing else changed.

## 8. First push script and its failure

Since the banner idea broke Netmiko on R2, I changed the pushed change to an interface description on the R1-R2 link:

| Device | Commands |
|---|---|
| R1 | `/interface ethernet set ether1 comment="to-R2-eth0"` |
| R2 | `set interfaces ethernet eth0 description 'to-R1-ether1'`, `commit`, `save` |

I created `scripts/push_config.py` with Netmiko `send_config_set`, error words in the output (`invalid`, `failure`, `expected end of command`, `not valid`) treated as a failure, and the VyOS config mode exited with `exit_config_mode()`. I saved it, and Explorer showed it next to `backup_configs.py`.

First run:

```
PS D:\it-ot-lab> python scripts\push_config.py
[ OK ] r1-mikrotik: 1 commands sent
[FAIL] r2-vyos:

Pattern not detected: '(?:\x1b\\[\\?2004hvyos@vyos.*$|#.*$)' in output.
...
1/2 devices updated in 42.5 s
```

R1 changed. R2 failed while entering config mode. I did not know whether any command had reached R2, so I checked R2 directly.

My mistake here: I was already on the VyOS console and typed `ssh vyos@192.168.56.12`, so VyOS connected to itself. The host key question appeared and my next command was pasted into the yes/no prompt, so I typed `yes` and then exited. No harm done.

Then in the console:

```
vyos@vyos:~$ show configuration commands | match description
set interfaces ethernet eth1 vif 10 description 'IT-zone'
set interfaces ethernet eth1 vif 20 description 'OT-zone'
set interfaces ethernet eth2 description 'MGMT'
```

No description on eth0, so R2 was unchanged. The script failed before sending the first `set`. Netmiko's `Last login ... from 192.168.56.1` line in the SSH banner showed that the script had connected.

Side note: the push has no rollback. After this run R1 had the change and R2 did not.

## 9. Debug script for R2

To see what R2 sends back, I wrote a read-only script that only enters config mode and leaves it (no `set`, no `commit`), with a 60 second timeout and a session log:

```python
ssh = ConnectHandler(
    device_type="vyos", host="192.168.56.12", username="vyos",
    password=pw, session_log="r2_session.log", read_timeout_override=60,
)
print("connected, prompt:", repr(ssh.find_prompt()))
try:
    ssh.config_mode()
    print("config mode OK:", ssh.check_config_mode())
    ssh.exit_config_mode()
except Exception as err:
    print("FAIL:", err)
ssh.disconnect()
```

I saved it as `debug_r2.py`, but it ended up in the `scripts` folder instead of `D:\it-ot-lab`, so `python debug_r2.py` said "No such file or directory" twice. Running it with the right path worked:

```
PS D:\it-ot-lab> python scripts\debug_r2.py
connected, prompt: '\x1b[?2004h'
config mode OK: True
```

The session log showed `configure` entering the `[edit]` prompt and `exit` leaving it, with a lot of empty prompts in between. Netmiko had masked the hostname and some words in the log.

Findings:

- Config mode works with a 60 second timeout.
- The only difference from the failed push was the timeout. The push script used the default, which is much shorter. R2 runs without KVM and answers slowly. This is my best explanation, not something I proved in isolation.
- `find_prompt` returns `'\x1b[?2004h'` instead of `vyos@vyos`. It is a terminal control code from VyOS rolling. It did not stop config mode from working.

## 10. Push with a longer timeout, and the before/after check

I added one line to `push()`:

```python
    conn["read_timeout_override"] = 60
```

```
PS D:\it-ot-lab> python scripts\push_config.py
[ OK ] r1-mikrotik: 1 commands sent
[ OK ] r2-vyos: 3 commands sent
2/2 devices updated in 76.3 s
```

`[ OK ]` only means the routers printed no error. To check the real result I took an "after" backup and compared it with the `074840` baseline:

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_080821\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_080821\r2-vyos.txt
2/2 devices backed up in 26.5 s

PS D:\it-ot-lab> $after = (Get-ChildItem backups | Sort-Object Name | Select-Object -Last 1).Name; $after
2026-10-05_080821
```

R1:

```
# 2026-10-05 01:08:28 by RouterOS 7.23.7                                     =>
set [ find default-name=ether1 ] comment=to-R2-eth0 disable-running-check=no =>
# 2026-10-05 00:48:45 by RouterOS 7.23.7                                     <=
set [ find default-name=ether1 ] disable-running-check=no                    <=
```

R2:

```
set interfaces ethernet eth0 description 'to-R1-ether1'                      =>
```

(`<=` is only in the before file, `=>` only in the after file. The two `#` lines on R1 are the export timestamps, not config changes.)

Result: R1 changed by the `ether1` comment only, R2 by the one description line, and nothing else. OSPF, VLANs and the firewall were not touched. The 76.3 s is not used for the final timing because R1 already had the comment from the failed first run.

## 11. Cleaning up the debug files

```
PS D:\it-ot-lab> Remove-Item scripts\debug_r2.py, r2_session.log
PS D:\it-ot-lab> Get-ChildItem scripts; Get-ChildItem *.log

-a----  10/5/2026   7:47 AM   2730 backup_configs.py
-a----  10/5/2026   8:05 AM   2458 push_config.py
```

Only the two real scripts are left, and there is no `.log` file in `D:\it-ot-lab`.

## 12. Lab restart: kernel panic and port error

I had shut the lab down for a while and started it again. MikroTik started fine and booted normally in its console. VyOS hit a kernel panic during boot in its console. I closed the console and stopped the node, and when I started it again GNS3 showed:

```
error while starting VyOS-1: Could not start Telnet QEMU console [Errno 98] error while attempting to bind on address ('0.0.0.0', 5013): [errno 98] address already in use
```

Solar-PuTTY showed "Disconnect (host hard-reset)!" on the VyOS tab, and the console would not open.

I did not find the cause of the panic. My guess is that the CPU of the GNS3 VM was full while two nodes booted (no KVM), but I did not confirm it. The panic happens before the config is read, so the config should be safe. The Errno 98 is the old VyOS process still holding console port 5013.

What I did:

1. Stopped all nodes in GNS3 and saved with Ctrl+S.
2. Closed the VyOS and MikroTik tabs in Solar-PuTTY.
3. Closed GNS3.
4. In VirtualBox: GNS3 VM, Close, ACPI Shutdown.
5. Started the GNS3 VM, waited for `IP: 192.168.56.101 PORT: 80`.
6. Opened GNS3, started VyOS alone first, then MikroTik, then the VPCS nodes.

After that both routers came up. I did not try the `noapic` boot option.

Persistence check after the restart:

```
[admin@CHR] > /interface ethernet print where name=ether1
Flags: R - RUNNING
Columns: NAME, MTU, MAC-ADDRESS, ARP
#   NAME     MTU  MAC-ADDRESS        ARP
;;; to-R2-eth0
0 R ether1  1500  0C:54:EB:19:00:00  enabled

vyos@vyos:~$ show configuration commands | match description
set interfaces ethernet eth0 description 'to-R1-ether1'
set interfaces ethernet eth1 vif 10 description 'IT-zone'
set interfaces ethernet eth1 vif 20 description 'OT-zone'
set interfaces ethernet eth2 description 'MGMT'
```

Both changes survived the restart, and the kernel panic did not damage the R2 config.

I also asked whether closing a Solar-PuTTY tab could cause boot problems. It cannot: closing a tab only drops the telnet session from Windows. The routers keep running in GNS3. The earlier boot problems came from starting and stopping nodes in GNS3, not from closing tabs.

## 13. Manual timing

To compare fairly, I removed the change from both routers first. This part was not timed.

R1:

```
[admin@CHR] > /interface ethernet set ether1 comment=""
[admin@CHR] > /interface ethernet print where name=ether1
Flags: R - RUNNING
Columns: NAME, MTU, MAC-ADDRESS, ARP
#   NAME     MTU  MAC-ADDRESS        ARP
0 R ether1  1500  0C:54:EB:19:00:00  enabled
```

R2:

```
vyos@vyos:~$ configure
vyos@vyos# delete interfaces ethernet eth0 description
vyos@vyos# compare | no-more
[interfaces ethernet eth0]
- description "to-R1-ether1"
vyos@vyos# commit
vyos@vyos# save
vyos@vyos# exit
vyos@vyos:~$ show configuration commands | match description
set interfaces ethernet eth1 vif 10 description 'IT-zone'
set interfaces ethernet eth1 vif 20 description 'OT-zone'
set interfaces ethernet eth2 description 'MGMT'
```

Method for the manual measurement, the same as for the manual backup timing in Phase 2: stopwatch (Windows Clock app) starts when I open the console session, I log in, type the commands by hand (no paste), and stops when the prompt comes back. Checking the result is not timed. I logged out with `/quit` (MikroTik) and `exit` (VyOS) and closed the tabs before each run, so the login was part of the time.

- R1: `/interface ethernet set ether1 comment="to-R2-eth0"`. Stopwatch: **17.26 s**.
- R2: `configure`, `set interfaces ethernet eth0 description 'to-R1-ether1'`, `commit`, `save`, `exit`. The stopwatch was reset to 0 before this run. Stopwatch: **1:19.03**, so **79.03 s**.

Check after stopping the stopwatch:

```
[admin@CHR] > /interface ethernet print where name=ether1
;;; to-R2-eth0
0 R ether1  1500  0C:54:EB:19:00:00  enabled

vyos@vyos:~$ show configuration commands | match description
set interfaces ethernet eth0 description 'to-R1-ether1'
set interfaces ethernet eth1 vif 10 description 'IT-zone'
set interfaces ethernet eth1 vif 20 description 'OT-zone'
set interfaces ethernet eth2 description 'MGMT'
```

Both changes were in place, so the manual numbers are valid. Manual total: 17.26 + 79.03 = about 96.3 s.

## 14. Script timing from a clean state

I removed the change from both routers again with the same commands as before (not timed) and checked both:

```
[admin@CHR] > /interface ethernet set ether1 comment=""
[admin@CHR] > /interface ethernet print where name=ether1
0 R ether1  1500  0C:54:EB:19:00:00  enabled      (no comment line)

vyos@vyos:~$ show configuration commands | match description
set interfaces ethernet eth1 vif 10 description 'IT-zone'
set interfaces ethernet eth1 vif 20 description 'OT-zone'
set interfaces ethernet eth2 description 'MGMT'
```

Script run:

```
PS D:\it-ot-lab> python scripts\push_config.py
[ OK ] r1-mikrotik: 1 commands sent
[ OK ] r2-vyos: 3 commands sent
2/2 devices updated in 60.6 s
```

The time the script prints starts after the passwords are typed and ends when both devices are done. Then the before/after check against the `074840` baseline:

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_142821\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_142821\r2-vyos.txt
2/2 devices backed up in 26.4 s
```

R1 diff:

```
# 2026-10-05 07:28:23 by RouterOS 7.23.7                                     =>
set [ find default-name=ether1 ] comment=to-R2-eth0 disable-running-check=no =>
                                                                             =>
                                                                             =>
                                                                             =>
[admin@CHR] >                                                                =>
# 2026-10-05 00:48:45 by RouterOS 7.23.7                                     <=
set [ find default-name=ether1 ] disable-running-check=no                    <=
```

R2 diff:

```
set interfaces ethernet eth0 description 'to-R1-ether1' =>
```

Result: the change is in place on both vendors and nothing else differs in the configs. The R1 file did get three empty lines and a RouterOS prompt at the end, which is the next section.

## 15. Prompt text at the end of the R1 backup

Ends of the two R1 files:

```
PS D:\it-ot-lab> Get-Content backups\$after\r1-mikrotik.rsc -Tail 8
...
/system note
set note="Authorized access only. Lab device."



[admin@CHR] >

PS D:\it-ot-lab> Get-Content backups\2026-10-05_074840\r1-mikrotik.rsc -Tail 8
...
/system note
set note="Authorized access only. Lab device."
```

The `142821` file had three empty lines and the prompt `[admin@CHR] >` at the end. The `074840` file was clean, and so was the `080821` run, so it does not happen every time. I do not know why. A `.rsc` file with a prompt line in it would give an error if I imported it again, so I changed `clean()` in the backup script:

```python
PROMPT = re.compile(r"^\[.+@.+\] >$")


def clean(text):
    kept = [
        line
        for line in text.splitlines()
        if not any(word in line.lower() for word in SKIP)
        and not PROMPT.match(line.strip())
    ]
    return "\n".join(kept).rstrip() + "\n"
```

(It also needed `import re` at the top.) Run after the change:

```
PS D:\it-ot-lab> python scripts\backup_configs.py
[ OK ] r1-mikrotik -> D:\it-ot-lab\backups\2026-10-05_143451\r1-mikrotik.rsc
[ OK ] r2-vyos -> D:\it-ot-lab\backups\2026-10-05_143451\r2-vyos.txt
2/2 devices backed up in 25.2 s

PS D:\it-ot-lab> $new = (Get-ChildItem backups | Sort-Object Name | Select-Object -Last 1).Name; Get-Content backups\$new\r1-mikrotik.rsc -Tail 6
add address=192.168.56.11/24 interface=ether2 network=192.168.56.0
/routing ospf interface-template
add area=backbone networks=10.0.0.0/30
add area=backbone networks=1.1.1.1/32 passive
/system note
set note="Authorized access only. Lab device."
```

The end of the file is clean now. Because the prompt did not appear in every run, one clean run does not prove the filter by itself; the filter logic is what guarantees it.

## 16. README block

I got a draft of a Phase 3 section for `README.md` (the change, how the script works, how I checked it, the timing table, changes to the backup script, the problems, and what is not done), plus two small edits to the intro and to the old "Not done yet" list. Before saving it I need to check that every number and sentence matches this log. This file is the detailed version of that section.

## 17. Results

| Item | Value |
|---|---|
| Manual, R1 | 17.26 s |
| Manual, R2 | 79.03 s |
| Manual, both | about 96.3 s |
| Script push, both (from clean state) | 60.6 s |
| Script push, both (first successful run, R1 already changed) | 76.3 s, not used for comparison |
| Script push, first run | 42.5 s, R2 failed |
| Backup script, both | 23.5 to 34.0 s over the day (34.0, 23.5, 25.8, 26.5, 26.4, 25.2 s on successful runs; 83.7 s on the failed run) |

The script was about 36 s faster than doing it by hand for two devices. It is one run per method, so it is a rough number. I only measured two devices.

Backup folders from today (all in `backups/`, ignored by git):

| Folder | What it is |
|---|---|
| `2026-10-05_072244` | R2 file empty (76 bytes), reported OK |
| `2026-10-05_072706` | R2 failed |
| `2026-10-05_073318` | R2 back to normal after the banner was removed (3337 bytes) |
| `2026-10-05_074840` | "before" baseline |
| `2026-10-05_080821` | "after" for the first successful push |
| `2026-10-05_142821` | "after" for the clean-state push (R1 ends with prompt) |
| `2026-10-05_143451` | after the `clean()` change, R1 ends cleanly |

## 18. What is still not done

- Log anomaly detection
- Monitoring (Grafana with LibreNMS or PRTG)
- A real Modbus test for the TCP 502 rule
- A third vendor (no legal Cisco or Juniper image)
- Pushing to more than two devices (I only measured two)
- Screenshots for Phase 1 to 3 and a topology diagram, planned for the end
- Refreshing `configs/` from the latest backup, then commit and push of the Phase 3 files (`scripts/push_config.py`, the updated `scripts/backup_configs.py`, README and this log)

## 19. My own mistakes during the session

These were mine, not lab problems, and none of them did damage:

- Typed `<folder>` literally in a PowerShell command.
- Pasted a long banner line into the VyOS console and got `devicee`.
- Ran `ssh` to the VyOS router from the VyOS console itself.
- Saved `debug_r2.py` in `scripts` instead of `D:\it-ot-lab`, so the first two runs could not find it.
- Typed `configure` while the console was already in config mode.
