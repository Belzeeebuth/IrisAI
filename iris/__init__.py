"""Iris — assistant vocal natif pour Omarchy OS.

Le paquet est organisé en couches indépendantes :

- ``iris.audio``     capture micro, détection d'activité vocale (VAD), lecture audio ;
- ``iris.wakeword``  détection du mot d'activation (« Hey Iris ») ;
- ``iris.stt``       transcription parole → texte (faster-whisper en local) ;
- ``iris.nlu``       compréhension : texte → intention + paramètres ;
- ``iris.actions``   exécution : Hyprland, audio, luminosité, applications, Omarchy… ;
- ``iris.core``      orchestration : machine à états, routeur, journal, réponses ;
- ``iris.tts``       synthèse vocale (Piper en local, ElevenLabs en option).

Toutes les dépendances lourdes sont importées paresseusement : le cœur d'Iris
(NLU, routeur, journal, mode texte) fonctionne avec la bibliothèque standard + numpy.
"""

from __future__ import annotations

__version__ = "0.3.0"
__all__ = ["__version__"]
