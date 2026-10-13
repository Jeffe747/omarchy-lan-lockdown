#!/usr/bin/env python3
"""Lightweight Ollama & Developer Decoy Honeypot.

Listens on port 11434 (default Ollama port), captures prober IPs, MAC addresses,
User-Agents, and payloads, dispatches desktop notifications, and logs entries.
Runs strictly in memory without executing any incoming data.
"""

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time

PORT = 11434
STATE_DIR = "/var/lib/lan-lockdown"
PROBES_FILE = os.path.join(STATE_DIR, "probes.json")
PID_FILE = os.path.join(STATE_DIR, "honeypot.pid")
MAX_STORED_PROBES = 50


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o755)
    except Exception:
        pass


def get_mac_address(ip):
    """Resolve MAC address from Linux ARP/neighbor table."""
    try:
        proc = subprocess.run(
            ["ip", "neigh", "show", ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        for line in proc.stdout.splitlines():
            match = re.search(r"lladdr\s+([0-9a-fA-F:]{17})", line)
            if match:
                return match.group(1).lower()
    except Exception:
        pass
    return "unknown"


def get_hostname(ip):
    """Attempt reverse DNS or hostname resolution."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def send_desktop_notification(ip, mac, path, user_agent):
    """Dispatches a desktop alert via notify-send."""
    title = "🚨 Honeypot Probe Detected!"
    msg = f"Host: {ip} ({mac})\nTool: {user_agent[:40]}\nTarget: {path[:40]}"

    # Try directly
    try:
        subprocess.run(
            ["notify-send", "-u", "critical", "-i", "security-high", title, msg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except Exception:
        pass

    # If running as root, attempt to notify desktop user (e.g. uid 1000)
    if os.geteuid() == 0:
        try:
            target_user = os.environ.get("SUDO_USER", "jaj")
            cmd = f'export DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; notify-send -u critical -i security-high "{title}" "{msg}"'
            subprocess.run(["su", "-", target_user, "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass


def record_probe(client_ip, client_port, method, path, headers, body_preview=""):
    ensure_state_dir()

    mac = get_mac_address(client_ip)
    hostname = get_hostname(client_ip)
    user_agent = headers.get("User-Agent", "Unknown / None")
    now = datetime.now()

    entry = {
        "timestamp": time.time(),
        "time_str": now.strftime("%H:%M:%S"),
        "date_str": now.strftime("%Y-%m-%d"),
        "ip": client_ip,
        "port": client_port,
        "mac": mac,
        "hostname": hostname,
        "method": method,
        "path": path,
        "user_agent": user_agent,
        "payload": body_preview[:256] if body_preview else "",
    }

    probes = []
    if os.path.exists(PROBES_FILE):
        try:
            with open(PROBES_FILE, "r") as f:
                probes = json.load(f)
        except Exception:
            probes = []

    probes.insert(0, entry)
    probes = probes[:MAX_STORED_PROBES]

    try:
        with open(PROBES_FILE, "w") as f:
            json.dump(probes, f, indent=2)
        os.chmod(PROBES_FILE, 0o644)
    except Exception as e:
        print(f"Error saving probe: {e}", file=sys.stderr)

    send_desktop_notification(client_ip, mac, path, user_agent)


class HoneypotHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default stderr logging to keep daemon quiet
        pass

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = ""
        if content_len > 0:
            try:
                body = self.rfile.read(min(content_len, 2048)).decode("utf-8", errors="replace")
            except Exception:
                body = "<binary or decode error>"
        self._handle_request("POST", body)

    def do_HEAD(self):
        self._handle_request("HEAD")

    def _handle_request(self, method, body=""):
        client_ip = self.client_address[0]
        client_port = self.client_address[1]

        # Ignore local loopback requests from ourselves
        if client_ip not in ("127.0.0.1", "::1"):
            threading.Thread(
                target=record_probe,
                args=(client_ip, client_port, method, self.path, dict(self.headers), body),
                daemon=True,
            ).start()

        # Generate realistic Ollama decoy responses to lure agent tools
        if self.path in ("/api/tags", "/api/tags/"):
            response_data = {
                "models": [
                    {
                        "name": "llama3:latest",
                        "model": "llama3:latest",
                        "modified_at": "2026-10-13T12:00:00Z",
                        "size": 4661224676,
                        "digest": "365c0bd3c000",
                        "details": {
                            "format": "gguf",
                            "family": "llama",
                            "parameter_size": "8.0B",
                            "quantization_level": "Q4_0",
                        },
                    }
                ]
            }
            body_bytes = json.dumps(response_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        elif self.path in ("/api/version", "/api/version/"):
            body_bytes = b'{"version":"0.1.48"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        elif self.path in ("/api/generate", "/api/chat"):
            # Acknowledge generation to see what the agent asks
            response_data = {
                "model": "llama3:latest",
                "created_at": datetime.now().isoformat() + "Z",
                "response": "Access restricted. LAN security policy active.",
                "done": True,
            }
            body_bytes = json.dumps(response_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        elif self.path == "/":
            body_bytes = b"Ollama is running\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        else:
            body_bytes = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)


def run_server():
    ensure_state_dir()

    # Save PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    def sig_handler(_signum, _frame):
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), HoneypotHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Honeypot failed to start: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
