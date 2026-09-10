// Widget Quickshell pour Iris — état de l'assistante dans ta barre.
//
// Lit le même fichier JSON que le module Waybar ($XDG_RUNTIME_DIR/iris/state.json,
// écrit par `iris run` à chaque changement d'état) et le surveille : aucune commande
// lancée en boucle, rafraîchissement instantané.
//
// Installation : copie ce fichier dans ~/.config/quickshell/ (ou le dossier de ta config
// Quickshell) puis, dans ta barre :
//
//     Iris { }                       // taille par défaut
//     Iris { pointSize: 14 }         // plus grand
//
// Clic gauche : push-to-talk (`iris trigger`, équivaut à « Hey Iris »).
// Clic droit  : pause / reprise (`iris trigger --pause`).
// Voir ../waybar/ pour l'équivalent Waybar.

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io

Item {
    id: root

    property int pointSize: 12
    property string state: "off"
    property string detail: ""
    property string tooltip: "Iris : arrêtée"

    // Icônes Nerd Font (les mêmes que le module Waybar) et couleurs par état.
    readonly property var icons: ({
        "idle": "󰍬", "active": "󰍬", "confirming": "󰋗", "paused": "󰍭",
        "dictating": "󰏫", "speaking": "󰔊", "thinking": "󰔟", "off": "󰍭"
    })
    readonly property var colors: ({
        "idle": "#a6adc8", "active": "#89b4fa", "confirming": "#f9e2af", "paused": "#6c7086",
        "dictating": "#94e2d5", "speaking": "#cba6f7", "thinking": "#fab387", "off": "#585b70"
    })

    implicitWidth: label.implicitWidth + 12
    implicitHeight: label.implicitHeight + 4

    FileView {
        id: stateFile
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/iris/state.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.parse(text())
        onLoadFailed: { root.state = "off"; root.detail = ""; root.tooltip = "Iris : arrêtée" }
    }

    // Filet de sécurité si l'inotify ne remonte pas (fichier remplacé atomiquement).
    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: stateFile.reload()
    }

    function parse(raw) {
        try {
            const data = JSON.parse(raw);
            root.state = data.alt || data.class || "off";
            root.tooltip = data.tooltip || ("Iris : " + root.state);
            const lines = root.tooltip.split("\n");
            root.detail = lines.length > 1 ? lines.slice(1).join(" · ") : "";
        } catch (e) {
            root.state = "off";
            root.tooltip = "Iris : arrêtée";
        }
    }

    Process { id: trigger; command: ["iris", "trigger"] }
    Process { id: pause;   command: ["iris", "trigger", "--pause"] }

    Text {
        id: label
        anchors.centerIn: parent
        text: root.icons[root.state] || root.icons.off
        color: root.colors[root.state] || root.colors.off
        font.pointSize: root.pointSize
        font.family: "Symbols Nerd Font"

        // Pulsation discrète quand Iris écoute ou réfléchit.
        SequentialAnimation on opacity {
            running: root.state === "active" || root.state === "thinking"
            loops: Animation.Infinite
            NumberAnimation { to: 0.35; duration: 600 }
            NumberAnimation { to: 1.0; duration: 600 }
            onRunningChanged: if (!running) label.opacity = 1.0
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton) pause.running = true;
            else trigger.running = true;
        }
        ToolTip.visible: containsMouse
        ToolTip.text: root.tooltip
    }
}
