#!/bin/bash
# MBRL Scan-to-Print — Start Server
# Double-click this file (or run in Terminal) to launch.

cd "$(dirname "$0")"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MBRL Scan-to-Print  ·  Starting…"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Install dependencies if needed
pip3 install -q -r requirements.txt

# Get local IP
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "unknown")

echo ""
echo "  Webapp URL (open in any browser on lab network):"
echo ""
echo "  ➜  http://localhost:5050      (this Mac)"
echo "  ➜  http://$IP:5050     (iPad / other devices)"
echo ""
echo "  Bookmark the network URL on your iPad."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Open browser on this Mac automatically
sleep 1.5 && open "http://localhost:5050" &

python3 server.py
