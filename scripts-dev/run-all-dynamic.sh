#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
CONFIG_FILE="$DATA_DIR/homeserver.yaml"
CERT_DIR="$DATA_DIR/certs"
DOWNLOAD_DIR="$CERT_DIR/download"

SYN_PID_FILE="$DATA_DIR/synapse-run.pid"
SYN_LOG_FILE="$DATA_DIR/synapse-run.log"
CERT_PID_FILE="$DATA_DIR/certs-download.pid"
CERT_LOG_FILE="$DATA_DIR/certs-download.log"

resolve_ip() {
    local ip=""
    local iface=""

    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return 0
    fi

    iface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')"
    if [[ -n "$iface" ]]; then
        ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    fi

    if [[ -z "$ip" ]]; then
        ip="$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')"
    fi

    if [[ -z "$ip" ]]; then
        echo "ERROR: could not detect local IP address" >&2
        exit 1
    fi

    echo "$ip"
}

stop_pid_if_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid="$(tr -d '[:space:]' < "$pid_file")"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" || true
        fi
        rm -f "$pid_file"
    fi
}

ensure_ca() {
    mkdir -p "$CERT_DIR" "$DOWNLOAD_DIR"

    if [[ ! -f "$CERT_DIR/ca.key" || ! -f "$CERT_DIR/ca.crt" ]]; then
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

    if [[ ! -f "$crt_file" ]] || ! openssl x509 -in "$crt_file" -noout -ext subjectAltName 2>/dev/null | grep -q "IP Address:${ip}"; then
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
    fi

    cp "$CERT_DIR/ca.crt" "$DOWNLOAD_DIR/synapse-ca-${ip}.crt"
}

update_homeserver_config() {
    local ip="$1"
    local cert_path="$CERT_DIR/synapse-${ip}.crt"
    local key_path="$CERT_DIR/synapse-${ip}.key"

    perl -0777 -i -pe "s|public_baseurl:\s*\"[^\"]*\"|public_baseurl: \"https://${ip}:8480/\"|g" "$CONFIG_FILE"
    perl -0777 -i -pe "s|tls_certificate_path:\s*\"[^\"]*\"|tls_certificate_path: \"${cert_path}\"|g" "$CONFIG_FILE"
    perl -0777 -i -pe "s|tls_private_key_path:\s*\"[^\"]*\"|tls_private_key_path: \"${key_path}\"|g" "$CONFIG_FILE"
}

start_cert_download_server() {
    local ip="$1"
    stop_pid_if_running "$CERT_PID_FILE"

    nohup python3 -m http.server 9999 \
        --bind "$ip" \
        --directory "$DOWNLOAD_DIR" \
        > "$CERT_LOG_FILE" 2>&1 &
    echo $! > "$CERT_PID_FILE"
}

run_synapse_foreground() {
    if python3 -m poetry --version >/dev/null 2>&1; then
        python3 -m poetry run python -m synapse.app.homeserver \
            --config-path "$CONFIG_FILE"
    else
        python3 -m synapse.app.homeserver \
            --config-path "$CONFIG_FILE"
    fi
}

http_code() {
    local url="$1"
    local tls_opt="${2:-}"
    if [[ "$tls_opt" == "-k" ]]; then
        curl -sk --connect-timeout 1 --max-time 2 -o /dev/null -w '%{http_code}' "$url" || true
    else
        curl -s --connect-timeout 1 --max-time 2 -o /dev/null -w '%{http_code}' "$url" || true
    fi
}

wait_for_200() {
    local url="$1"
    local tls_opt="${2:-}"
    local attempts="${3:-40}"
    local code=""

    for _ in $(seq 1 "$attempts"); do
        code="$(http_code "$url" "$tls_opt")"
        if [[ "$code" == "200" ]]; then
            echo "$code"
            return 0
        fi
        perl -e 'select(undef, undef, undef, 0.25);'
    done

    echo "$code"
    return 1
}

main() {
    local ip
    ip="$(resolve_ip "${1:-}")"

    ensure_ca
    ensure_server_cert_for_ip "$ip"
    update_homeserver_config "$ip"

    # Start cert download server in background
    start_cert_download_server "$ip"

    # Cleanup on Ctrl+C / exit
    trap 'echo ""; echo "Stopping cert server..."; stop_pid_if_running "$CERT_PID_FILE"; echo "Stopped."; exit 0' INT TERM EXIT

    local http_url="http://${ip}:8080/_matrix/static/"
    local https_url="https://${ip}:8480/_matrix/static/"
    local cert_url="http://${ip}:9999/synapse-ca-${ip}.crt"

    echo ""
    echo "IP=${ip}"
    echo "  HTTP  : ${http_url}"
    echo "  HTTPS : ${https_url}"
    echo "  CERT  : ${cert_url}"
    echo ""
    echo "Starting Synapse (foreground) — press Ctrl+C to stop"
    echo "------------------------------------------------------"

    run_synapse_foreground
}

main "$@"
