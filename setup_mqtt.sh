#!/usr/bin/env bash
# Install a Mosquitto broker on the Pi and point the RFID service at it, so the
# whole MQTT path runs on this one box - no external broker needed.
#
#     ./setup_mqtt.sh                      broker on this Pi, open to the LAN
#     ./setup_mqtt.sh --user bot --password s3cret
#     ./setup_mqtt.sh --base rfid          topic prefix (default: rfid)
#     ./setup_mqtt.sh --off                stop using MQTT (REST keeps working)
#
# What this gives you:
#
#     [robot]  --MQTT-->  [Pi: mosquitto]  -->  [Pi: rfid-api]  --USB/ZETI-->  [sled]
#                 or
#     [robot]  --REST-->  [Pi: rfid-api]   ------------------- --USB/ZETI-->  [sled]
#
# The sled is NOT an MQTT client and never sees MQTT. It is driven over USB.
# MQTT here is the robot's way of talking to the Pi, as an alternative to REST.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT=/etc/systemd/system/rfid-api.service
MQ_USER=""
MQ_PASS=""
BASE="rfid"
ACTION="on"

while [ $# -gt 0 ]; do
    case "$1" in
        --user)     MQ_USER="$2"; shift 2 ;;
        --password) MQ_PASS="$2"; shift 2 ;;
        --base)     BASE="$2"; shift 2 ;;
        --off)      ACTION="off"; shift ;;
        -h|--help)  awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

[ -f "$UNIT" ] || { echo "run ./install.sh first - $UNIT does not exist" >&2; exit 1; }

# ---------------------------------------------------------------- off
if [ "$ACTION" = "off" ]; then
    echo "removing MQTT settings from the service"
    sudo sed -i 's|^Environment=MQTT_|#Environment=MQTT_|' "$UNIT"
    sudo systemctl daemon-reload
    sudo systemctl restart rfid-api
    echo "done - REST still works, MQTT is off."
    echo "mosquitto is left installed; disable it with: sudo systemctl disable --now mosquitto"
    exit 0
fi

# ---------------------------------------------------------------- install
if ! command -v mosquitto >/dev/null; then
    echo "installing mosquitto"
    sudo apt update
    sudo apt install -y mosquitto mosquitto-clients
else
    echo "mosquitto already installed"
fi

CONF=/etc/mosquitto/conf.d/rfid.conf
echo "writing $CONF"
if [ -n "$MQ_USER" ]; then
    [ -n "$MQ_PASS" ] || { echo "--user needs --password too" >&2; exit 2; }
    sudo mosquitto_passwd -b -c /etc/mosquitto/rfid.passwd "$MQ_USER" "$MQ_PASS"
    sudo chmod 640 /etc/mosquitto/rfid.passwd
    sudo chown root:mosquitto /etc/mosquitto/rfid.passwd
    sudo tee "$CONF" >/dev/null <<EOF
# RFID API broker - written by setup_mqtt.sh
listener 1883
allow_anonymous false
password_file /etc/mosquitto/rfid.passwd
EOF
else
    echo
    echo "*** No --user given: the broker will accept anyone on the network."
    echo "*** Fine on a closed machine-to-machine LAN. On anything wider, re-run"
    echo "*** with --user and --password."
    echo
    sudo tee "$CONF" >/dev/null <<EOF
# RFID API broker - written by setup_mqtt.sh
listener 1883
allow_anonymous true
EOF
fi

sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sleep 2
sudo systemctl is-active --quiet mosquitto || {
    echo "mosquitto failed to start:" >&2
    sudo journalctl -u mosquitto -n 20 --no-pager >&2
    exit 1
}
echo "mosquitto is running"

# ---------------------------------------------------------------- wire up
echo "pointing the RFID service at it"
# Drop any MQTT_ lines we previously wrote, then add the current ones.
sudo sed -i '/^#\?Environment=MQTT_/d' "$UNIT"
TMP="$(mktemp)"
{
    echo "Environment=MQTT_BROKER=127.0.0.1"
    echo "Environment=MQTT_PORT=1883"
    echo "Environment=MQTT_BASE=$BASE"
    [ -n "$MQ_USER" ] && echo "Environment=MQTT_USER=$MQ_USER"
    [ -n "$MQ_PASS" ] && echo "Environment=MQTT_PASS=$MQ_PASS"
} > "$TMP"
# 'r' appends the file after the matched line - plain POSIX-ish sed, unlike the
# 'e' (execute) extension which some sed builds ship disabled.
sudo sed -i "/^\[Service\]/r $TMP" "$UNIT"
rm -f "$TMP"

if [ -n "$MQ_PASS" ]; then
    # The password now sits in the unit file, which is world-readable by default.
    sudo chmod 640 "$UNIT"
    sudo chown root:root "$UNIT"
fi

sudo systemctl daemon-reload
sudo systemctl restart rfid-api
sleep 4

echo
sudo systemctl status rfid-api --no-pager -l | head -14
echo

IP="$(hostname -I | awk '{print $1}')"
cat <<EOF
MQTT is live.

  broker : $IP:1883${MQ_USER:+   user $MQ_USER}
  topics : $BASE/read   -> publish a command here
           $BASE/result <- the EPC array comes back here
           $BASE/status <- retained, {"connected":true}

Test from this Pi:
  mosquitto_sub -h 127.0.0.1 -t '$BASE/#' -v ${MQ_USER:+-u $MQ_USER -P '<password>'} &
  mosquitto_pub -h 127.0.0.1 -t $BASE/read -m '{"requestId":"t1","ms":1000}' ${MQ_USER:+-u $MQ_USER -P '<password>'}

Test from the robot / another machine on the LAN - same commands with -h $IP

REST still works at the same time:
  curl "http://$IP:8080/api/read?ms=1000"
EOF
