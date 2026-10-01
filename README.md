# RFID_Reader

REST + MQTT API in front of a Zebra **RFD4031** UHF RFID sled, in pure Python.
Built to run on a **Raspberry Pi 4/5** as the main unit.

Software sends a command → the sled reads → an array of EPCs comes back.
**No trigger pull** — the read is started from software.

```
GET  /api/read        -> {"success":true,"count":2,"tags":["EPC1","EPC2"],"readAt":"..."}
     nothing          -> {"success":true,"count":0,"tags":[],"readAt":"..."}
     reader down      -> HTTP 503 {"success":false,"error":"READER_DISCONNECTED"}
GET  /api/health      -> reader status
```

---

## Why there is no Zebra SDK here

Zebra's RFID **Host SDK** (Windows/Linux) covers the *fixed* readers — FX7500,
FX9600, ATR7000 — not the RFD40 sleds, and Zebra states plainly that **ARM is not
supported**, so the x86 `.so`/`.dll` can never load on a Pi. The supported SDK for
an RFD40 is the **Android** one.

The way out: the sled's RFID serial interface speaks **ZETI** (Zebra Easy Text
Interface) — plain ASCII, CR LF terminated, documented in the *RFD8500/i RFID
Developer Guide*, Appendix A. `pyserial` is all that is needed.

Verified against the hardware here — `RFD4031-G10B700-TH`, firmware
`PAAFKS00-013-R05`:

```
-> cn   <- Command: connect,Status:Connection Successful
-> gv   <- ,,HARDWARE,HWID_3_DV_MV,RFD40,PRE+
           ,,NGE,2.0.54.0
           ,,CRIMAN_DEVICE,PAAFKS00-013-R05
           ,,WIFI,17.92.1.p149.84
```

### The sled exposes two serial ports

Only one speaks ZETI. The other is the **barcode scanner**, which answers binary
SSI — a ZETI command sent there comes back as
`\x05\xd1\x00\x80\x01\xfe\xa9`. `zeti.find_port()` sorts this out by asking each
port and keeping the one that replies as text, so the device number never has to
be hardcoded:

| Host | Ports |
|---|---|
| Raspberry Pi | `/dev/ttyACM0`, `/dev/ttyACM1` |
| Windows | `COM15`, `COM16` |

### Wi-Fi on the sled cannot carry tag data

Don't go looking. The sled accepts no inbound connections, and its on-board MQTT
is **Reader Management only** — `rfd4031-prg-en.pdf` p.25 files MQTT under *Mobile
Device Management* (42Gears, SOTI). Zebra's own answer on the developer forum:
*"the MQTT if defined can only be available for Reader Management functionality and
not for RFID expected interactions."* Hence this design: the sled stays on USB to
the Pi, and the **Pi** is what speaks to the network.

---

## Install (Raspberry Pi OS)

```bash
sudo apt update && sudo apt install -y python3-pip
git clone https://github.com/FongZ7/RFID_Reader.git
cd RFID_Reader
pip3 install -r requirements.txt
```

The sled appears as a USB CDC ACM device. Give yourself serial access once:

```bash
sudo usermod -aG dialout $USER     # log out and back in
```

Check that the sled is seen and which port is the RFID one:

```bash
python3 rfid_cli.py --ports
```

---

## Use

### CLI — no server needed

```bash
python3 rfid_cli.py                 # one 1000 ms read
python3 rfid_cli.py --ms 1500       # longer window
python3 rfid_cli.py --dbm 10        # set antenna power first
python3 rfid_cli.py --loop          # until Ctrl+C
python3 rfid_cli.py --info          # firmware versions
python3 rfid_cli.py --sweep         # find the right antenna power
```

### Server

```bash
RFID_DBM=10 python3 rfid_api_server.py
```

```bash
curl http://<pi-ip>:8080/api/read?ms=1000
curl -X POST http://<pi-ip>:8080/api/read -H "Content-Type: application/json" -d '{"timeoutMs":1000}'
curl http://<pi-ip>:8080/api/health
```

`/read` and `/health` work too, without the `/api` prefix.

### MQTT

Set `MQTT_BROKER` and the server also listens on MQTT. Useful when the client
should not have to reach the Pi directly — both sides connect *out* to the broker.

