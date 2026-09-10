# Widget Quickshell

`Iris.qml` affiche l'état d'Iris (veille, écoute, réflexion, parole, confirmation, dictée, pause) dans une barre [Quickshell](https://quickshell.org), avec push-to-talk au clic.

1. Copie `Iris.qml` dans ton dossier Quickshell (`~/.config/quickshell/`).
2. Dans ta barre (`shell.qml` ou le composant de ta barre), ajoute `Iris { }` là où tu veux l'icône.
3. Rien à configurer côté Iris : le widget lit `$XDG_RUNTIME_DIR/iris/state.json`, écrit par `iris run` à chaque changement d'état (`waybar_signal` n'est utile que pour Waybar).

Le widget utilise la police *Symbols Nerd Font* (installée par Omarchy) pour les icônes ; change `font.family` sinon. Les couleurs sont celles de Catppuccin Mocha, adapte-les à ton thème.

Équivalent Waybar : [`../waybar/`](../waybar/).
