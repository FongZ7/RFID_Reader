#!/usr/bin/env bash
# Turn the Pi's Wi-Fi into an access point, so client devices can join it and
# call the RFID API without any existing network.
#
#     ./setup_ap.sh                                  create/enable with defaults
#     ./setup_ap.sh --ssid RFID-01 --password s3cret12
#     ./setup_ap.sh --status                         show current state
#     ./setup_ap.sh --off                            go back to being a Wi-Fi client
#
# Uses NetworkManager (default on Raspberry Pi OS Bookworm and later). With
# ipv4.method=shared, NetworkManager runs DHCP and NAT itself - no hostapd or
# dnsmasq config to write by hand. The Pi becomes 10.42.0.1 on the AP subnet.
#
# The RFID sled stays on USB. It is the client devices - phone, tablet, laptop,
# the customer's machine - that join this Wi-Fi.
set -euo pipefail

SSID="RFID-READER"
PASSWORD="rfid12345"
IFACE=""
BAND="bg"              # bg = 2.4 GHz (best range and client compatibility); a = 5 GHz
CHANNEL=""
CON_NAME="rfid-ap"
ACTION="up"

while [ $# -gt 0 ]; do
    case "$1" in
        --ssid)     SSID="$2"; shift 2 ;;
        --password) PASSWORD="$2"; shift 2 ;;
        --iface)    IFACE="$2"; shift 2 ;;
        --band)     BAND="$2"; shift 2 ;;
        --channel)  CHANNEL="$2"; shift 2 ;;
        --name)     CON_NAME="$2"; shift 2 ;;
        --status)   ACTION="status"; shift ;;
        --off)      ACTION="off"; shift ;;
        -h|--help)  sed -n '2,16p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

command -v nmcli >/dev/null || {
    echo "nmcli not found - this script needs NetworkManager." >&2
    echo "Raspberry Pi OS Bookworm and later have it. On older releases either" >&2
    echo "upgrade, or set up hostapd + dnsmasq by hand." >&2
    exit 1
}

# Pick the wireless interface if one was not named
if [ -z "$IFACE" ]; then
    IFACE="$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1; exit}')"
fi
[ -n "$IFACE" ] || { echo "no wifi interface found" >&2; exit 1; }

# ---------------------------------------------------------------- status
show_status() {
    echo "interface : $IFACE"
    nmcli -t -f GENERAL.STATE,GENERAL.CONNECTION device show "$IFACE" 2>/dev/null |
        sed 's/^/  /' || true
    echo
    echo "wifi connections known to NetworkManager:"
    nmcli -t -f NAME,TYPE,AUTOCONNECT connection show |
        awk -F: '$2 ~ /wireless/ {printf "  %-20s autoconnect=%s\n", $1, $3}'
    echo
    if nmcli -t -f NAME connection show --active | grep -qx "$CON_NAME"; then
        echo "AP '$CON_NAME' is ACTIVE"
        ip -4 addr show "$IFACE" | awk '/inet /{print "  address : "$2}'
        echo "  clients join SSID: $(nmcli -g 802-11-wireless.ssid connection show "$CON_NAME")"
        echo
        echo "  API from a joined client:"
        AP_IP="$(ip -4 -o addr show "$IFACE" | awk '{split($4,a,"/"); print a[1]}' | head -1)"
        echo "    curl http://${AP_IP:-10.42.0.1}:8080/api/health"
    else
        echo "AP '$CON_NAME' is not active"
    fi
}

if [ "$ACTION" = "status" ]; then
    show_status
    exit 0
fi

# ---------------------------------------------------------------- off
if [ "$ACTION" = "off" ]; then
    echo "stopping AP '$CON_NAME'"
    sudo nmcli connection down "$CON_NAME" 2>/dev/null || true
    sudo nmcli connection modify "$CON_NAME" connection.autoconnect no 2>/dev/null || true
    echo "re-enabling autoconnect on the other wifi connections"
    nmcli -t -f NAME,TYPE connection show |
        awk -F: -v ap="$CON_NAME" '$2 ~ /wireless/ && $1 != ap {print $1}' |
        while read -r c; do sudo nmcli connection modify "$c" connection.autoconnect yes; done
    echo
    echo "done. The Pi is a Wi-Fi client again."
    echo "Connect it to a network with:  sudo nmcli device wifi connect <SSID> password <PASSWORD>"
    exit 0
