#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo " ============================================="
echo "  RoArm Mission Manager"
echo " ============================================="
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1)
    # Require Python 3.9+
    major=$("$candidate" -c "import sys; print(sys.version_info.major)")
    minor=$("$candidate" -c "import sys; print(sys.version_info.minor)")
    if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
      PYTHON="$candidate"
      echo " [OK] Found $ver"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo " [ERROR] Python 3.9+ not found."
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

# ── Check tkinter ─────────────────────────────────────────────────────────────
echo ""
echo " Checking tkinter..."
if "$PYTHON" -c "import tkinter" &>/dev/null; then
  echo " [OK] tkinter available"
else
  echo " [ERROR] tkinter not found."
  echo ""
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo " Install it with:  brew install python-tk"
  elif command -v apt &>/dev/null; then
    echo " Install it with:  sudo apt install python3-tk"
  elif command -v dnf &>/dev/null; then
    echo " Install it with:  sudo dnf install python3-tkinter"
  elif command -v pacman &>/dev/null; then
    echo " Install it with:  sudo pacman -S tk"
  else
    echo " Install the tkinter package for your distribution."
  fi
  echo ""
  exit 1
fi

# ── Install pyserial ──────────────────────────────────────────────────────────
echo ""
echo " Checking pyserial..."
if "$PYTHON" -c "import serial" &>/dev/null; then
  echo " [OK] pyserial already installed"
else
  echo " Installing pyserial..."
  "$PYTHON" -m pip install pyserial --quiet --break-system-packages 2>/dev/null ||
    "$PYTHON" -m pip install pyserial --quiet
  if ! "$PYTHON" -c "import serial" &>/dev/null; then
    echo " [ERROR] Failed to install pyserial."
    echo "         Try manually: pip install -r requirements.txt"
    exit 1
  fi
  echo " [OK] pyserial installed"
fi

# ── Linux: offer to add user to dialout group ─────────────────────────────────
if [[ "$OSTYPE" != "darwin"* ]]; then
  if ! groups | grep -qw dialout; then
    echo ""
    echo " [NOTE] Your user is not in the 'dialout' group."
    echo "        Without this you may get 'Permission denied' on the serial port."
    read -rp " Add current user to dialout group? (recommended) [Y/n]: " ADD_GROUP
    if [[ "${ADD_GROUP,,}" != "n" ]]; then
      sudo usermod -aG dialout "$USER"
      echo " [OK] Added to dialout. Log out and back in for this to take effect."
      echo "      Or run: newgrp dialout"
    fi
  fi
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo " Starting launcher..."
echo ""
"$PYTHON" "$SCRIPT_DIR/launcher.py"
