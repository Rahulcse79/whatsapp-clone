#!/usr/bin/env bash
# start.sh — Detects the local LAN IP, updates homeserver.yaml, ensures TLS
# certs exist, starts Synapse, and then launches the sliding-sync proxy.

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SYNAPSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SYNAPSE_DIR/data"
CERT_DIR="$DATA_DIR/certs"
TEMPLATE="$DATA_DIR/homeserver.yaml.template"
CONFIG="$DATA_DIR/homeserver.yaml"
SLIDING_SYNC_DIR="${SLIDING_SYNC_DIR:-/Users/muskansethi/Documents/GitHub/whatsapp-clone-sliding-sync}"
SYNAPSE_PID_FILE="$DATA_DIR/homeserver.pid"

# ── Detect local IP ──────────────────────────────────────────────────────────
resolve_ip() {
    local ip=""
    local iface=""

    # Accept an explicit override as the first argument.
    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return 0
    fi

    # macOS: use the default-route interface.
    iface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')"
    if [[ -n "$iface" ]]; then
        ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    fi

    # Fallback: first non-loopback inet address.
    if [[ -z "$ip" ]]; then
        ip="$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')"
    fi

    if [[ -z "$ip" ]]; then
        echo "ERROR: could not detect local IP address" >&2
        exit 1
    fi

    echo "$ip"
}

# ── TLS cert helpers (mirrors sliding-sync script) ───────────────────────────
ensure_ca() {
    mkdir -p "$CERT_DIR"

    if [[ ! -f "$CERT_DIR/ca.key" || ! -f "$CERT_DIR/ca.crt" ]]; then
        echo "→ Generating CA key/cert …"
        openssl genrsa -out "$CERT_DIR/ca.key" 4096
        openssl req -x509 -new -nodes \
            -key "$CERT_DIR/ca.key" \
            -sha256 -days 3650 \
            -out "$CERT_DIR/ca.crt" \
            -subj "/C=US/ST=NA/L=NA/O=WhatsAppClone/OU=Dev/CN=WhatsAppClone-CA"
    fi
}

ensure_server_cert_for_ip() {
    local ip="$1"
    local key_file="$CERT_DIR/synapse-${ip}.key"
    local csr_file="$CERT_DIR/synapse-${ip}.csr"
    local crt_file="$CERT_DIR/synapse-${ip}.crt"
    local ext_file="$CERT_DIR/synapse-${ip}.ext"

    # Regenerate if cert is missing or does not have the right SAN.
    if [[ ! -f "$crt_file" ]] || \
       ! openssl x509 -in "$crt_file" -noout -ext subjectAltName 2>/dev/null \
           | grep -q "IP Address:${ip}"; then

        echo "→ Generating TLS cert for IP ${ip} …"
        openssl genrsa -out "$key_file" 2048
        openssl req -new \
            -key "$key_file" \
            -out "$csr_file" \
            -subj "/C=US/ST=NA/L=NA/O=WhatsAppClone/OU=Dev/CN=${ip}"

        cat > "$ext_file" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
IP.1=${ip}
EOF

        openssl x509 -req \
            -in "$csr_file" \
            -CA "$CERT_DIR/ca.crt" \
            -CAkey "$CERT_DIR/ca.key" \
            -CAcreateserial \
            -out "$crt_file" \
            -days 825 \
            -sha256 \
            -extfile "$ext_file"

        rm -f "$csr_file" "$ext_file"
        echo "  cert → $crt_file"
        echo "  key  → $key_file"
    else
        echo "→ TLS cert for ${ip} already up to date."
    fi
}

# ── Render homeserver.yaml from template ─────────────────────────────────────
render_config() {
    local ip="$1"
    echo "→ Writing $CONFIG with IP=${ip} …"
    sed "s/__LOCAL_IP__/${ip}/g" "$TEMPLATE" > "$CONFIG"
}

# ── Stop any running Synapse ──────────────────────────────────────────────────
stop_synapse_if_running() {
    if [[ -f "$SYNAPSE_PID_FILE" ]]; then
        local pid
        pid="$(tr -d '[:space:]' < "$SYNAPSE_PID_FILE")"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "→ Stopping existing Synapse (PID ${pid}) …"
            kill "$pid" || true
            sleep 1
        fi
        rm -f "$SYNAPSE_PID_FILE"
    fi
}

# ── Start Synapse ─────────────────────────────────────────────────────────────
start_synapse() {
    echo "→ Starting Synapse …"

    # Prefer the installed synctl/synapse_homeserver from user site-packages bin.
    # Fall back to python3 -m if the binary isn't on PATH.
    local user_bin="/Users/muskansethi/Library/Python/3.9/bin"
    if [[ -x "$user_bin/synapse_homeserver" ]]; then
        "$user_bin/synapse_homeserver" \
            --config-path "$CONFIG" \
            --daemonize \
            -D
    else
        # Do not override PYTHONPATH inside an active virtual environment.
        if [[ -z "${VIRTUAL_ENV:-}" ]]; then
            export PYTHONPATH="$SYNAPSE_DIR"
        fi
        python3 -m synapse.app.homeserver \
            --config-path "$CONFIG" \
            --daemonize \
            -D
    fi
}

# ── Start sliding-sync proxy ──────────────────────────────────────────────────
start_sliding_sync() {
    local ip="$1"
    echo "→ Starting sliding-sync proxy (IP=${ip}) …"
    bash "$SLIDING_SYNC_DIR/scripts/run-dual-syncv3.sh" start "$ip"
}

# ── Print connection info ─────────────────────────────────────────────────────
print_urls() {
    local ip="$1"
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "  Mobile client settings"
    echo "    Homeserver URL  https://${ip}:8480"
    echo "    Sliding Sync    native via Synapse /versions"
    echo ""
    echo "  Synapse"
    echo "    HTTP   http://${ip}:8080/_matrix/static/"
    echo "    HTTPS  https://${ip}:8480/_matrix/static/"
    echo ""
    echo "  Sliding-Sync proxy"
    echo "    HTTP   http://${ip}:8008/client/"
    echo "    HTTPS  https://${ip}:8448/client/"
    echo ""
    echo "  CA cert (install on devices)"
    echo "    http://${ip}:9999/synapse-ca-${ip}.crt"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
}

# ── Stop mode ────────────────────────────────────────────────────────────────
stop_all() {
    echo "→ Stopping sliding-sync proxy …"
    bash "$SLIDING_SYNC_DIR/scripts/run-dual-syncv3.sh" stop || true
    stop_synapse_if_running
    echo "Done."
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    local mode="${1:-start}"

    case "$mode" in
        stop)
            stop_all
            exit 0
            ;;
        start) ;;
        *)
            echo "Usage: $0 [start|stop] [ip]" >&2
            exit 1
            ;;
    esac

    local ip
    ip="$(resolve_ip "${2:-}")"

    echo "Detected IP: ${ip}"

    ensure_ca
    ensure_server_cert_for_ip "$ip"
    render_config "$ip"
    stop_synapse_if_running
    start_synapse
    start_sliding_sync "$ip"
    print_urls "$ip"
}

main "$@"
