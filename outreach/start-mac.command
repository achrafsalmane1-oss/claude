#!/usr/bin/env bash
# Double-click this file to start Outreach. Close the Terminal window to stop it.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "  Python 3 isn't installed on this Mac."
  echo "  Install it from https://www.python.org/downloads/ (click the big yellow button,"
  echo "  open the downloaded file, click Continue/Install), then double-click this file again."
  echo ""
  read -r -p "Press Return to close."
  exit 1
fi

echo "Starting Outreach… your browser will open in a second."
echo "Leave this window open while you use the app. Close it to stop."
echo ""
python3 app.py --open
read -r -p "Outreach stopped. Press Return to close."
