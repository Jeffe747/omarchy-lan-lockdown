# omarchy-lan-lockdown

🛡️ **One-click stealth, inbound firewall lockdown, and autonomous agent honeypot for Omarchy Linux.**

Play games freely while completely locking down your machine against automated port scanners, network fuzzers, and autonomous reconnaissance agents—and catch attackers in the act.

---

## ⚡ What it Does

When you're at a LAN party or on an untrusted network, attackers and automated AI agents sweep the local subnet for open services, vulnerable ports, mDNS broadcasts, and device fingerprints.

**LAN Lockdown** gives you a one-click toggle directly in your Omarchy status bar:

| Feature | Normal Mode | 🛡️ LAN Lockdown Mode |
| :--- | :--- | :--- |
| **Inbound Firewall (UFW)** | Standard rules (LocalSend, etc. allowed) | **Strictly drops all unsolicited inbound traffic** |
| **mDNS / Bonjour Broadcast** | `avahi-daemon` active (`hostname.local`) | **Silenced & stopped** (zero network broadcasts) |
| **Hostname Profile** | Your personal machine name | **Masked as `guest-pc`** (restores original on disable) |
| **Local File Shares** | LocalSend / file sharing apps active | **Closed & stopped** |
| **Bluetooth** | Discoverable/Powered | **Powered off** |
| **Tailscale** | Connected | **Disconnected** (`tailscale down`) |
| **🪤 Decoy Honeypot** | Inactive | **Active on port 11434 (Ollama bait)** |
| **Gaming (Steam, Proton, Online)** | Working | **100% Working** |

> [!NOTE]
> **Why doesn't this break online gaming?**  
> Modern games, Steam, matchmaking, Discord, and anti-cheat only require **outbound** network connections. Linux uses a stateful firewall (`conntrack`), so when your game connects out to a game lobby or matchmaking server, return packets are automatically permitted back in.

---

## 🪤 The Agent-Bait Honeypot

Scanning agents (like AutoGPT, PentestGPT, or custom network crawlers) specifically probe port **`11434`** looking for unauthenticated Ollama/LLM endpoints.

When LAN Lockdown is active, a lightweight in-memory HTTP sinkhole starts on port `11434` mimicking a live Ollama instance. When an agent or scanner touches it:

1. **Captures Hardware MAC:** Queries the Linux kernel ARP/neighbor table (`ip neigh`) to grab the prober's hardware MAC address.
2. **Captures Software Fingerprint:** Extracts `User-Agent` (e.g. `python-requests`, `Go-http-client`, `LangChain`, `curl`, `nmap`).
3. **Captures Targets & Payloads:** Logs the exact paths requested (`/api/tags`, `/.env`, `/admin`) and prompt payloads.
4. **Desktop Notification:** Dispatches an immediate high-priority Omarchy desktop notification:
   ```
   🚨 Honeypot Probe Detected!
   Host: 192.168.86.105 (f4:f5:e8:71:22:90)
   Tool: python-requests/2.31.0
   Target: GET /api/tags
   ```
5. **Panel Feed:** Displays recent probes directly in the Omarchy status bar popup card.

---

## 📦 Installation

Install directly via the Omarchy plugin manager:

```bash
omarchy plugin add https://github.com/Jeffe747/omarchy-lan-lockdown.git --enable
```

*When prompted for placement, choose `right` (or place it next to your network widgets).*

---

## 🚀 Usage

### 1. From the Status Bar
Click the shield icon in your top bar:
- **`󰀝` (Muted Shield):** Standard network mode.
- **`󰒃` (Active Shield):** LAN Lockdown is engaged (Stealth + Honeypot).

Clicking opens the quick card where you can see:
* The live status of each protection layer.
* Active honeypot status.
* Live feed of captured probes (IP, MAC address, tool, target).
* One-click toggle button.

### 2. From Omarchy Menu (`SUPER + SPACE`)
You can optionally register a toggle in `~/.config/omarchy/extensions/omarchy-menu.jsonc`:

```jsonc
{
  "trigger.lan-lockdown": {
    "icon": "󰒃",
    "label": "LAN Lockdown",
    "description": "Toggle stealth LAN mode and inbound firewall block",
    "checked": "[[ \"$(python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py status | jq -r .locked)\" == \"true\" ]]",
    "action": "python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py toggle"
  }
}
```

### 3. CLI
You can also inspect, toggle, or view probes directly from your terminal:

```bash
# Query status and recent probes (JSON)
python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py status

# Toggle lockdown
python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py toggle

# Clear captured probe history
python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py clear-probes
```

---

## 🔑 Seamless (Passwordless) Authorization (Optional)

By default, engaging or disengaging the firewall and hostname requires standard administrator confirmation via Omarchy's native Polkit popup.

If you would like the button to toggle instantly without a password prompt, you can add a Polkit rule:

```bash
sudo tee /etc/polkit-1/rules.d/50-lan-lockdown.rules <<'EOF'
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.policykit.exec" &&
        action.lookup("program").indexOf("jeffe747.lan-lockdown/backend.py") !== -1 &&
        subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
EOF
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