fi

# ---------------------------------------------------------------- checks
[ "${#PASSWORD}" -ge 8 ] || { echo "password must be at least 8 characters (WPA2 requirement)" >&2; exit 2; }

# A radio with no regulatory domain cannot run an AP. On Raspberry Pi OS the
# WLAN country is set in raspi-config; without it wlan0 is often soft-blocked.
if command -v rfkill >/dev/null && rfkill list wlan 2>/dev/null | grep -q "Soft blocked: yes"; then
    echo "WARNING: the wifi radio is soft-blocked." >&2
    echo "  Set the WLAN country first:  sudo raspi-config  ->  Localisation  ->  WLAN Country" >&2
    echo "  then:  sudo rfkill unblock wlan" >&2
fi
if command -v iw >/dev/null; then
    REG="$(iw reg get 2>/dev/null | awk -F: '/country/{print $1; exit}' | awk '{print $2}')"
    if [ "$REG" = "00" ]; then
        echo "WARNING: regulatory domain is 00 (world) - AP mode may be refused." >&2
        echo "  Set the WLAN country in raspi-config." >&2
    fi
fi

cat <<EOF

About to turn $IFACE into an access point:

  SSID      : $SSID
  password  : $PASSWORD
  band      : $BAND${CHANNEL:+  channel $CHANNEL}
  Pi address: 10.42.0.1 (NetworkManager assigns this to a shared connection)

*** The Pi has one Wi-Fi radio. As an access point it CANNOT also be joined to
*** another Wi-Fi network. If you are connected over Wi-Fi right now - SSH or
*** VNC - you will be disconnected. Run this from Ethernet or a local console.

EOF
printf "continue? [y/N] "
read -r reply
case "$reply" in [yY]*) ;; *) echo "cancelled"; exit 0 ;; esac

# ---------------------------------------------------------------- create
if nmcli -t -f NAME connection show | grep -qx "$CON_NAME"; then
    echo "updating existing connection '$CON_NAME'"
else
    echo "creating connection '$CON_NAME'"
    sudo nmcli connection add type wifi ifname "$IFACE" con-name "$CON_NAME" ssid "$SSID" >/dev/null
fi

sudo nmcli connection modify "$CON_NAME" \
    802-11-wireless.ssid "$SSID" \
    802-11-wireless.mode ap \
    802-11-wireless.band "$BAND" \
    ipv4.method shared \
    ipv6.method ignore \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.proto rsn \
    wifi-sec.pairwise ccmp \
    wifi-sec.group ccmp \
    wifi-sec.psk "$PASSWORD" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100

if [ -n "$CHANNEL" ]; then
    sudo nmcli connection modify "$CON_NAME" 802-11-wireless.channel "$CHANNEL"
else
    sudo nmcli connection modify "$CON_NAME" 802-11-wireless.channel 0 2>/dev/null || true
fi

# Stop other wifi profiles from grabbing the radio back after a reboot
nmcli -t -f NAME,TYPE connection show |
    awk -F: -v ap="$CON_NAME" '$2 ~ /wireless/ && $1 != ap {print $1}' |
    while read -r c; do
        echo "  disabling autoconnect on other wifi connection: $c"
        sudo nmcli connection modify "$c" connection.autoconnect no
    done

echo "bringing the AP up"
sudo nmcli connection up "$CON_NAME"
sleep 3

echo
show_status
cat <<EOF

Next:
  1. On a phone or laptop, join the Wi-Fi network "$SSID"
  2. Call the API:
       curl http://10.42.0.1:8080/api/health
       curl "http://10.42.0.1:8080/api/read?ms=1000"

The AP comes back by itself after a reboot. To undo:  ./setup_ap.sh --off
EOF
