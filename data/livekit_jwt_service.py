#!/usr/bin/env python3
"""
Minimal LiveKit JWT token service for Element Call / MatrixRTC.
Listens on port 8880 and issues LiveKit access tokens.
"""
import json
import time
import hmac
import hashlib
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler

LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "supersecretlivekitkey1234567890ab"
LIVEKIT_URL = "ws://192.168.1.199:7880"

def base64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def create_jwt(claims):
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(',', ':')).encode())
    payload_b64 = base64url_encode(json.dumps(claims, separators=(',', ':')).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        LIVEKIT_API_SECRET.encode(),
        signing_input.encode(),
        hashlib.sha256
    ).digest()
    sig_b64 = base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def create_livekit_token(room, identity):
    now = int(time.time())
    claims = {
        "iss": LIVEKIT_API_KEY,
        "sub": identity,
        "iat": now,
        "nbf": now,
        "exp": now + 86400,
        "jti": f"{identity}-{now}",
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
            "canUpdateOwnMetadata": True
        },
        "metadata": "",
        "name": identity
    }
    return create_jwt(claims)

class TokenHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        room = data.get("room", "default-room")
        identity = data.get("openid_token", {}).get("sub", data.get("identity", "anonymous"))

        token = create_livekit_token(room, identity)

        response = json.dumps({"accessToken": token, "url": LIVEKIT_URL})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response.encode())

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[JWT Service] {args[0]}")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8880), TokenHandler)
    print(f"LiveKit JWT service running on http://0.0.0.0:8880")
    print(f"LiveKit URL: {LIVEKIT_URL}")
    server.serve_forever()
