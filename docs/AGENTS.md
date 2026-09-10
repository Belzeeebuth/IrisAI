# Tâches, agents, projets, mémoire (phase 3)

## Tâches en arrière-plan

Une tâche est une commande longue qu'Iris lance sans bloquer, puis dont elle **annonce la fin** à voix haute (succès, échec, durée) et par notification.

```toml
[[tasks]]
name = "compilation"
phrases = ["lance la compilation", "compile le projet"]
exec = "cargo build --release"
cwd = "~/projets/cnvs-clone"
announce = true
notify = true
```

| Tu dis | Iris |
|---|---|
| « lance la compilation » (phrase déclarée) · « lance la tâche compilation » | lance `exec`, puis « compilation terminé en 1 min 05. » ou « compilation a échoué après 12 secondes, code 101. » |
| « surveille la compilation » | lance la tâche si elle existe dans la config, sinon **surveille un processus** existant dont la ligne de commande contient « compilation » (`pgrep -f`) et prévient quand il se termine |
| « où en est la compilation ? » · « mes tâches » | état des tâches en cours (durée) et de la dernière terminée |
| « annule la compilation » | termine le processus (SIGTERM puis SIGKILL) |
| « lis le résultat » · « lis le résultat de la compilation » | lit la fin de la sortie (300 caractères), le texte complet part en notification |

Les annonces attendent un moment calme : jamais pendant une confirmation, une dictée ou une pause. Le journal (`iris tasks`) garde nom, commande, statut, code de retour, durée et fin de sortie. Les processus lancés survivent au redémarrage d'Iris (session séparée) ; seules les surveillances s'arrêtent.

## Agents IA

« Demande à Claude de corriger les tests dans le projet cnvs-clone » lance **Claude Code** en arrière-plan dans le dossier du projet, puis Iris résume la réponse à voix haute et l'envoie en notification. Même chose pour **OpenCode** (`opencode run`), **Codex** (`codex exec`) et **Gemini CLI** (`gemini -p`).

Chaque CLI s'authentifie avec sa propre connexion (`claude login` = ton abonnement claude.ai ; compte OpenCode ; …) : **Iris ne manipule aucune clé API** pour les agents.

```toml
[agents]
enabled = true
default = "claude"        # agent utilisé pour « lance un agent … »
timeout_s = 600
workdir = ""              # dossier par défaut ; « … dans le projet X » prend le dessus
# [agents.bins]
# claude = "/home/moi/.local/bin/claude"
```

| Tu dis | Iris |
|---|---|
| « demande à Claude d'écrire un README dans le projet iris » | `claude -p "écrire un README" --output-format text` dans `~/projets/iris`, puis « Claude a terminé : … » |
| « demande à OpenCode : refactore le module audio » | `opencode run "refactore le module audio"` |
| « lance un agent pour ranger le bureau » | agent par défaut |
| « qu'a répondu Claude ? » · « lis la réponse de l'agent » | relit le résumé |
| « où en est l'agent ? » · « annule Claude » | comme une tâche |

`iris agents` liste les CLI trouvés. Les agents restent des tâches : `iris tasks` en garde l'historique. Le prompt transmis est le texte reconnu, avec ses accents et majuscules d'origine.

## Projets

« Ouvre le projet cnvs-clone » ouvre l'éditeur (`omarchy-launch-editor`, `$VISUAL`, `code`, `zed`…) sur le dossier et un terminal dedans (`ghostty --working-directory`, `alacritty --working-directory`, `kitty --directory`, `foot`, sinon `sh -c "cd … && exec $TERMINAL"`).

Résolution : `[projects]` de la config (nom prononcé → chemin), puis les sous-dossiers de `system.project_dirs` (`~/projets`, `~/code`, `~/dev`, `~/src`, `~/work`, `~/Projects`…) par correspondance floue. `iris projects` liste les candidats, `iris projects <nom>` montre la résolution.

```toml
[projects]
"cnvs clone" = "~/projets/cnvs-clone"

[system]
project_dirs = ["~/projets", "~/code"]
```

## Voix vers le terminal (style BridgeVoice)

- « envoie : lance les tests » · « dis au terminal npm test » : tape le texte dans la fenêtre active **puis Entrée** (`wtype`).
- « mode terminal » (ou « mode prompt ») : dictée continue avec Entrée après chaque phrase, jusqu'à « fin de dictée ». Idéal pour parler à un agent qui tourne dans un terminal (Claude Code, OpenCode en mode interactif).
- « écris : … » et « mode dictée » restent sans Entrée.

## Mémoire persistante

| Tu dis | Iris |
|---|---|
| « retiens que mon éditeur est Zed » · « souviens-toi que je pars à 18 h » | enregistre le fait (clé « mon éditeur » → « Zed », ou texte libre) |
| « qu'est-ce que tu sais de moi ? » | liste les faits |
| « oublie mon éditeur » · « oublie tout » | supprime (correspondance floue) / efface |

Les faits sont injectés dans le prompt du LLM (« Ce que tu sais de l'utilisateur ») : le modèle en tient compte dans ses décisions et ses réponses. L'historique de conversation LLM est lui aussi persistant (`memory.history` dans SQLite, `llm.history_turns` tours transmis). `iris memory` (list / remember / forget / clear) pour la ligne de commande.

### Reprise de session

Toutes les `memory.snapshot_interval_min` minutes (10 par défaut) et à l'arrêt, Iris enregistre un instantané des fenêtres ouvertes par workspace (session « last »). Avec `assistant.resume_prompt = true`, au démarrage, si l'instantané a plus de `memory.resume_min_age_min` minutes et contient au moins deux applications, elle demande : « Veux-tu reprendre ta session précédente : ghostty, kdenlive ? ». « Oui » relance chaque application sur son workspace. À tout moment : « reprends ma session d'hier ».

## Outils du modèle

Quand une phrase sort des règles, le LLM peut demander **un** outil avant de décider (`llm.tools = true`) :

| Outil | Exemple | Limites |
|---|---|---|
| `calc` | « ça fait combien 15 % de 240 ? » → 36 | arithmétique pure (`ast`), jamais d'exécution de code |
| `clipboard` | « résume ce que j'ai copié » | `wl-paste`, 4 000 caractères |
| `read_file` | « lis mes notes du jour » | fichiers texte **du dossier personnel**, 20 000 caractères |
| `recall` | « rappelle-moi ce que j'aime » | faits mémorisés |
| `tasks` | « la compilation est passée ? » | état des tâches et agents |

Le résultat est renvoyé au modèle qui décide ensuite (action, réponse ou silence). Une action proposée passe toujours par les gestionnaires d'Iris et leurs confirmations.

## Réponses en streaming

`llm.stream = true` : les questions ouvertes (« explique-moi… ») sont lues phrase par phrase pendant que le modèle génère (SSE, `/chat/completions` et `/messages`). La première phrase part à la voix en une à deux secondes au lieu d'attendre la réponse complète.
