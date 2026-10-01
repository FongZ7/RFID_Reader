"""RFID API server for the Zebra RFD4031 on a Raspberry Pi.

Software-triggered reads - no trigger pull. Two ways in, both talking to the same
reader behind one lock, because the sled can only run one inventory at a time:

  REST    GET  /api/health              reader status
          GET  /api/read?ms=1000        read, return the EPC array
          POST /api/read  {"timeoutMs":1000}

  MQTT    publish  rfid/read            {} or {"ms":1000,"requestId":"x"}
          receive  rfid/result          {"status":"ok","count":2,"tags":[...]}

Config comes from the environment (see README):
  RFID_DEVICE RFID_BAUD RFID_MS RFID_DBM RFID_MINRSSI
  RFID_HOST RFID_PORT
  MQTT_BROKER MQTT_PORT MQTT_BASE MQTT_USER MQTT_PASS

MQTT is only started when MQTT_BROKER is set.
"""

import atexit
import json
import os
import platform
import signal
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request

from zeti import ZetiReader, ZetiError, find_port

# ---------------------------------------------------------------- config
DEVICE   = os.environ.get("RFID_DEVICE") or None          # None = autodetect
BAUD     = int(os.environ.get("RFID_BAUD", "115200"))
DEF_MS   = int(os.environ.get("RFID_MS", "1000"))
DBM      = os.environ.get("RFID_DBM")
DBM      = float(DBM) if DBM else None
MIN_RSSI = os.environ.get("RFID_MINRSSI")
MIN_RSSI = int(MIN_RSSI) if MIN_RSSI else None

HOST = os.environ.get("RFID_HOST", "0.0.0.0")
PORT = int(os.environ.get("RFID_PORT", "8080"))

MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_BASE   = os.environ.get("MQTT_BASE", "rfid").strip("/")
MQTT_USER   = os.environ.get("MQTT_USER")
MQTT_PASS   = os.environ.get("MQTT_PASS")

app = Flask(__name__)

# ---------------------------------------------------------------- reader
_reader = ZetiReader(port=DEVICE, baud=BAUD, power_dbm=DBM, log=lambda m: log("reader: " + m))
_lock = threading.Lock()       # one inventory at a time, REST and MQTT share it
_last_error = ""


def log(msg):
    print("%s  %s" % (datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def _ensure():
    """Open the port, reopening after the sled slept and dropped off USB."""
    global _last_error
    if _reader.is_open:
        return
    if DEVICE is None:
        _reader.port = None                 # re-detect, the device node can move
    _reader.open()
    _last_error = ""


def read_tags(ms, min_rssi):
    """Serialised read with one reconnect+retry - the sled drops USB when it sleeps."""
    global _last_error
    with _lock:
        try:
            _ensure()
            return _reader.inventory(ms, min_rssi)
        except Exception as first:
            log("read failed (%s) - reconnecting" % first)
            try:
                _reader.close()
            except Exception:
                pass
            try:
                _ensure()
                return _reader.inventory(ms, min_rssi)
            except Exception as second:
                _last_error = str(second)
                raise


def status():
    global _last_error
    out = {
        "connected": False,
        "device": _reader.port or DEVICE or "(autodetect)",
        "model": "",
        "powerDbm": None,
        "defaultMs": DEF_MS,
        "minRssi": MIN_RSSI,
        "lastError": _last_error,
        "at": datetime.now().astimezone().isoformat(),
    }
    with _lock:
        try:
            _ensure()
            out["connected"] = _reader.is_open
            out["device"] = _reader.port
            out["model"] = _reader.model()
            out["powerDbm"] = _reader.get_power_dbm()
        except Exception as e:
            _last_error = str(e)
            out["lastError"] = _last_error
    out["success"] = out["connected"]
    return out


def _args(body, qs):
    """Read window / RSSI floor from a JSON body or the query string."""
    ms = DEF_MS
    min_rssi = MIN_RSSI
    for key in ("timeoutMs", "ms"):
        if isinstance(body, dict) and key in body:
            ms = int(body[key])
        elif qs.get(key):
            ms = int(qs[key])
    if isinstance(body, dict) and "minRssi" in body:
        min_rssi = int(body["minRssi"])
    elif qs.get("minrssi"):
        min_rssi = int(qs["minrssi"])
    return max(50, min(ms, 10000)), min_rssi


# ---------------------------------------------------------------- REST
@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/api/health", methods=["GET"])
@app.route("/health", methods=["GET"])
def http_health():
    s = status()
    return jsonify(s), (200 if s["connected"] else 503)


@app.route("/api/read", methods=["GET", "POST", "OPTIONS"])
@app.route("/read", methods=["GET", "POST", "OPTIONS"])
def http_read():
    if request.method == "OPTIONS":
        return "", 204
    body = request.get_json(silent=True) or {}
    ms, min_rssi = _args(body, request.args)
    try:
        tags = read_tags(ms, min_rssi)
    except Exception as e:
        return jsonify({"success": False, "error": "READER_DISCONNECTED", "detail": str(e)}), 503
    log("REST read %dms -> %d tag" % (ms, len(tags)))
    return jsonify({
        "success": True,
        "count": len(tags),
        "tags": tags,
        "readAt": datetime.now().astimezone().isoformat(),
    })


# ---------------------------------------------------------------- MQTT
def mqtt_loop():
    import paho.mqtt.client as mqtt

    cmd_topic = MQTT_BASE + "/read"
    out_topic = MQTT_BASE + "/result"

    def on_connect(client, userdata, flags, rc, *a):
        if rc == 0:
            client.subscribe(cmd_topic, qos=1)
            log("mqtt: connected %s:%d  sub %s" % (MQTT_BROKER, MQTT_PORT, cmd_topic))
        else:
            log("mqtt: refused, rc=%s" % rc)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except ValueError:
            payload = {}                                   # empty or non-JSON = defaults

        req_id = payload.get("requestId")
        reply_to = payload.get("replyTo") or out_topic
        if "#" in reply_to or "+" in reply_to:             # cannot publish to a wildcard
            reply_to = out_topic
        ms, min_rssi = _args(payload, {})

        try:
            tags = read_tags(ms, min_rssi)
            out = {
                "status": "ok" if tags else "no_tag",
                "count": len(tags),
                "tags": tags,
                "readAt": datetime.now().astimezone().isoformat(),
            }
            log("MQTT read %dms -> %d tag%s" % (ms, len(tags), "  id=" + req_id if req_id else ""))
        except Exception as e:
            out = {"status": "error", "count": 0, "tags": [], "error": str(e)}
            log("MQTT read FAILED - %s" % e)

        if req_id is not None:
            out["requestId"] = req_id
        client.publish(reply_to, json.dumps(out), qos=1)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id="rfd4031-%s" % platform.node().lower())
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id="rfd4031-%s" % platform.node().lower())   # paho 1.x
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.will_set(MQTT_BASE + "/status",
                    json.dumps({"connected": False, "reason": "connection lost"}),
                    qos=1, retain=True)

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.publish(MQTT_BASE + "/status",
                           json.dumps({"connected": True}), qos=1, retain=True)
            client.loop_forever()
        except Exception as e:
            log("mqtt: %s - reconnecting in 3s" % e)
            time.sleep(3)


