"""ZETI client for the Zebra RFD4031 sled over USB-CDC serial.

ZETI = Zebra Easy Text Interface. The sled exposes it as plain ASCII on its RFID
serial port, so no Zebra SDK is needed - which is the whole point: the SDK is
.NET/Windows only and Zebra does not support ARM, so a Raspberry Pi could never
run it. pyserial can.

Port, as seen from each host:
    Raspberry Pi    /dev/ttyACM0   (the sled shows up as two ACM devices)
    Windows         COM15          (two COM ports; one is the barcode scanner)

The sled exposes TWO serial interfaces. Only one speaks ZETI - the other is the
barcode scanner and answers binary SSI, so a ZETI command there comes back as
b'\\x05\\xd1\\x00\\x80\\x01\\xfe\\xa9'. find_port() picks the right one by asking.

Command reference: RFD8500/i RFID Developer Guide, Appendix A (ZETI REFERENCE).
Commands are ASCII, CR LF terminated, parameters introduced by a dot:

    cn                      connect        -> Command: connect,Status:Connection Successful
    gv                      getversion     -> ,,HARDWARE,...,RFD40,PRE+
    ac .p 100               antenna power  -> 100 = 10.0 dBm  (NOT abort - that is 'a')
    ac .n                   read back the current antenna config
    rc .iz .ir              report config: include firstseentime + RSSI
    st .d                   start trigger: defaults = start as soon as 'in' is sent
    ot .ip .et .to 1000     stop trigger: ignore the gun trigger, stop after 1000 ms
    in                      inventory      -> ,,<EPC>,<firstseentime>,<rssi>
    a                       abort
    dc                      disconnect

Gotcha worth keeping: 'ac' is setantennaconfiguration. Abort is 'a'. Sending 'ac'
with no parameters when you meant abort silently rewrites the antenna config.
"""

import time

import serial
import serial.tools.list_ports


class ZetiError(Exception):
    pass


def find_port(candidates=None, baud=115200, timeout=1.5):
    """Return the serial port that answers ZETI, or None.

    Asks each candidate for its version. The scanner interface answers binary,
    a non-sled device answers nothing, so only the RFID port replies as text.
    """
    if candidates is None:
        candidates = [p.device for p in serial.tools.list_ports.comports()]
    for dev in candidates:
        try:
            with serial.Serial(dev, baud, timeout=0.2, write_timeout=2) as s:
                s.reset_input_buffer()
                s.write(b"cn\r\n")
                s.flush()
                buf = _drain(s, timeout)
                if b"Command:" in buf:
                    return dev
        except Exception:
            # Any port that cannot be opened, configured or read is simply not
            # ours - a modem, a console port, the scanner interface. Catch
            # broadly on purpose: letting one odd port's errno escape here
            # replaces the clear "no ZETI port found" with something like
            # "[Errno 22] Invalid argument" at the API boundary.
            continue
    return None


def _drain(s, quiet_for=0.4, hard_limit=15.0):
    """Read until the port has been silent for quiet_for seconds."""
    buf = b""
    start = time.time()
    last = start
    while time.time() - last < quiet_for and time.time() - start < hard_limit:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            last = time.time()
    return buf


