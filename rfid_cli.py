"""Command-line test tool - talks to the sled directly, no server involved.

    python rfid_cli.py                      one 1000 ms read
    python rfid_cli.py --ms 1500            longer read window
    python rfid_cli.py --dbm 10             set antenna power first
    python rfid_cli.py --loop               keep reading until Ctrl+C
    python rfid_cli.py --info               port, model and firmware versions
    python rfid_cli.py --ports              list serial ports and say which one is ZETI
    python rfid_cli.py --device /dev/ttyACM0
    python rfid_cli.py --raw gr             any raw ZETI command - here, the RF region

Use --sweep to find the antenna power that sees only the tag you care about:

    python rfid_cli.py --sweep
"""

import argparse
import sys
import time

import serial.tools.list_ports

from zeti import ZetiReader, ZetiError, find_port


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None, help="serial port (default: autodetect)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--ms", type=int, default=1000)
    ap.add_argument("--dbm", type=float, default=None)
    ap.add_argument("--minrssi", type=int, default=None)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--ports", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--raw", metavar="CMD",
                    help="send one raw ZETI command and print the reply, "
                         "e.g. --raw gr (get region), --raw ga (supported regions)")
    a = ap.parse_args()

    if a.ports:
        zeti = find_port()
        for p in serial.tools.list_ports.comports():
            mark = "  <-- ZETI" if p.device == zeti else ""
            print("%-14s %s%s" % (p.device, p.description, mark))
        if not zeti:
            print("\nno ZETI port found - sled unplugged, asleep, or in HID mode")
            return 2
        return 0

    try:
        reader = ZetiReader(port=a.device, baud=a.baud, power_dbm=a.dbm, log=print)
        with reader:
            print("port    : %s" % reader.port)
            print("model   : %s" % reader.model())
            p = reader.get_power_dbm()
            print("power   : %s" % ("%.1f dBm" % p if p is not None else "?"))

            if a.raw:
                # 'gr' and 'ga' answer with a long multi-line channel list, so
                # give the sled longer than the default quiet window.
                print()
                print(reader.command(a.raw, quiet_for=1.0).strip())
                return 0

            if a.info:
                for k, v in reader.version().items():
                    print("  %-16s %s" % (k, v))
                return 0

            if a.sweep:
                return sweep(reader, a.ms)

            while True:
                t0 = time.time()
                tags = reader.inventory(a.ms, a.minrssi)
                dt = (time.time() - t0) * 1000
                print("\n%d tag(s) in %.0f ms" % (len(tags), dt))
                for t in tags:
                    print("  %s" % t)
                if not a.loop:
                    return 0
                time.sleep(0.5)
    except ZetiError as e:
        print("error: %s" % e)
        return 1
    except KeyboardInterrupt:
        print()
        return 0


def sweep(reader, ms):
    """Walk the power range and show what each level picks up. Pick the highest
    level that still sees only your target tag."""
    print("\nsweeping antenna power - target tag in place, others out of range\n")
    for dbm in range(5, 31, 5):
        reader.set_power(dbm)
        tags = reader.inventory(ms, None)
        print("%4.1f dBm  %d tag(s)  %s" % (dbm, len(tags), ", ".join(t[-8:] for t in tags)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
