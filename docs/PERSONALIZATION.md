# Personnalisation et apprentissage

Depuis la phase 4, Iris s'adapte à toi de deux façons : tu lui dis comment tu la veux (**à la voix**, sans éditer la configuration), et elle **observe tes habitudes** dans son journal pour te proposer des raccourcis — en demandant toujours ton accord.

Tout ce qui est appris est stocké dans le journal SQLite (table `prefs`, clés `pref.*`) et réappliqué au démarrage, **par-dessus** `config.toml`. `iris prefs` liste ce qu'Iris a retenu, `iris prefs reset` l'oublie.

## Style de réponse

| Tu dis | Effet | Réponse |
|---|---|---|
| « sois plus directe » · « sois cash » · « be direct » | ton `direct` | D'accord, je serai plus directe. |
| « sois chaleureuse » · « sois douce » · « be friendly » | ton `warm` (défaut) | |
| « sois motivante » · « sois coach » · « be energetic » | ton `coach` | |
| « sois taquine » · « sois drôle » · « be playful » | ton `playful` : « Oui, mon capitaine ? », « Je suis toute ouïe. » | |
| « sois professionnelle » · « sois sérieuse » · « be formal » | ton `pro` : vouvoiement, sobriété | |
| « sois zen » · « sois calme » · « be calm » | ton `zen` : réponses posées | |
| « sois plus concise » · « réponses plus courtes » · « moins de blabla » · « be brief » | verbosité `concise` | Compris. |
| « sois plus bavarde » · « parle plus » · « développe » · « talk more » | verbosité `chatty` (ajoute « Autre chose ? ») | |
| « réponses normales » · « normal answers » | verbosité `normal` | |
| « parle en anglais » · « réponds en français » · « speak french » | langue des réponses **et** de la transcription (`fr` / `en`) | Okay, I'll answer in English. |

Le ton s'applique à toutes les réponses « règles » (`phrasebook.py` a des variantes par ton pour l'activation, les salutations, les remerciements…), au LLM (il reçoit le ton et la personnalité) et à la **voix** quand le moteur est pilotable par instructions (OpenAI `gpt-4o-mini-tts` : style dérivé du ton, plus `assistant.personality`).

### Profil de personnalité

`assistant.personality = "Tutoie-moi, sois directe et un peu taquine."` est un texte libre. Il est transmis au cerveau LLM (phrases hors règles, questions, conversation) et aux instructions de la voix OpenAI. Pour les réponses à règles, choisis un **ton** (ci-dessus) : c'est lui qui décide des formulations.

### Phrases personnalisées

Tu peux remplacer n'importe quelle réplique d'Iris dans `config.toml` :

```toml
[phrases]
ack = ["Oui chef ?", "Je t'écoute."]        # liste = tirage au sort
greet = "Salut toi ! On fait quoi ?"
not_understood = "Pardon ?"
done = "Fait."
```

Les clés sont celles de `iris/core/phrasebook.py` (`ack`, `greet`, `thanks_reply`, `done`, `not_understood`, `cancelled`, `confirm_timeout`, `follow_up`, `remembered`, `app_opened`, `automation_created`…). Une clé surchargée ignore le ton et la verbosité ; `{app}`, `{n}`, `{desc}`… restent disponibles dans le texte.

### Heures calmes

`assistant.quiet_hours = "22:00-07:00"` : pendant cette plage, Iris répond en mode `concise` (quelle que soit la verbosité choisie) et **ne fait aucune suggestion** proactive. Les automatisations et rappels continuent de s'exécuter. La plage peut traverser minuit.

## Voix

