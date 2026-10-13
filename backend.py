#!/usr/bin/env python3
"""Omarchy LAN Lockdown Backend Helper.

Provides status queries and executes lockdown / restore procedures.
Manages the decoy honeypot daemon on port 11434.
Privileged actions automatically elevate via pkexec when executed by an unprivileged user.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

STATE_DIR = "/var/lib/lan-lockdown"
STATE_FILE = os.path.join(STATE_DIR, "state.json")
PROBES_FILE = os.path.join(STATE_DIR, "probes.json")
HONEYPOT_PID_FILE = os.path.join(STATE_DIR, "honeypot.pid")
ANONYMOUS_HOSTNAME = "guest-pc"
HONEYPOT_PORT = 11434


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)
    try:
        os.chmod(STATE_DIR, 0o755)
    except Exception:
        pass


def is_root():
    return os.geteuid() == 0


def elevate_if_needed(action):
    """Re-executes this script via pkexec if root privileges are required."""
    if not is_root():
        script_path = os.path.abspath(__file__)
        python_bin = sys.executable
        args = ["pkexec", python_bin, script_path, action]
        try:
            os.execvp("pkexec", args)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"Failed to elevate privileges: {e}"}))
            sys.exit(1)


def read_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def write_state(data):
    ensure_state_dir()
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(STATE_FILE, 0o644)
    except Exception as e:
        print(f"Error saving state: {e}", file=sys.stderr)


def remove_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception:
            pass


def get_current_hostname():
    try:
        proc = subprocess.run(
            ["hostnamectl", "--static"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return socket.gethostname()


def is_service_active(service_name):
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return proc.stdout.strip() == "active"
    except Exception:
        return False


def is_bluetooth_powered():
    try:
        proc = subprocess.run(
            ["bluetoothctl", "show"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return "Powered: yes" in proc.stdout
    except Exception:
        return False


def is_tailscale_active():
    try:
        proc = subprocess.run(
            ["tailscale", "status"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return proc.returncode == 0 and "Tailscale is stopped" not in proc.stdout
    except Exception:
        return False


def is_localsend_running():
    try:
        proc = subprocess.run(
            ["pgrep", "-x", "localsend"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return proc.returncode == 0
    except Exception:
        return False


def is_honeypot_running():
    if os.path.exists(HONEYPOT_PID_FILE):
        try:
            with open(HONEYPOT_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except Exception:
            pass
    return False


def start_honeypot():
    if is_honeypot_running():
        return

    ensure_state_dir()
    honeypot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "honeypot.py")
    if not os.path.exists(honeypot_script):
        return

    try:
        proc = subprocess.Popen(
            [sys.executable, honeypot_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with open(HONEYPOT_PID_FILE, "w") as f:
            f.write(str(proc.pid))
        os.chmod(HONEYPOT_PID_FILE, 0o644)
    except Exception as e:
        print(f"Failed to start honeypot: {e}", file=sys.stderr)

    # Allow port in UFW specifically for decoy
    if shutil.which("ufw"):
        try:
            subprocess.run(["ufw", "allow", f"{HONEYPOT_PORT}/tcp"], check=False, timeout=5)
            subprocess.run(["ufw", "reload"], check=False, timeout=5)
        except Exception:
            pass


def stop_honeypot():
    if os.path.exists(HONEYPOT_PID_FILE):
        try:
            with open(HONEYPOT_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            os.remove(HONEYPOT_PID_FILE)
        except Exception:
            pass

    # Remove UFW decoy rule
    if shutil.which("ufw"):
        try:
            subprocess.run(["ufw", "delete", "allow", f"{HONEYPOT_PORT}/tcp"], check=False, timeout=5)
            subprocess.run(["ufw", "reload"], check=False, timeout=5)
        except Exception:
            pass


def get_recent_probes():
    if os.path.exists(PROBES_FILE):
        try:
            with open(PROBES_FILE, "r") as f:
                probes = json.load(f)
                return probes[:10]
        except Exception:
            pass
    return []


def get_status():
    state = read_state()
    current_host = get_current_hostname()
    avahi_active = is_service_active("avahi-daemon.service")
    bt_powered = is_bluetooth_powered()
    ts_active = is_tailscale_active()
    ls_running = is_localsend_running()
    hp_running = is_honeypot_running()
    probes = get_recent_probes()

    is_locked = False
    original_hostname = ""
    if state and state.get("locked"):
        is_locked = True
        original_hostname = state.get("originalHostname", "")
    elif current_host == ANONYMOUS_HOSTNAME and not avahi_active:
        is_locked = True

    return {
        "ok": True,
        "locked": is_locked,
        "hostname": current_host,
        "originalHostname": original_hostname or current_host,
        "avahiActive": avahi_active,
        "bluetoothPowered": bt_powered,
        "tailscaleActive": ts_active,
        "localsendRunning": ls_running,
        "honeypotRunning": hp_running,
        "probes": probes,
        "probeCount": len(probes),
    }


def engage_lockdown():
    elevate_if_needed("lock")

    current_host = get_current_hostname()
    existing_state = read_state()
    orig_host = current_host

    if existing_state and existing_state.get("originalHostname"):
        orig_host = existing_state["originalHostname"]
    elif current_host == ANONYMOUS_HOSTNAME:
        orig_host = "omarchy-pc"

    # 1. Anonymize hostname
    try:
        subprocess.run(["hostnamectl", "set-hostname", ANONYMOUS_HOSTNAME], check=False, timeout=5)
    except Exception:
        pass

    # 2. Stop & silence Avahi (mDNS broadcast)
    try:
        subprocess.run(
            ["systemctl", "stop", "avahi-daemon.service", "avahi-daemon.socket"],
            check=False,
            timeout=5,
        )
    except Exception:
        pass

    # 3. Enforce strict UFW firewall
    if shutil.which("ufw"):
        try:
            subprocess.run(["ufw", "default", "deny", "incoming"], check=False, timeout=5)
            subprocess.run(["ufw", "default", "allow", "outgoing"], check=False, timeout=5)
            # Remove LocalSend incoming port rules if present
            subprocess.run(["ufw", "delete", "allow", "53317/tcp"], check=False, timeout=5)
            subprocess.run(["ufw", "delete", "allow", "53317/udp"], check=False, timeout=5)
            subprocess.run(["ufw", "reload"], check=False, timeout=5)
        except Exception:
            pass

    # 4. Stop local file share processes
    try:
        subprocess.run(["pkill", "-x", "localsend"], check=False, timeout=2)
    except Exception:
        pass

    # 5. Disable Bluetooth discovery & radio
    if shutil.which("bluetoothctl"):
        try:
            subprocess.run(["bluetoothctl", "power", "off"], check=False, timeout=5)
        except Exception:
            pass

    # 6. Disconnect Tailscale to isolate mesh network
    if shutil.which("tailscale"):
        try:
            subprocess.run(["tailscale", "down"], check=False, timeout=5)
        except Exception:
            pass

    # 7. Start Honeypot Decoy (Ollama on port 11434)
    start_honeypot()

    # 8. Record state
    state_payload = {
        "locked": True,
        "originalHostname": orig_host,
        "timestamp": time.time(),
        "localsendRestorable": True,
        "honeypotActive": True,
    }
    write_state(state_payload)

    return {
        "ok": True,
        "locked": True,
        "message": "LAN Lockdown engaged: Inbound traffic blocked, Avahi silenced, decoy honeypot active.",
    }


def restore_normal():
    elevate_if_needed("unlock")

    existing_state = read_state() or {}
    orig_host = existing_state.get("originalHostname", "")

    # 1. Stop Honeypot
    stop_honeypot()

    # 2. Restore hostname
    if orig_host and orig_host != ANONYMOUS_HOSTNAME:
        try:
            subprocess.run(["hostnamectl", "set-hostname", orig_host], check=False, timeout=5)
        except Exception:
            pass

    # 3. Start Avahi (mDNS)
    try:
        subprocess.run(
            ["systemctl", "start", "avahi-daemon.socket", "avahi-daemon.service"],
            check=False,
            timeout=5,
        )
    except Exception:
        pass

    # 4. Restore UFW LocalSend rule if it was originally present
    if shutil.which("ufw"):
        try:
            if existing_state.get("localsendRestorable", True):
                subprocess.run(["ufw", "allow", "53317/tcp"], check=False, timeout=5)
                subprocess.run(["ufw", "allow", "53317/udp"], check=False, timeout=5)
            subprocess.run(["ufw", "reload"], check=False, timeout=5)
        except Exception:
            pass

    # 5. Restore Bluetooth
    if shutil.which("bluetoothctl"):
        try:
            subprocess.run(["bluetoothctl", "power", "on"], check=False, timeout=5)
        except Exception:
            pass

    # 6. Remove state file
    remove_state()

    return {
        "ok": True,
        "locked": False,
        "message": "Normal network settings restored.",
    }


def toggle():
    status = get_status()
    if status.get("locked"):
        return restore_normal()
    else:
        return engage_lockdown()


def clear_probes():
    if os.path.exists(PROBES_FILE):
        try:
            os.remove(PROBES_FILE)
        except Exception:
            pass
    return {"ok": True, "message": "Probe history cleared"}


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    if action == "status":
        res = get_status()
    elif action == "lock":
        res = engage_lockdown()
    elif action == "unlock":
        res = restore_normal()
    elif action == "toggle":
        res = toggle()
    elif action == "clear-probes":
        res = clear_probes()
    else:
        res = {"ok": False, "error": f"Unknown action: {action}"}

    print(json.dumps(res))


if __name__ == "__main__":
    main()
