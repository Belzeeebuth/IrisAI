# Commandes vocales reconnues

Toutes les phrases sont normalisées avant analyse : minuscules, accents ignorés, nombres en lettres convertis (« cinquante » → 50), « pour cent » → %, « github point com » → github.com, formules de politesse retirées (« peux-tu … s'il te plaît »). Le mot d'activation peut être en tête (« Hey Iris, … ») ou en queue (« …, Iris »).

Les intentions marquées **⚠ confirmation** demandent « Veux-tu vraiment … ? » — réponds « oui / vas-y / ok » ou « non / annule ».

Plusieurs commandes dans une phrase : « ouvre le terminal **et** va sur le workspace 2 », « monte le son **puis** ferme firefox », « ouvre firefox **et** spotify ». Si une commande demande confirmation, la suite attend ta réponse.

| Intention | Français | English |
|---|---|---|
| `open_app` | ouvre / lance / démarre **le terminal**, mon navigateur, l'éditeur, les fichiers, la musique, la calculatrice, le moniteur système, le lanceur, les raccourcis, Discord, Slack, Signal, Telegram, WhatsApp, Obsidian, Steam, VLC, GIMP, LibreOffice, Thunderbird, YouTube, GitHub, ChatGPT, Claude, Figma, Notion, Zoom, lazygit, neovim… ou n'importe quelle application `.desktop` | open / launch / start firefox, the browser, my editor… |
| `close_app` | ferme / quitte **firefox** | close / quit / kill the browser |
| `close_all` ⚠ | ferme tout · ferme toutes les applications | close all (windows) |
| `window_close` | ferme cette fenêtre · ferme la fenêtre active | close this window |
| `window_fullscreen` | plein écran | fullscreen |
| `window_floating` | (fenêtre) flottante | floating |
| `window_move_workspace` | envoie / déplace cette fenêtre sur le workspace **3** | move this window to workspace 3 |
| `workspace_switch` | va sur le workspace **3** · bureau 2 · workspace trois | go to workspace 3 · desktop 2 |
| `workspace_next` / `workspace_prev` | workspace suivant / précédent · bureau suivant | next / previous workspace |
| `volume_set` | mets le volume à **50** · volume 30 · volume à cinquante pour cent | set volume to 50 · volume 30 |
| `volume_up` | monte le son · augmente le volume (de 10) · plus fort | turn up the volume · louder |
| `volume_down` | baisse le son (de 20) · moins fort | turn down the volume · quieter |
| `volume_mute` / `volume_unmute` | coupe le son · éteins le son · mute / remets le son · unmute | mute / unmute |
| `brightness_set` | luminosité à **40** · mets la luminosité à 70 | brightness 40 · set brightness to 70 |
| `brightness_up` / `brightness_down` | monte / baisse la luminosité (de 15) · écran plus lumineux | brighter / dimmer · turn up the brightness |
| `media_play_pause` | pause · lecture · mets la musique · reprends la musique · play | play · pause · resume |
| `media_next` / `media_prev` | musique / piste / chanson suivante · précédente · suivant · next | next track · previous song · skip |
| `theme_next` | change de thème · thème suivant | next theme · switch theme |
| `theme_set` | mets le thème **tokyo night** · applique le thème catppuccin | set theme tokyo night |
| `night_light` | mode nuit · lumière de nuit | night light · night mode |
| `screenshot` | prends une capture d'écran · capture | take a screenshot |
| `lock_screen` | verrouille l'écran · verrouille · lock | lock the screen · lock |
| `suspend` ⚠ | mets en veille · mets le pc en veille · veille | suspend · put the computer to sleep |
| `shutdown` ⚠ | éteins l'ordinateur · éteins le pc | shut down the computer · power off the pc |
| `reboot` ⚠ | redémarre le pc · redémarre | reboot · restart the computer |
| `time` / `date` | quelle heure est-il · dis-moi l'heure / quel jour sommes-nous · la date | what time is it / what's the date |
| `say` | dis **bonjour à tout le monde** · répète … | say hello · repeat … |
| `open_url` | ouvre **github.com** · va sur lemonde.fr · ouvre github point com | open github.com · go to example.org |
| `web_search` | cherche **des recettes de crêpes** (sur internet) · recherche … · google … | search for cats · look up … |
| `greet` / `thanks` | bonjour · salut · coucou / merci | hello · hi / thanks |
| `who_are_you` / `help` | qui es-tu · présente-toi / qu'est-ce que tu sais faire · aide | who are you / what can you do · help |
| `stop` | stop · arrête · annule · laisse tomber · tais-toi | stop · cancel · never mind |
| `pause_listening` | mets-toi en pause (pendant **10** minutes) · ne m'écoute plus | stop listening · go to sleep (for 10 minutes) |
| `resume_listening` | reprends l'écoute · réveille-toi · reprends | resume listening · wake up |
| `type_text` | écris : **bonjour à tous** · tape … · note … | write … · type … |
| `dictation_start` / `dictation_stop` | mode dictée · dictée / fin de dictée · arrête la dictée | start dictation / stop dictation |
| `monitor_move` | envoie cette fenêtre sur l'écran de **droite** / gauche / haut / bas | move this window to the right monitor |
| `monitor_focus` | va sur l'écran de gauche · écran de droite | focus the left monitor |
| `bluetooth_on` / `bluetooth_off` | active / désactive le bluetooth | bluetooth on / off |
| `bluetooth_connect` / `bluetooth_disconnect` | connecte **mes écouteurs** (alias `[bluetooth]` ou nom de l'appareil) / déconnecte le casque | connect my headphones / disconnect … |
| `wifi_on` / `wifi_off` | active le wifi / coupe le wi-fi | wifi on / turn off the wifi |
| `airplane_on` / `airplane_off` | mode avion / désactive le mode avion | airplane mode on / off |
| `battery` | niveau de batterie · batterie | battery level |
| `audio_output_switch` | change de sortie audio · sortie audio suivante | switch audio output |
| `notifications_read` | lis mes notifications · mes notifications | read my notifications |
| `notifications_dismiss` | efface les notifications | clear notifications |
| `dnd_on` / `dnd_off` | ne pas déranger · active ne pas déranger / désactive ne pas déranger | do not disturb / turn off do not disturb |
| `session_open` | ouvre ma session **vidéo** · *phrases déclarées dans [[sessions]]* | open my video session |
| `session_save` | sauvegarde la session sous **montage** | save the session as … |
| `ask_llm` | pourquoi … · comment … · explique-moi … · c'est quoi … · question : … · *toute phrase inconnue si `llm.fallback_nlu`* | why … · how … · explain … · what is … |
| `ask_agent` | demande à **Claude** / **OpenCode** / **Codex** / **Gemini** de … (dans le projet X) · lance un agent pour … | ask Claude to … · run an agent to … |
| `task_run` | lance la compilation (*phrase déclarée dans [[tasks]]*) · lance la tâche **build** | run task build |
| `task_watch` | surveille **la compilation** (tâche déclarée ou processus existant) | watch the build · keep an eye on cargo |
| `task_status` | où en est la compilation ? · mes tâches · état des tâches | how is the build? · tasks |
| `task_cancel` | annule la compilation · stoppe le téléchargement | cancel the build |
| `task_result` | lis le résultat (de la compilation) · qu'a répondu Claude ? | read the result · what did Claude say? |
| `open_project` | ouvre le projet **cnvs-clone** | open the project iris |
| `type_and_enter` | envoie : **lance les tests** · dis au terminal npm test | send: npm test · tell the terminal … |
| `dictation_start_enter` | mode terminal · mode prompt | terminal mode |
| `remember` / `forget` / `forget_all` / `recall` | retiens que **mon éditeur est Zed** · souviens-toi que … / oublie mon éditeur / oublie tout / qu'est-ce que tu sais de moi ? | remember that … / forget … / forget everything / what do you know about me? |
| `session_resume` | reprends ma session d'hier · reprends ma dernière session | resume my last session |
| `automation_create` | **chaque matin à 9 h** lance spotify · en semaine à 8 h 30 lance mon workspace de dev · tous les vendredis à 17 h mets le thème tokyo night · chaque soir à 22 h active ne pas déranger (*période + heure + n'importe quelle commande sans confirmation*, voir [AUTOMATIONS.md](AUTOMATIONS.md)) | every weekday at 8:30 open the browser · every day at 9 open spotify |
| `reminder_create` | rappelle-moi de **sortir les poubelles** à 20 h · dans 25 minutes rappelle-moi la réunion · demain à 9 h rappelle-moi d'appeler Alice · rappelle-moi dans 2 heures de boire de l'eau | remind me to call Bob at 3 pm · in 20 minutes remind me … · remind me tomorrow at 9 to … |
| `automation_list` | quelles sont mes automatisations · mes rappels · liste mes programmations | what are my automations · list my reminders |
| `automation_delete` | supprime l'automatisation **de 9 h** · supprime le rappel des poubelles · annule la routine spotify (*nom, heure ou numéro*) | delete the automation at 9 · remove the reminder … |
| `alias_learn` | quand je dis **mes mails**, ouvre **thunderbird** · quand je dis mon site, c'est le navigateur · … ça veut dire … | when I say my mails, open thunderbird |
| `alias_list` | quels sont mes alias · mes alias | what are my aliases |
| `habits_show` | quelles sont mes habitudes · mes habitudes | what are my habits |
| `suggestions_off` / `suggestions_on` | arrête de me proposer des suggestions · plus de suggestions / propose-moi à nouveau des suggestions · reprends les suggestions | stop suggesting · no more suggestions / suggest again |
| `style_tone` | sois plus **directe** · sois cash · sois chaleureuse · sois motivante · sois taquine · sois drôle · sois professionnelle · sois sérieuse · sois zen · sois calme | be direct · be friendly · be energetic · be playful · be formal · be calm |
| `style_verbosity` | sois plus concise · réponses plus courtes · moins de blabla / sois plus bavarde · parle plus · développe / réponses normales | be brief · shorter answers / talk more · be chatty / normal answers |
| `language_switch` | parle en anglais · réponds en français | speak french · answer in english |
| `voice_speed` | parle plus vite · parle plus lentement · vitesse normale · parle normalement | speak faster · slower · normal speed |
| `voice_change` | change de voix · prends une autre voix · utilise la voix de **Léa** · mets la voix Sarah | change your voice · next voice · use the Nova voice |
| `wake_add` | appelle-toi **Nova** · réponds aussi à Jarvis · tu t'appelles Nova | call yourself Nova · also answer to Jarvis |
| `custom` | vos phrases (`[[commands]]`), correspondance floue ≥ 85 % | idem |

## Réponses d'Iris

Selon `assistant.verbosity` et `assistant.tone` :

| Situation | concise | normal (warm) | chatty |
|---|---|---|---|
| Activation | Oui ? | Oui ? / Je t'écoute. | Oui, dis-moi. |
| Non compris | Pas compris. | Je n'ai pas compris. | Hmm, je n'ai pas compris. Tu peux reformuler ? |
| Application lancée | ghostty. | ghostty est lancé. | C'est parti, ghostty est lancé. Autre chose ? |
| Workspace | Workspace 3. | Workspace 3. | Te voilà sur le workspace 3. Autre chose ? |

Ton `direct` : « Oui. », « De rien. » ; ton `coach` : « Je suis là. On fait quoi ? », « Prêt à attaquer la journée ? » ; ton `playful` : « Oui, mon capitaine ? », « Je suis toute ouïe. » ; ton `pro` : « Je vous écoute. » ; ton `zen` : « Oui… ». Le ton et la verbosité se changent à la voix (« sois plus directe », « sois plus concise ») et sont mémorisés ; `[phrases]` dans la config remplace n'importe quelle réplique. Détails : [PERSONALIZATION.md](PERSONALIZATION.md).
