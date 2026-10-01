#!/usr/bin/env bash
# Install the RFID API as a systemd service so it starts at boot and waits for
# REST requests. Run from the repo directory:
#
#     ./install.sh
#
# Re-running is safe - it rewrites the unit and restarts the service.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
UNIT=/etc/systemd/system/rfid-api.service

# Prefer the venv in the repo if there is one, so its packages are the ones used
if [ -x "$DIR/venv/bin/python3" ]; then
    PYTHON="$DIR/venv/bin/python3"
elif [ -x "$DIR/.venv/bin/python3" ]; then
    PYTHON="$DIR/.venv/bin/python3"
else
    PYTHON="$(command -v python3)"
fi

echo "user   : $USER_NAME"
echo "dir    : $DIR"
echo "python : $PYTHON"

# Serial access. Takes effect on next login for the current shell, but the
# service runs with Group=dialout so it works immediately.
if ! id -nG "$USER_NAME" | tr ' ' '\n' | grep -qx dialout; then
    echo "adding $USER_NAME to the dialout group"
    sudo usermod -aG dialout "$USER_NAME"
fi

echo "checking dependencies"
"$PYTHON" - <<'PY'
import importlib, sys
missing = [m for m in ("serial", "flask") if not importlib.util.find_spec(m)]
if missing:
    sys.exit("missing: %s - run: pip3 install -r requirements.txt" % ", ".join(missing))
print("  pyserial, flask present")
print("  waitress present" if importlib.util.find_spec("waitress")
      else "  waitress NOT present - the Flask dev server will be used instead")
PY

echo "writing $UNIT"
sed -e "s|__USER__|$USER_NAME|g" \
    -e "s|__DIR__|$DIR|g" \
    -e "s|__PYTHON__|$PYTHON|g" \
    "$DIR/rfid-api.service" | sudo tee "$UNIT" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable rfid-api
sudo systemctl restart rfid-api
sleep 3

echo
sudo systemctl status rfid-api --no-pager -l | head -20
echo
PORT="$(grep -oP 'RFID_PORT=\K[0-9]+' "$DIR/rfid-api.service" || echo 8080)"
echo "test it:"
echo "  curl http://localhost:$PORT/api/health"
echo "  curl \"http://localhost:$PORT/api/read?ms=1000\""
echo "logs:"
echo "  journalctl -u rfid-api -f"
