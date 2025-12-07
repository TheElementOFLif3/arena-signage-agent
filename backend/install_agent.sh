#!/usr/bin/env bash
set -e

echo "== ArenaSignage Agent installer =="

# Always work from the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] Script directory: $SCRIPT_DIR"

# --- Ensure system packages ---------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
  echo "[INFO] Installing python3..."
  sudo apt update
  sudo apt install -y python3
fi

if ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo "[INFO] Installing python3-venv..."
  sudo apt update
  sudo apt install -y python3-venv
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[INFO] Installing git..."
  sudo apt update
  sudo apt install -y git
fi

# --- Create virtual environment ----------------------------------------------

echo "[INFO] Python version:"
python3 --version

if [ ! -d "venv" ]; then
  echo "[INFO] Creating virtual environment..."
  python3 -m venv venv
else
  echo "[INFO] Reusing existing virtual environment (venv/)."
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[INFO] Upgrading pip and installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "[OK] Installation complete."
echo "To configure the agent run:"
echo "  cd \"$SCRIPT_DIR\""
echo "  source venv/bin/activate"
echo "  python3 configure_agent.py"
echo
echo "To start the agent:"
echo "  cd \"$SCRIPT_DIR\""
echo "  source venv/bin/activate"
echo "  python3 pi_agent.py"
echo