class ZetiReader:
    """A connected RFD4031. Not thread-safe - serialise calls yourself."""

    def __init__(self, port=None, baud=115200, power_dbm=None, log=None):
        self.port = port
        self.baud = baud
        self.power_dbm = power_dbm
        self._log = log or (lambda m: None)
        self._s = None
        self._applied_power = None
        self._stop_ms = None

    # ---------- connection ----------
    @property
    def is_open(self):
        return self._s is not None and self._s.is_open

    def open(self):
        if self.is_open:
            return
        if not self.port:
            self.port = find_port()
            if not self.port:
                raise ZetiError("no ZETI serial port found - is the sled plugged in and awake?")
        self._s = serial.Serial(self.port, self.baud, timeout=0.2, write_timeout=2)
        self._s.reset_input_buffer()

        reply = self.command("cn")
        if "Status:" not in reply:
            raise ZetiError("no answer to 'cn' on %s" % self.port)

        # Pin the report config instead of only adding to it: include first-seen
        # time and RSSI, exclude everything else. Report config is sticky on the
        # sled, so without the excludes a tag line can arrive with extra columns
        # from whatever ran before us and the field positions shift.
        #   iz/el/ec/ir/ek/eh/es = inc firstseen, exc lastseen, exc pc, inc rssi,
        #                          exc phase, exc channelindex, exc tagseencount
        self.command("rc .iz .el .ec .ir .ek .eh .es")
        # start as soon as 'in' is sent, not on a trigger pull
        self.command("st .d")

        self._applied_power = None
        self._stop_ms = None
        if self.power_dbm is not None:
            self.set_power(self.power_dbm)
        self._log("connected %s" % self.port)

    def close(self):
        if self._s is not None:
            try:
                if self._s.is_open:
                    self.command("a", quiet_for=0.2)
                    self.command("dc", quiet_for=0.2)
            except Exception:
                pass
            try:
                self._s.close()
            except Exception:
                pass
            self._s = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------- raw command ----------
    def command(self, cmd, quiet_for=0.4, hard_limit=15.0):
        if not self.is_open:
            raise ZetiError("not connected")
        self._s.reset_input_buffer()
        self._s.write((cmd + "\r\n").encode("ascii"))
        self._s.flush()
        return _drain(self._s, quiet_for, hard_limit).decode("ascii", "replace")

    # ---------- info ----------
    def version(self):
        """{'HARDWARE': 'HWID_3_DV_MV,RFD40,PRE+', 'NGE': '2.0.54.0', ...}"""
        out = {}
        for line in self.command("gv").splitlines():
            line = line.strip()
            if not line.startswith(",,"):
                continue
            parts = line[2:].split(",", 1)
            if len(parts) == 2:
                out[parts[0].strip()] = parts[1].strip()
        return out

    def model(self):
        hw = self.version().get("HARDWARE", "")
        for piece in hw.split(","):
            if piece.startswith("RFD"):
                return piece
        return hw or "RFD40"

    # ---------- antenna power ----------
    def get_power_dbm(self):
        """Read the power back off the sled. None if it could not be parsed."""
        reply = self.command("ac .n")
        marker = ".power "
        i = reply.find(marker)
        if i < 0:
            return None
        digits = ""
        for ch in reply[i + len(marker):]:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) / 10.0 if digits else None

    def set_power(self, dbm):
        """ZETI takes tenths of a dBm: .p 100 is 10.0 dBm."""
        tenths = int(round(float(dbm) * 10))
        if tenths < 0:
            tenths = 0
        reply = self.command("ac .p %d" % tenths)
        if "Status:OK" not in reply:
            raise ZetiError("set power failed: %s" % reply.strip())
        self._applied_power = dbm
        return dbm

    # ---------- inventory ----------
    def inventory(self, ms=1000, min_rssi=None):
        """Software-triggered read. Returns EPCs in the order first seen.

        No trigger pull: 'ot .ip' tells the sled to ignore the physical trigger
        and '.et .to <ms>' stops the operation on a timeout.
        """
        if not self.is_open:
            raise ZetiError("not connected")
        ms = max(50, min(int(ms), 10000))

        # The stop trigger is sticky on the sled, so only program it when the
        # window actually changes - resending it costs ~0.5 s per read.
        if self._stop_ms != ms:
            reply = self.command("ot .ip .et .to %d" % ms, quiet_for=0.2)
            if "Status:OK" not in reply:
                raise ZetiError("set stop trigger failed: %s" % reply.strip())
            self._stop_ms = ms

        self._s.reset_input_buffer()
        self._s.write(b"in\r\n")
        self._s.flush()

        order, seen = [], set()
        # The sled stops itself on the timeout; this is only a backstop for a
        # sled that went away mid-read.
        deadline = time.time() + (ms / 1000.0) + 1.5
        pending = ""
        header_seen = False
        stopped = False

        while time.time() < deadline and not stopped:
            chunk = self._s.read(4096)
            if not chunk:
                continue
            pending += chunk.decode("ascii", "replace")
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                line = line.strip()

                if not line:
                    # A bare CR LF after the header is how ZETI marks end of
                    # response - that, not a notification, is what ends an
                    # inventory. Waiting for Notification:StopOperation instead
                    # burns the whole backstop, because notifications are off by
                    # default (a 1 s read then takes 3 s).
                    if header_seen:
                        stopped = True
                        break
                    continue

                if line.startswith("Command:inventory"):
                    header_seen = True
                    continue
                if line.startswith("Notification:StopOperation"):
                    stopped = True
                    break
                if not line.startswith(",,"):
                    continue                              # echo, notifications, summaries
                epc, rssi = _parse_tag_line(line)
                if not epc:
                    continue
                if min_rssi is not None and rssi is not None and rssi < min_rssi:
                    continue
                if epc not in seen:
                    seen.add(epc)
                    order.append(epc)

        if not stopped:
            # Only needed when the backstop fired - a sled that ended its own
            # response has already stopped, and 'a' would cost another ~0.3 s.
            # ('a' is abort; 'ac' is antenna config - do not mix them up.)
            self.command("a", quiet_for=0.15)
        return order


def _parse_tag_line(line):
    """',,<EPC>,<firstseentime>,<rssi>' -> ('<EPC>', -41). Field count varies
    with the report config, so read positionally and tolerate what is missing."""
    parts = [p.strip() for p in line.split(",")]
    parts = parts[2:]                                     # the two leading empty fields
    if not parts or not parts[0]:
        return None, None
    epc = parts[0]
    rssi = None
    for p in parts[1:]:
        try:
            v = int(p)
        except ValueError:
            continue
        if -120 <= v <= 0:                                # a plausible dBm, not a timestamp
            rssi = v
            break
    return epc, rssi