| Topic | Direction | Payload |
|---|---|---|
| `rfid/read` | client → Pi | anything, even empty |
| `rfid/result` | Pi → client | `{"status":"ok","count":2,"tags":[...]}` |
| `rfid/status` | Pi → client | retained + LWT, `{"connected":true}` |

Command fields, all optional:

| Field | Meaning |
|---|---|
| `ms` / `timeoutMs` | read window, clamped to 50–10000 |
| `minRssi` | drop tags weaker than this (e.g. `-60`) |
| `requestId` | any string, echoed back in the result |
| `replyTo` | answer on this topic instead of `rfid/result` |

```bash
mosquitto_sub -h ns.artroninnovative.co.th -t rfid/result &
mosquitto_pub -h ns.artroninnovative.co.th -t rfid/read -m '{"requestId":"a1","ms":1000}'
```

```json
{"status":"ok",     "requestId":"a1", "count":2, "tags":["E200...43","E200...6B"]}
{"status":"no_tag", "requestId":"a1", "count":0, "tags":[]}
{"status":"error",  "requestId":"a1", "count":0, "tags":[], "error":"..."}
```

`requestId` is left out when the command did not carry one. With one reader and a
shared `rfid/result`, two clients asking at once cannot tell whose array is whose —
match on `requestId`, or give each client its own `replyTo`.

---

## Configuration

Environment variables, all optional:

| Variable | Default | Meaning |
|---|---|---|
| `RFID_DEVICE` | autodetect | serial port, e.g. `/dev/ttyACM0`. Leave unset — the number moves between plug-ins |
| `RFID_BAUD` | `115200` | |
| `RFID_MS` | `1000` | default read window |
| `RFID_DBM` | sled's own | antenna power in dBm |
| `RFID_MINRSSI` | off | RSSI floor |
| `RFID_HOST` | `0.0.0.0` | |
| `RFID_PORT` | `8080` | |
| `MQTT_BROKER` | unset = MQTT off | |
| `MQTT_PORT` | `1883` | |
| `MQTT_BASE` | `rfid` | topic prefix |
| `MQTT_USER` / `MQTT_PASS` | unset | |

---

## Run as a service

```bash
sudo cp rfid-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rfid-api
journalctl -u rfid-api -f
```

Edit the `Environment=` lines in the unit first — at minimum `User`,
`WorkingDirectory`, and whether `MQTT_BROKER` should be set.

---

## Layout

```
RFID_Reader/
├── zeti.py              ZETI protocol over pyserial - the only reader code
├── rfid_api_server.py   Flask REST + MQTT, one reader behind one lock
├── rfid_cli.py          test/CLI tool, also the --sweep power finder
├── rfid-api.service     systemd unit
└── requirements.txt
```

---

## ZETI notes worth keeping

Learned the hard way; the full reference is Appendix A of the RFD8500 guide.

| Command | Meaning |
|---|---|
| `cn` / `dc` | connect / disconnect the ASCII session. Everything else fails with `Status:ASCII Connection not present` until `cn` |
| `gv` | versions, one `,,KEY,VALUE` line each |
| **`a`** | **abort** |
| **`ac .p 100`** | **antenna power, tenths of a dBm** — `100` is 10.0 dBm |
| `ac .n` | read the current antenna config back |
| `rc .iz .ir` | report config: include first-seen time and RSSI |
| `st .d` | start trigger defaults — begin as soon as `in` is sent |
| `ot .ip .et .to 1000` | stop trigger: ignore the gun trigger, stop after 1000 ms |
| `in` | inventory. Tag lines are `,,<EPC>,<firstseentime>,<rssi>` |

- **`ac` is not abort.** Abort is `a`. Sending `ac` on its own quietly rewrites the
  antenna configuration instead of stopping anything.
- Tag line field count follows the report config, so parse positionally and
  tolerate missing fields — `_parse_tag_line()` does.
- The sled sleeps when idle and **drops off USB entirely**; the port disappears
  rather than going quiet. Every read reconnects once before giving up, and
  autodetect re-runs because the device number can change.

## Open item — antenna power

At 25 dBm the reader picks up tags elsewhere in the room. At 10 dBm it is clean,
but it has not been confirmed that the intended tag still reads at the working
distance. Use `rfid_cli.py --sweep` with the target tag in place, take the highest
level that shows **only** that tag, and set `RFID_DBM`.
