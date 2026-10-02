#!/usr/bin/env bash
# Give this unit its identity, for when several identical Pi+sled units are
# deployed from the same image.
#
#     ./provision.sh --name robot01
#     ./provision.sh --name robot02 --dbm 12 --ap-ssid RFID-ROBOT02
#     ./provision.sh --show
#
# Sets, in one go:
#   hostname            robot01            (so you can tell units apart on the LAN)
#   MQTT_BASE           rfid/robot01       -> rfid/robot01/read, /result, /status
#   MQTT_CLIENT_ID      rfid-robot01       unique per unit - see below
#   RFID_DBM            optional, antenna power for this unit's mounting
#   AP SSID             optional, if the unit broadcasts its own Wi-Fi
#
# Why MQTT_CLIENT_ID matters: MQTT brokers allow one connection per client id.
# A fleet flashed from one image shares a hostname, so every unit would use the
# same id and they would disconnect each other in a loop. The symptom looks
# like reads failing at random, not like an MQTT problem at all.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT=/etc/systemd/system/rfid-api.service
NAME=""
DBM=""
AP_SSID=""
AP_PASS=""
PREFIX="rfid"
ACTION="set"

while [ $# -gt 0 ]; do
    case "$1" in
        --name)      NAME="$2"; shift 2 ;;
        --prefix)    PREFIX="$2"; shift 2 ;;
        --dbm)       DBM="$2"; shift 2 ;;
        --ap-ssid)   AP_SSID="$2"; shift 2 ;;
        --ap-pass)   AP_PASS="$2"; shift 2 ;;
        --show)      ACTION="show"; shift ;;
        -h|--help)   awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

show() {
    echo "hostname      : $(hostname)"
    echo "machine-id    : $(cut -c1-8 /etc/machine-id 2>/dev/null || echo '?')"
    echo "IP addresses  : $(hostname -I)"
    if [ -f "$UNIT" ]; then
        echo "service settings:"
        grep -E '^Environment=(RFID|MQTT)_' "$UNIT" | sed 's/^Environment=/  /' |
            sed 's/^\(  MQTT_PASS=\).*/\1********/'
    else
        echo "service       : not installed (run ./install.sh)"
    fi
    if command -v nmcli >/dev/null && nmcli -t -f NAME connection show 2>/dev/null | grep -qx rfid-ap; then
        echo "AP SSID       : $(nmcli -g 802-11-wireless.ssid connection show rfid-ap 2>/dev/null)"
    fi
}

if [ "$ACTION" = "show" ]; then
    show
    exit 0
fi

[ -n "$NAME" ] || { echo "--name is required, e.g. --name robot01" >&2; exit 2; }
echo "$NAME" | grep -qE '^[a-z0-9][a-z0-9-]{0,30}$' || {
    echo "--name must be lowercase letters, digits and dashes (it becomes the hostname)" >&2
    exit 2
}
[ -f "$UNIT" ] || { echo "run ./install.sh first - $UNIT does not exist" >&2; exit 1; }

echo "provisioning this unit as '$NAME'"

# ---------------------------------------------------------------- hostname
if [ "$(hostname)" != "$NAME" ]; then
    echo "  hostname: $(hostname) -> $NAME"
    sudo hostnamectl set-hostname "$NAME"
    # keep /etc/hosts in step, or sudo complains about resolving the host
    sudo sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$NAME/" /etc/hosts
    grep -q "^127.0.1.1" /etc/hosts || echo -e "127.0.1.1\t$NAME" | sudo tee -a /etc/hosts >/dev/null
else
    echo "  hostname: already $NAME"
fi

# ---------------------------------------------------------------- service env
set_env() {   # set_env KEY VALUE  - replace the line if present, else add it
    local key="$1" val="$2"
    sudo sed -i "/^#\?Environment=${key}=/d" "$UNIT"
    sudo sed -i "/^\[Service\]/a Environment=${key}=${val}" "$UNIT"
    echo "  $key=$val"
}

set_env MQTT_BASE "${PREFIX}/${NAME}"
set_env MQTT_CLIENT_ID "rfid-${NAME}"
[ -n "$DBM" ] && set_env RFID_DBM "$DBM"

sudo systemctl daemon-reload
sudo systemctl restart rfid-api

# ---------------------------------------------------------------- AP
if [ -n "$AP_SSID" ]; then
    echo "  AP SSID: $AP_SSID"
    if [ -n "$AP_PASS" ]; then
        "$DIR/setup_ap.sh" --ssid "$AP_SSID" --password "$AP_PASS"
    else
        echo "  (--ap-ssid given without --ap-pass: run ./setup_ap.sh yourself)"
    fi
fi

sleep 3
echo
show
cat <<EOF

This unit answers on:
  REST   http://$(hostname -I | awk '{print $1}'):8080/api/read?ms=1000
  MQTT   ${PREFIX}/${NAME}/read   ->   ${PREFIX}/${NAME}/result

From the robot side, one subscription covers every unit:
  mosquitto_sub -h <broker> -t '${PREFIX}/+/result' -v
  mosquitto_sub -h <broker> -t '${PREFIX}/+/status' -v     # who is online

A reboot is the clean way to finish a hostname change.
EOF