| Tu dis | Effet |
|---|---|
| « parle plus vite » · « parle plus lentement » · « speak faster » · « slower » | débit × 1,12 (ou ÷ 1,12) à chaque demande, entre 0,6 et 1,6 ; appliqué à tous les moteurs (ElevenLabs borne à 0,7 – 1,2 ; Piper via `length_scale`) et **mémorisé** |
| « vitesse normale » · « parle normalement » | débit 1,0 |
| « change de voix » · « prends une autre voix » | ElevenLabs : voix suivante parmi celles de ton compte ; OpenAI : voix suivante (alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar) ; Kokoro : voix suivante |
| « utilise la voix de Léa » · « prends la voix Sarah » · « use the Nova voice » | voix par nom (ElevenLabs : une voix **de ton compte**, `iris voices list --engine elevenlabs` ; ajoute-la d'abord avec `iris voices add` si elle vient de la bibliothèque) |

La voix choisie est mémorisée par moteur (`voice.name`), donc rebasculer d'ElevenLabs à OpenAI retrouve la voix choisie pour chacun.

## Nom d'activation

« **appelle-toi Nova** », « **réponds aussi à Jarvis** », « call yourself Nova » : ajoute « nova » et « hey nova » aux phrases d'activation, immédiatement (le détecteur est rechargé) et pour les prochains démarrages. Le nom doit rester simple (2 à 30 lettres) : Whisper doit pouvoir le transcrire. Les phrases de `[wake]` restent actives ; `iris prefs reset` retire les noms appris.

## Alias appris

```
toi   : Iris, quand je dis mes mails, ouvre Thunderbird
iris  : D'accord : quand tu dis « mes mails », j'ouvre thunderbird.
toi   : Iris, ouvre mes mails
iris  : thunderbird est lancé.
toi   : Iris, quels sont mes alias
iris  : Tes alias : mes mails → thunderbird.
```

Formes : « quand je dis X, c'est Y », « … ça veut dire Y », « … ouvre / lance Y », « when I say X, open Y ». La cible est n'importe quoi qu'« ouvre … » accepte : nom d'application, alias embarqué (« le navigateur », « mon éditeur »), web-app (« youtube »), commande. Iris la résout au moment de l'apprentissage et mémorise la commande réelle (`chromium`, `webapp:https://youtube.com`…), comme une entrée `[apps]` ; un alias appris l'emporte sur une entrée `[apps]` qui aurait la même phrase.

## Habitudes et suggestions

Iris relit son **journal des actions** (les 14 derniers jours par défaut, `habits.window_days`) et cherche deux choses. Seules les actions **réussies** et **automatisables** comptent (applications, URL, projets, workspaces, sessions, commandes perso, tâches, thèmes, volume, luminosité, musique, Bluetooth, ne pas déranger, mode nuit, verrouillage, notifications) — jamais les actions à confirmation.

### Routines horaires

Une même action, à la même demi-heure, sur au moins **3 jours distincts** (`habits.min_occurrences`) devient une routine. Dans un moment calme (Iris en veille, au plus une fois toutes les 10 minutes), si l'heure de la routine est proche (± 30 min) et qu'aucune automatisation ne la couvre déjà :

```
iris  : Tu fais souvent ouvrir spotify vers 9 h. Veux-tu que je m'en occupe chaque jour à 9 h ?
toi   : oui
iris  : Programmé : chaque jour à 9 h : ouvrir spotify.
```

Si la routine n'a été observée qu'en semaine, la proposition est « en semaine à 9 h ». « non » : la suggestion est **définitivement** abandonnée (« D'accord, je ne te le proposerai plus »). Pas de réponse en 24 s : elle reviendra après le délai de `habits.cooldown_hours` (24 h). Une seule proposition de routine par période de cooldown, pour ne jamais devenir envahissante.

### Enchaînements

Quand une action est suivie d'une autre dans les deux minutes, au moins 3 fois et dans **au moins la moitié des cas**, Iris propose la seconde juste après la première :

```
toi   : Iris, ouvre mon workspace de dev
iris  : Workspace de dev lancé. Veux-tu aussi activer ne pas déranger ?
toi   : oui
iris  : Ne pas déranger activé.
```

« non » abandonne cette suggestion pour de bon ; sans réponse (12 s), elle reviendra après le cooldown. Une action à confirmation (éteindre, fermer tout…) n'est jamais proposée automatiquement.

### Voir et contrôler

| Tu dis | Effet |
|---|---|
| « quelles sont mes habitudes » | « Ce que j'ai remarqué : ouvrir spotify vers 9 h (5 fois); après lancer workspace-dev, souvent activer ne pas déranger. » |
| « arrête de me proposer des suggestions » · « plus de suggestions » · « no more suggestions » | plus aucune suggestion (routines et enchaînements), mémorisé |
| « propose-moi à nouveau des suggestions » · « reprends les suggestions » | réactive |

```bash
iris habits            # routines détectées (heure, jours, occurrences) et enchaînements (ratio)
iris prefs             # tout ce qu'Iris a appris (ton, vitesse, voix, noms, alias, suggestions refusées)
iris prefs reset       # oublie tout (les automatisations restent : iris automations)
```

Configuration (`[habits]`) : `enabled`, `suggest_follow_ups`, `suggest_routines`, `window_days`, `min_occurrences`, `cooldown_hours`. Les suggestions exigent `privacy.journal_actions = true` (par défaut) : sans journal, pas d'habitudes.

## Ce qui n'est pas appris (volontairement)

- Iris ne crée **jamais** une automatisation sans ton « oui » explicite.
- Rien de ce qu'elle apprend ne quitte la machine : les habitudes sont calculées localement, les préférences vivent dans `~/.local/state/iris/iris.db`. Le LLM ne reçoit ni les routines ni les préférences apprises — seulement le ton, la personnalité, les faits que tu as explicitement demandé de retenir (« retiens que … ») et, si `llm.context = true`, les trois dernières actions.
- Une suggestion refusée n'est pas reposée. Une préférence dite à la voix l'emporte sur `config.toml` jusqu'à `iris prefs reset` (ou jusqu'à ce que tu en dises une autre).
