# Project Context & Session History

This document preserves the context, threat model, architectural decisions, and verification logs for `omarchy-lan-lockdown` so work can seamlessly continue in future sessions.

---

## 1. Background & Threat Model

### The Problem
* **Scenario:** Attending a LAN party or untrusted local network.
* **Threat Profile:** Other attendees running autonomous security agents, penetration testing tools, port scanners, and banner grabbers (e.g. PentestGPT, AutoGPT, Nmap, masscan).
* **Vulnerabilities on LAN:**
  1. **mDNS Profiling:** `avahi-daemon` broadcasting personal hostname (`JeffesMacBookAir.local`) and OS details on UDP `5353`.
  2. **Exposed Local Services:** Local file-sharing services (e.g. LocalSend on port `53317`) and dev/AI endpoints.
  3. **Mesh VPN Bridging:** Tailscale tunnels potentially accessible from LAN peers.
  4. **Peripheral Risks:** Bluetooth discoverability.

### The Constraint: Gaming Must Still Work
* Modern multiplayer games (Steam, Proton, matchmaking, anti-cheat, Discord) only initiate **outbound** connections.
* Linux stateful connection tracking (`conntrack` in UFW / iptables / nftables) automatically admits inbound return packets for existing outbound sessions.
* **Conclusion:** You do not need any open inbound ports to join games, play online, or use voice chat. Inbound ports are only needed if locally hosting a LAN server.

---

## 2. Implemented Architecture

### Components & Repositories
* **GitHub Repository:** [`Jeffe747/omarchy-lan-lockdown`](https://github.com/Jeffe747/omarchy-lan-lockdown)
* **Local Source:** `/home/jaj/Work/omarchy-lan-lockdown`
* **Installed Plugin:** `~/.config/omarchy/plugins/jeffe747.lan-lockdown`
* **Plugin Namespace:** `jeffe747.lan-lockdown` (per Omarchy rules, third-party plugins must avoid reserved `omarchy.*` namespace)

### File Structure
```
omarchy-lan-lockdown/
├── manifest.json       # Omarchy plugin manifest (schemaVersion 1, bar-widget)
├── Panel.qml           # Quickshell UI: BarIconButton + interactive KeyboardPanel
├── backend.py          # Core engine (status, lock, unlock, toggle, report)
├── honeypot.py         # In-memory Ollama decoy trap on port 11434
├── README.md           # Comprehensive user & installation documentation
└── CONTEXT.md          # This context record
```

---

## 3. Key Technical Decisions & Solved Issues

### Visuals & Icons (Option 2 Selected)
* **Inactive (Standby):** `󰒙` (`nf-md-shield_outline` — hollow shield outline).
* **Active (Lockdown + Honeypot):** `󰦝` (`nf-md-shield_lock` — shield with padlock).
* *Note:* Avoided `󰀝` as it mapped to an airplane icon in JetBrainsMono Nerd Font.

### QML Property Fix
* `BarIconButton` in Omarchy inherits from `WidgetButton` and does not have a `color` property.
* Resolved by setting `active: root.lockedDown`, `useActiveColor: true`, `activeColor: ...`, and `foreground: ...`.

### Privilege Escalation & Process Inspection
* **Unprivileged Status Checks:** `backend.py status` runs completely without root (queries hostname, `systemctl is-active`, bluetoothctl, reads state files).
* **Auto-Elevation:** Mutating actions (`lock`, `unlock`, `toggle`) detect non-root execution and automatically elevate via `pkexec`, triggering Omarchy's native Polkit popup.
* **EPERM Handling:** When checking if `honeypot.py` is running (`os.kill(pid, 0)`), Python raises `OSError` with `errno.EPERM` because the honeypot process is owned by `root`. This is handled to correctly recognize that the process is running.

---

## 4. The Decoy Honeypot System

### Why Port 11434 (Ollama)?
Autonomous pentesting agents specifically look for unprotected LLM/Ollama API endpoints on LANs. 

### What it Captures:
1. **Hardware MAC Address:** Queries `ip neigh show <ip>` from the Linux kernel ARP table to identify the attacker's physical NIC.
2. **Scanner Fingerprint:** Captures the `User-Agent` (e.g. `python-requests`, `aiohttp`, `Go-http-client`, `LangChain`, `nmap`).
3. **Targets & Payloads:** Logs requested URIs (`/api/tags`, `/api/generate`, `/.env`) and payloads.
4. **Immediate Alerting:** Dispatches high-urgency `notify-send -u critical` alerts to the desktop.
5. **Reporting:**
   * One-click export from the UI to `~/Desktop/lan-honeypot-report.md`.
   * CLI command: `python3 backend.py report`.

---

## 5. Live Verification Log (2026-10-13)

Both transitions were tested and verified live on the user's Omarchy system:

### Activation Verification:
* Hostname successfully changed from `JeffesMacBookAir` to `guest-pc`.
* Original hostname recorded in `/var/lib/lan-lockdown/state.json`.
* `avahi-daemon.service` stopped.
* Port `53317` (LocalSend) removed from UFW rules.
* Port `11434` added to UFW rules for honeypot.
* `honeypot.py` verified listening on `0.0.0.0:11434` and responding to simulated Ollama requests.
* Bluetooth powered off (`Powered: no`).
* Bar icon switched to `󰦝` (shield with lock).

### Restoration Verification:
* Hostname restored to `JeffesMacBookAir`.
* `avahi-daemon.service` active.
* Port `11434` closed and removed from UFW.
* Port `53317` restored in UFW.
* Bluetooth powered back on (`Powered: yes`).
* State directory `/var/lib/lan-lockdown/` cleaned up.
* Bar icon returned to `󰒙` (hollow outline).

---

## 6. Future Ideas & Backlog

When resuming this project, potential enhancements include:
1. **Multi-Port Decoy Matrix:** Add optional decoys for port 22 (fake SSH banner) or port 80/8080 (fake router/web admin page).
2. **Audio / Chime Alerts:** Play a discreet sound effect on probe detection.
3. **Automated Packet Capture (PCAP):** Capture the full TCP packet exchange of probers to `~/Desktop/honeypot-probe.pcap`.
4. **Custom LAN Game Profiles:** Add a quick "Host Game" dialog allowing a specific port (e.g. 25565 or 27015) to be opened for the duration of a match.