# ---------------------------------------------------------------- main
def main():
    log("RFD4031 API server")
    log("  device   : %s" % (DEVICE or "autodetect"))
    log("  listen   : http://%s:%d" % (HOST, PORT))
    log("  read win : %d ms" % DEF_MS)
    if DBM is not None:
        log("  power    : %.1f dBm" % DBM)
    if MIN_RSSI is not None:
        log("  minRssi  : %d" % MIN_RSSI)

    # A failure here is not fatal: at boot systemd can start us before the sled
    # has finished enumerating on USB, and the sled drops off USB whenever it
    # sleeps. Every request reconnects, so serve either way.
    try:
        with _lock:
            _ensure()
        log("  reader   : connected (%s on %s)" % (_reader.model(), _reader.port))
    except Exception as e:
        log("  reader   : not ready yet (%s) - will connect on first request" % e)

    if MQTT_BROKER:
        log("  mqtt     : %s:%d  %s/read -> %s/result" % (MQTT_BROKER, MQTT_PORT, MQTT_BASE, MQTT_BASE))
        threading.Thread(target=mqtt_loop, name="mqtt", daemon=True).start()
    else:
        log("  mqtt     : off (set MQTT_BROKER to enable)")

    atexit.register(_shutdown)
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, AttributeError, OSError):
            pass                                        # not the main thread, or no such signal

    serve()


def _shutdown():
    """Release the serial port so the next start finds it free."""
    try:
        _reader.close()
    except Exception:
        pass


def _on_signal(signum, frame):
    log("signal %d - stopping" % signum)
    _shutdown()
    raise SystemExit(0)


def serve():
    """waitress when it is installed, Flask's dev server otherwise.

    This runs as a boot service, so the dev server is the wrong default: it warns
    about exactly that, and it is single-threaded per connection by default.
    waitress is pure Python, so it installs on a Pi with no compiler.
    """
    try:
        from waitress import serve as waitress_serve
    except ImportError:
        log("  server   : Flask dev server (pip install waitress for the production one)")
        app.run(host=HOST, port=PORT, threaded=True)
        return
    # One reader behind one lock means requests serialise anyway; a handful of
    # threads is plenty and keeps /health responsive during a read.
    log("  server   : waitress")
    log("\nready.  waiting for requests.")
    waitress_serve(app, host=HOST, port=PORT, threads=4, _quiet=True)


if __name__ == "__main__":
    main()
