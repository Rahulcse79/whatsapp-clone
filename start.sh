PYTHON=/usr/local/bin/python3.11

# Auto-detect current LAN IP
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

echo "Detected IP: $IP"

# Update public_baseurl in homeserver.yaml
sed -i '' "s|public_baseurl: .*|public_baseurl: \"https://$IP:8008/\"|" data/homeserver.yaml

# Kill any existing Synapse on port 8008
kill $(lsof -ti :8008) 2>/dev/null

echo "Starting Synapse at https://$IP:8008 ..."
$PYTHON -m synapse.app.homeserver -c data/homeserver.yaml
