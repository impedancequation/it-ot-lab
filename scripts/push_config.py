"""Push a small config change to the lab routers over SSH.

Passwords are asked when the script starts (or read from the environment
variables LAB_R1_PASS and LAB_R2_PASS). Run backup_configs.py before and
after to keep a record of what changed.
"""

import os
import time
from getpass import getpass

from netmiko import ConnectHandler

DEVICES = [
    {
        "name": "r1-mikrotik",
        "env": "LAB_R1_PASS",
        "commands": [
            '/interface ethernet set ether1 comment="to-R2-eth0"',
        ],
        "conn": {
            "device_type": "mikrotik_routeros",
            "host": "192.168.56.11",
            "username": "admin",
        },
    },
    {
        "name": "r2-vyos",
        "env": "LAB_R2_PASS",
        "commands": [
            "set interfaces ethernet eth0 description 'to-R1-ether1'",
            "commit",
            "save",
        ],
        "conn": {
            "device_type": "vyos",
            "host": "192.168.56.12",
            "username": "vyos",
        },
    },
]

# If any of these appear in the device output, the push is treated as failed.
ERROR_WORDS = ("invalid", "failure", "expected end of command", "not valid")


def push(dev):
    conn = dict(dev["conn"])
    conn["password"] = dev["password"]
    # The lab runs without KVM, so the routers answer slowly.
    conn["read_timeout_override"] = 60
    try:
        with ConnectHandler(**conn) as ssh:
            output = ssh.send_config_set(dev["commands"], exit_config_mode=False)
            if dev["conn"]["device_type"] == "vyos":
                ssh.exit_config_mode()
    except Exception as err:
        print(f"[FAIL] {dev['name']}: {err}")
        return False
    if any(word in output.lower() for word in ERROR_WORDS):
        print(f"[FAIL] {dev['name']}: device reported an error:\n{output}")
        return False
    print(f"[ OK ] {dev['name']}: {len(dev['commands'])} commands sent")
    return True


def main():
    for dev in DEVICES:
        user = dev["conn"]["username"]
        dev["password"] = os.environ.get(dev["env"]) or getpass(
            f"Password for {dev['name']} ({user}): "
        )

    start = time.perf_counter()
    results = [push(dev) for dev in DEVICES]
    elapsed = time.perf_counter() - start

    print(f"{sum(results)}/{len(results)} devices updated in {elapsed:.1f} s")


if __name__ == "__main__":
    main()