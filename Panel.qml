import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "jeffe747.lan-lockdown"

  property bool lockedDown: false
  property string currentHostname: ""
  property string origHostname: ""
  property bool avahiActive: true
  property bool bluetoothPowered: true
  property bool tailscaleActive: true
  property bool honeypotRunning: false
  property var probes: []
  property int probeCount: 0
  property bool busy: false
  property string errorText: ""

  readonly property string helper: Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, "")

  implicitWidth: icon.implicitWidth
  implicitHeight: icon.implicitHeight

  function refresh() {
    if (busy || statusProcess.running) return
    statusProcess.running = true
  }

  function toggleLockdown() {
    if (busy) return
    busy = true
    errorText = ""
    actionProcess.running = true
  }

  onOpenedChanged: if (opened) refresh()

  Timer {
    interval: 3000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  Process {
    id: statusProcess
    command: ["python3", root.helper, "status"]
    stdout: StdioCollector {
      id: statusOutput
      waitForEnd: true
    }
    onExited: function(code) {
      if (code !== 0) return
      try {
        var data = JSON.parse(statusOutput.text)
        if (data.ok) {
          root.lockedDown = (data.locked === true)
          root.currentHostname = data.hostname || ""
          root.origHostname = data.originalHostname || ""
          root.avahiActive = (data.avahiActive === true)
          root.bluetoothPowered = (data.bluetoothPowered === true)
          root.tailscaleActive = (data.tailscaleActive === true)
          root.honeypotRunning = (data.honeypotRunning === true)
          root.probes = data.probes || []
          root.probeCount = (data.probes || []).length
        }
      } catch (err) {}
    }
  }

  Process {
    id: actionProcess
    command: ["python3", root.helper, "toggle"]
    stdout: StdioCollector {
      id: actionOutput
      waitForEnd: true
    }
    onExited: function(code) {
      root.busy = false
      try {
        var data = JSON.parse(actionOutput.text)
        if (!data.ok) {
          root.errorText = data.error || "Lockdown operation failed"
        } else {
          root.errorText = ""
        }
      } catch (err) {
        if (code !== 0) root.errorText = "Authentication or command cancelled"
      }
      root.refresh()
    }
  }

  BarIconButton {
    id: icon
    anchors.fill: parent
    bar: root.bar
    text: root.lockedDown ? "󰒃" : "󰀝"
    active: root.lockedDown
    useActiveColor: true
    activeColor: root.probeCount > 0 ? Color.urgent : (root.bar ? root.bar.urgent : Color.urgent)
    foreground: root.bar ? root.bar.barForeground : Color.foreground
    tooltipText: root.lockedDown
      ? (root.probeCount > 0 ? ("LAN Lockdown: " + root.probeCount + " probes captured!") : "LAN Lockdown: Active (Stealth & Honeypot)")
      : "LAN Lockdown: Inactive"
    onPressed: root.toggle()
  }

  KeyboardPanel {
    anchorItem: icon
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: fittedContentWidth(Style.space(340))
    contentHeight: fittedContentHeight(cardContent.implicitHeight)

    Column {
      id: cardContent
      width: parent.width
      spacing: Style.space(10)

      // Header row
      Row {
        width: parent.width
        spacing: Style.space(8)

        Text {
          text: "LAN Lockdown"
          color: root.barForeground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
          anchors.verticalCenter: parent.verticalCenter
        }

        Rectangle {
          height: Style.space(20)
          width: statusBadgeText.implicitWidth + Style.space(12)
          radius: Style.cornerRadius
          color: root.lockedDown ? (root.probeCount > 0 ? Color.urgent : Color.urgent) : Color.muted
          opacity: 0.9
          anchors.verticalCenter: parent.verticalCenter

          Text {
            id: statusBadgeText
            anchors.centerIn: parent
            text: root.lockedDown ? (root.probeCount > 0 ? (root.probeCount + " PROBES CAUGHT") : "STEALTH + HONEYPOT") : "NORMAL"
            color: Color.background
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }
      }

      // Description text
      Text {
        width: parent.width
        wrapMode: Text.WordWrap
        text: root.lockedDown
          ? "Hostile network stealth active. Inbound traffic blocked, mDNS silent, hostname masked. Fake Ollama decoy trap active on port 11434."
          : "Standard network operation. Local discovery and inbound peer services are enabled."
        color: root.barForeground
        opacity: 0.7
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      // Protection checklist
      Column {
        width: parent.width
        spacing: Style.space(4)

        Row {
          spacing: Style.space(6)
          Text {
            text: root.lockedDown ? "✓" : "·"
            color: root.lockedDown ? Color.urgent : Color.muted
            font.bold: true
          }
          Text {
            text: root.lockedDown ? "Inbound Firewall: Blocked (UFW drop)" : "Inbound Firewall: Default"
            color: root.barForeground
            font.pixelSize: Style.font.caption
          }
        }

        Row {
          spacing: Style.space(6)
          Text {
            text: !root.avahiActive ? "✓" : "·"
            color: !root.avahiActive ? Color.urgent : Color.muted
            font.bold: true
          }
          Text {
            text: !root.avahiActive ? "mDNS Broadcast (Avahi): Silent" : "mDNS Broadcast: Active"
            color: root.barForeground
            font.pixelSize: Style.font.caption
          }
        }

        Row {
          spacing: Style.space(6)
          Text {
            text: root.currentHostname === "guest-pc" ? "✓" : "·"
            color: root.currentHostname === "guest-pc" ? Color.urgent : Color.muted
            font.bold: true
          }
          Text {
            text: root.currentHostname === "guest-pc" ? "Hostname: Masked (guest-pc)" : ("Hostname: " + root.currentHostname)
            color: root.barForeground
            font.pixelSize: Style.font.caption
          }
        }

        Row {
          spacing: Style.space(6)
          Text {
            text: root.honeypotRunning ? "✓" : "·"
            color: root.honeypotRunning ? Color.urgent : Color.muted
            font.bold: true
          }
          Text {
            text: root.honeypotRunning ? "Decoy Honeypot: Active (Port 11434 Ollama)" : "Decoy Honeypot: Inactive"
            color: root.barForeground
            font.pixelSize: Style.font.caption
          }
        }
      }

      // Honeypot Probes Section
      Column {
        visible: root.lockedDown
        width: parent.width
        spacing: Style.space(6)

        Rectangle {
          width: parent.width
          height: 1
          color: root.barForeground
          opacity: 0.15
        }

        Row {
          width: parent.width
          spacing: Style.space(6)
          Text {
            text: "Captured Probes (" + root.probeCount + ")"
            color: root.barForeground
            font.family: root.bar ? root.bar.fontFamily : Style.font.family
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }

        Text {
          visible: root.probeCount === 0
          width: parent.width
          text: "Listening for scanning agents… No probes captured yet."
          color: root.barForeground
          opacity: 0.5
          font.pixelSize: Style.font.caption
        }

        Repeater {
          model: Math.min(root.probes.length, 3)
          delegate: Rectangle {
            width: parent.width
            height: probeInfoCol.implicitHeight + Style.space(8)
            radius: Style.cornerRadius
            color: Color.background
            opacity: 0.95
            border.width: 1
            border.color: Color.urgent

            Column {
              id: probeInfoCol
              anchors.fill: parent
              anchors.margins: Style.space(4)
              spacing: Style.space(2)

              Row {
                width: parent.width
                spacing: Style.space(4)
                Text {
                  text: modelData.time_str || ""
                  color: Color.muted
                  font.pixelSize: Style.font.caption
                }
                Text {
                  text: (modelData.ip || "") + " (" + (modelData.mac || "") + ")"
                  color: Color.urgent
                  font.bold: true
                  font.pixelSize: Style.font.caption
                }
              }

              Text {
                width: parent.width
                elide: Text.ElideRight
                text: (modelData.method || "GET") + " " + (modelData.path || "") + " · " + (modelData.user_agent || "")
                color: root.barForeground
                font.pixelSize: Style.font.caption
              }
            }
          }
        }
      }

      // Error banner
      Text {
        visible: root.errorText !== ""
        width: parent.width
        wrapMode: Text.WordWrap
        text: root.errorText
        color: root.bar ? root.bar.urgent : Color.urgent
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.bodySmall
      }

      // Main Toggle Action Button
      Rectangle {
        width: parent.width
        height: Style.space(36)
        radius: Style.cornerRadius
        color: root.lockedDown ? (root.bar ? root.bar.foreground : Color.foreground) : (root.bar ? root.bar.urgent : Color.urgent)
        opacity: root.busy ? 0.6 : 1.0

        Text {
          anchors.centerIn: parent
          text: root.busy ? "Switching..." : (root.lockedDown ? "Restore Normal Settings" : "Engage LAN Lockdown")
          color: root.lockedDown ? Color.background : Color.foreground
          font.family: root.bar ? root.bar.fontFamily : Style.font.family
          font.pixelSize: Style.font.body
          font.bold: true
        }

        MouseArea {
          anchors.fill: parent
          enabled: !root.busy
          cursorShape: Qt.PointingHandCursor
          onClicked: root.toggleLockdown()
        }
      }
    }
  }
}
