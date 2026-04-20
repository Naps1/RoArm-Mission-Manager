#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo " ============================================="
echo "  RoArm Mission Manager - First-time Setup"
echo " ============================================="
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1)
        # Require Python 3.7+
        major=$("$candidate" -c "import sys; print(sys.version_info.major)")
        minor=$("$candidate" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 7 ]; then
            PYTHON="$candidate"
            echo " [OK] Found $ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo " [ERROR] Python 3.7+ not found."
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo " Install it with:  brew install python3"
        echo " Or download from: https://www.python.org/downloads/"
    else
        echo " Install it with:  sudo apt install python3 python3-pip"
        echo " Or:               sudo dnf install python3"
    fi
    echo ""
    exit 1
fi

# ── Install pyserial (skip if already installed) ──────────────────────────────
echo ""
echo " Checking pyserial..."
if "$PYTHON" -c "import serial" &>/dev/null; then
    echo " [OK] pyserial already installed"
else
    echo " Installing pyserial..."
    "$PYTHON" -m pip install pyserial --quiet --break-system-packages 2>/dev/null \
        || "$PYTHON" -m pip install pyserial --quiet
    if ! "$PYTHON" -c "import serial" &>/dev/null; then
        echo " [ERROR] Failed to install pyserial."
        echo "         Try manually: pip install -r requirements.txt"
        exit 1
    fi
    echo " [OK] pyserial installed"
fi

# ── Detect serial ports ───────────────────────────────────────────────────────
echo ""
echo " Detecting serial ports..."
"$PYTHON" -c "
import serial.tools.list_ports
ports = list(serial.tools.list_ports.comports())
if ports:
    for p in ports:
        print(f'   {p.device}  -  {p.description}')
else:
    print('   (none found - connect the arm and re-run if needed)')
"
echo ""

# ── Ask for port ──────────────────────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    DEFAULT_PORT="/dev/tty.usbserial-0001"
else
    DEFAULT_PORT="/dev/ttyUSB0"
fi

read -rp " Enter serial port [${DEFAULT_PORT}]: " PORT
PORT="${PORT:-$DEFAULT_PORT}"

# ── Linux: offer to add user to dialout group ─────────────────────────────────
if [[ "$OSTYPE" != "darwin"* ]]; then
    if ! groups | grep -qw dialout; then
        echo ""
        echo " [NOTE] Your user is not in the 'dialout' group."
        echo "        Without this you may get 'Permission denied' on the serial port."
        read -rp " Add current user to dialout group? (recommended) [Y/n]: " ADD_GROUP
        if [[ "${ADD_GROUP,,}" != "n" ]]; then
            sudo usermod -aG dialout "$USER"
            echo " [OK] Added to dialout. You'll need to log out and back in for this to take effect."
            echo "      (or run: newgrp dialout  in the terminal where you launch the server)"
        fi
    fi
fi

# ── Write launch.sh ───────────────────────────────────────────────────────────
LAUNCH="$SCRIPT_DIR/launch.sh"
cat > "$LAUNCH" <<LAUNCH_EOF
#!/usr/bin/env bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
echo ""
echo " Starting RoArm Mission Manager on port ${PORT}..."
echo " Open your browser at: http://localhost:5000"
echo " Press Ctrl+C to stop."
echo ""

# Try to open browser after a short delay
if command -v xdg-open &>/dev/null; then
    (sleep 1.5 && xdg-open http://localhost:5000) &
elif command -v open &>/dev/null; then
    (sleep 1.5 && open http://localhost:5000) &
fi

${PYTHON} "\$SCRIPT_DIR/server.py" --port ${PORT}
LAUNCH_EOF

chmod +x "$LAUNCH"

# ── macOS: also create a double-clickable .command file ──────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    COMMAND_FILE="$SCRIPT_DIR/Launch RoArm Manager.command"
    cat > "$COMMAND_FILE" <<CMD_EOF
#!/usr/bin/env bash
cd "\$(dirname "\$0")"
bash launch.sh
CMD_EOF
    chmod +x "$COMMAND_FILE"
    echo " [OK] Created 'Launch RoArm Manager.command' (double-clickable in Finder)"
fi

echo ""
echo " ============================================="
echo "  Setup complete!"
echo " ============================================="
echo ""
echo " To start the Mission Manager, run:"
echo "   ./launch.sh"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo " Or double-click 'Launch RoArm Manager.command' in Finder."
fi
echo ""
echo " Your browser will open automatically."
echo ""
