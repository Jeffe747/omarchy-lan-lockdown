# omarchy-lan-lockdown

🛡️ **One-click stealth and network lockdown for Omarchy Linux at LAN parties and hostile networks.**

Play games freely while completely locking down your machine against automated port scanners, network fuzzers, and autonomous reconnaissance agents.

---

## ⚡ What it Does

When you're at a LAN party or on an untrusted Wi-Fi network, attackers and automated AI agents sweep the local subnet for open services, vulnerable ports, mDNS broadcasts, and device fingerprints.

**LAN Lockdown** gives you a one-click toggle directly in your Omarchy status bar:

| Feature | Normal Mode | 🛡️ LAN Lockdown Mode |
| :--- | :--- | :--- |
| **Inbound Firewall (UFW)** | Standard rules (LocalSend, etc. allowed) | **Strictly drops all unsolicited inbound traffic** |
| **mDNS / Bonjour Broadcast** | `avahi-daemon` active (`hostname.local`) | **Silenced & stopped** (zero network broadcasts) |
| **Hostname Profile** | Your personal machine name | **Masked as `guest-pc`** (restores original on disable) |
| **Local File Shares** | LocalSend / file sharing apps active | **Closed & stopped** |
| **Bluetooth** | Discoverable/Powered | **Powered off** |
| **Tailscale** | Connected | **Disconnected** (`tailscale down`) |
| **Gaming (Steam, Proton, Online)** | Working | **100% Working** |

> [!NOTE]
> **Why doesn't this break online gaming?**  
> Modern games, Steam, matchmaking, Discord, and anti-cheat only require **outbound** network connections. Linux uses a stateful firewall (`conntrack`), so when your game connects out to a game lobby or matchmaking server, return packets are automatically permitted back in.

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
- **`󰒃` (Active Shield):** LAN Lockdown is engaged.

Clicking opens the quick card where you can see the status of each protection layer and toggle Lockdown with one click.

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
You can also inspect or toggle lockdown directly from your terminal:

```bash
# Query JSON status
python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py status

# Toggle lockdown (prompts for Polkit authorization if needed)
python3 ~/.config/omarchy/plugins/jeffe747.lan-lockdown/backend.py toggle
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
