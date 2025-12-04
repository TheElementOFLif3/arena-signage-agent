#!/usr/bin/env bash
set -e

echo "=== ArenaSignage Agent installer ==="

# 1. Install Python & tools if missing (Debian/Ubuntu style)
if ! command -v python3 >/dev/null 2>&1; then
  echo "[INFO] Python3 not found, installing..."
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip
else
  echo "[INFO] Python3 found: $(python3 --version)"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "[INFO] git not found, installing..."
  sudo apt-get update
  sudo apt-get install -y git
fi

# 2. Go to backend directory where pi_agent.py lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

# 3. Create virtualenv if not exists
if [ ! -d "venv" ]; then
  echo "[INFO] Creating Python virtualenv..."
  python3 -m venv venv
fi

# 4. Activate venv and install requirements
echo "[INFO] Activating virtualenv..."
# shellcheck source=/dev/null
source venv/bin/activate

echo "[INFO] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Run configuration menu
echo
echo "[INFO] Running agent configuration..."
python3 configure_agent.py

echo
echo "=== Installation finished ==="
echo "To start the agent manually, run:"
echo "  cd \"$SCRIPT_DIR/backend\""
echo "  source venv/bin/activate"
echo "  python3 pi_agent.py"
echo