"""Back up the configs of the lab routers over SSH.

Passwords are asked when the script starts (or read from the environment
variables LAB_R1_PASS and LAB_R2_PASS), so no secret is stored in this file.
Each run writes one folder under backups/ named with the date and time.
"""

import os
import time
from datetime import datetime
from getpass import getpass
from pathlib import Path

from netmiko import ConnectHandler

DEVICES = [
    {
        "name": "r1-mikrotik",
        "ext": "rsc",
        "env": "LAB_R1_PASS",
        "command": "/export",
        "conn": {
            "device_type": "mikrotik_routeros",
            "host": "192.168.56.11",
            "username": "admin",
        },
    },
    {
        "name": "r2-vyos",
        "ext": "txt",
        "env": "LAB_R2_PASS",
        "command": "show configuration commands",
        "conn": {
            "device_type": "vyos",
            "host": "192.168.56.12",
            "username": "vyos",
        },
    },
]

# Lines containing any of these are dropped before the file is saved.
SKIP = ("password", "# system id")


def clean(text):
    kept = [
        line
        for line in text.splitlines()
        if not any(word in line.lower() for word in SKIP)
    ]
    return "\n".join(kept) + "\n"


def backup(dev, outdir):
    conn = dict(dev["conn"])
    conn["password"] = dev["password"]
    try:
        with ConnectHandler(**conn) as ssh:
            output = ssh.send_command(dev["command"], read_timeout=60)
    except Exception as err:
        print(f"[FAIL] {dev['name']}: {err}")
        return False
    path = outdir / f"{dev['name']}.{dev['ext']}"
    path.write_text(clean(output), encoding="utf-8")
    print(f"[ OK ] {dev['name']} -> {path}")
    return True


def main():
    # Ask for passwords first so typing time is not counted in the timer.
    for dev in DEVICES:
        user = dev["conn"]["username"]
        dev["password"] = os.environ.get(dev["env"]) or getpass(
            f"Password for {dev['name']} ({user}): "
        )

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    outdir = Path(__file__).resolve().parent.parent / "backups" / stamp
    outdir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    results = [backup(dev, outdir) for dev in DEVICES]
    elapsed = time.perf_counter() - start

    print(f"{sum(results)}/{len(results)} devices backed up in {elapsed:.1f} s")


if __name__ == "__main__":
    main()
