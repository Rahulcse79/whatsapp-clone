PYTHON=/usr/local/bin/python3.11

# Auto-detect current LAN IP
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

echo "Detected IP: $IP"

# Update public_baseurl in homeserver.yaml
sed -i '' "s|public_baseurl: .*|public_baseurl: \"https://$IP:8008/\"|" data/homeserver.yaml

# Kill any existing Synapse on port 8008
kill $(lsof -ti :8008) 2>/dev/null

# Replace default Synapse static page with WhatsApp Clone branding
SYNAPSE_DIR=$($PYTHON -c "import synapse, os; print(os.path.dirname(synapse.__file__))")
cp synapse_v98_backup/static/index.html "$SYNAPSE_DIR/static/index.html" 2>/dev/null || \
  sudo cp synapse_v98_backup/static/index.html "$SYNAPSE_DIR/static/index.html"
echo "Custom landing page applied."

echo "Starting Synapse at https://$IP:8008 ..."
$PYTHON -m synapse.app.homeserver -c data/homeserver.yaml
