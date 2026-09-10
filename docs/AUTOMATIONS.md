# Automatisations et rappels

Depuis la phase 4, Iris exécute des actions **à heure fixe** sans que tu aies rien à écrire : tu le lui dis, elle le programme, elle s'en occupe. Tout est stocké dans son journal SQLite (`~/.local/state/iris/iris.db`, table `automations`) et vérifié par la boucle vocale elle-même : aucune unité systemd, aucun cron.

## Programmer une action

```
toi   : Iris, chaque matin à 9 h, lance Spotify
iris  : Programmé : chaque jour à 9 h : ouvrir spotify.
toi   : Iris, en semaine à 8 h 30 lance mon workspace de dev      ← commande [[commands]]
iris  : Programmé : en semaine à 8 h 30 : lancer workspace-dev.
toi   : Iris, tous les vendredis à 17 h mets le thème tokyo night
iris  : Programmé : chaque vendredi à 17 h : appliquer le thème tokyo night.
toi   : Iris, chaque soir à 22 h active ne pas déranger
iris  : Programmé : chaque jour à 22 h : activer ne pas déranger.
toi   : Iris, every weekday at 8:30 open the browser
iris  : Programmé : en semaine à 8 h 30 : ouvrir browser.
```

La phrase se compose d'une **période**, d'une **heure** et d'une **action** — dans l'ordre que tu veux (« lance Spotify chaque matin à 9 h » marche aussi). L'action est comprise par le même moteur de règles que les commandes ordinaires : tout ce que tu peux demander à Iris à la voix peut être programmé, y compris tes commandes `[[commands]]`, tes tâches `[[tasks]]`, tes sessions `[[sessions]]` et « ouvre le projet X ».

### Périodes reconnues

| Français | English | Résultat |
|---|---|---|
| chaque jour · tous les jours · chaque matin / midi / soir / nuit | every day · every morning / evening / night | quotidien (« matin » et « soir » ne changent pas l'heure : précise-la) |
| en semaine · chaque jour de (la) semaine · les jours ouvrés | on weekdays · every weekday | lundi → vendredi |
| le week-end · les week-ends · chaque week-end | on weekends · every weekend | samedi + dimanche |
| chaque lundi · tous les mardis · … | every monday · on fridays · … | un jour de la semaine |

### Heures reconnues

`à 9 h`, `à 9 heures`, `à 9 h 30`, `à 9:30`, `vers 18 h`, `à 8 pm`, `at 8:30`, `at 8 am`, `à 7 h du soir`, `à midi`, `à minuit`, `at noon`, `at midnight`. Sans heure, « chaque matin » et « chaque jour » sont programmés à 9 h, « chaque midi » à 12 h, « chaque soir » et « chaque nuit » à 20 h ; mieux vaut dire l'heure.

### Ce qu'Iris refuse de programmer

- **Les actions à confirmation** (éteindre, redémarrer, mettre en veille, fermer tout, commandes `confirm = true`) : « Je ne programme pas une action qui demande une confirmation. » Une automatisation ne doit jamais te demander « oui » à 23 h.
- Les questions au LLM, les agents (« demande à Claude … »), et les commandes de contrôle (stop, pause).
- Une phrase dont l'action n'est pas comprise : « Je n'ai pas compris quoi faire à ce moment-là. Redis-moi l'horaire et l'action. » (le planning est reconnu mais pas la commande).

## Rappels

```
toi   : Iris, rappelle-moi de sortir les poubelles à 20 h
iris  : Je te le rappellerai aujourd'hui à 20 h 00 : sortir les poubelles.
toi   : Iris, dans 25 minutes rappelle-moi la réunion
iris  : Je te le rappellerai aujourd'hui à 15 h 25 : la réunion.
toi   : Iris, demain à 9 h rappelle-moi d'appeler Alice
toi   : Iris, rappelle-moi dans 2 heures de boire de l'eau
toi   : Iris, remind me tomorrow at 9 to call Bob
```

Un rappel est une automatisation à exécution unique (`once`) : à l'heure dite, Iris dit **« Rappel : sortir les poubelles. »** et envoie une notification bureau *critique* (elle reste affichée jusqu'à ce que tu la fermes). Le rappel est ensuite supprimé. Si l'heure est déjà passée aujourd'hui (« à 8 h » dit à 10 h), c'est pour demain. Si Iris était éteinte au moment prévu, le rappel est dit dès qu'elle redémarre — un rappel raté n'est jamais perdu en silence.

Formes reconnues : `rappelle-moi de … à 20 h`, `à 20 h, rappelle-moi …`, `dans N minutes / heures`, `demain (à 9 h)`, `ce soir`, `ce matin`, `cet après-midi`, `aujourd'hui`, et leurs équivalents anglais (`remind me …`, `in N minutes`, `tomorrow`, `tonight`). Le texte du rappel garde tes accents et majuscules (« appeler Alice »).

## Lister, supprimer, tester

```
toi   : Iris, quelles sont mes automatisations
iris  : Tes automatisations : en semaine à 8 h 30 : lancer workspace-dev; chaque jour à 9 h : ouvrir spotify; aujourd'hui à 20 h 00 : sortir les poubelles.
toi   : Iris, supprime le rappel des poubelles
iris  : Supprimé : aujourd'hui à 20 h 00 : sortir les poubelles.
toi   : Iris, supprime l'automatisation de 9 h
iris  : Supprimé : chaque jour à 9 h : ouvrir spotify.
```

« supprime l'automatisation » sans précision supprime la seule qui existe ; s'il y en a plusieurs, Iris répond « Je ne trouve pas cette automatisation » et il faut préciser. La recherche accepte un bout du nom (« poubelles », « spotify »), l'heure (« 9 h »), ou le numéro affiché par la CLI.

```bash
iris automations                      # liste : numéro, planning, action, origine [voice | habit]
iris automations add "chaque matin à 9 h lance spotify"
iris automations delete spotify       # ou un numéro, ou "9 h"
iris automations run spotify          # exécute tout de suite (pour tester)
```

## Comment ça tourne

- La boucle vocale vérifie les échéances toutes les `automations.check_interval_s` secondes (30 par défaut), uniquement quand Iris est **en veille ou à l'écoute** — jamais pendant une confirmation, une dictée ou une pause : l'action est jouée juste après.
- Une automatisation quotidienne / hebdomadaire est due pendant les **10 minutes** qui suivent son heure, une seule fois par jour. Si Iris ne tournait pas dans cette fenêtre (machine éteinte), l'occurrence est sautée — sauf pour les rappels, toujours rattrapés.
- À l'exécution, Iris annonce **« Comme prévu : ghostty est lancé. »** (`automations.announce = true`) ; sans le préfixe si `false`. Le journal enregistre l'action comme n'importe quelle commande (`iris journal`), avec le texte `automation:<nom>` si `privacy.store_transcripts = true`.
- Une action programmée n'ouvre pas de fenêtre d'enchaînement : Iris l'annonce et reste dans l'état où elle était.
- `automations.enabled = false` désactive tout (les commandes vocales répondent « Les automatisations sont désactivées dans ma configuration ») ; les entrées existantes sont conservées.

## Suggestions automatiques

Iris peut aussi **proposer** une automatisation à partir de tes habitudes (« Tu fais souvent ouvrir spotify vers 9 h. Veux-tu que je m'en occupe chaque jour à 9 h ? »). Un « oui » crée l'automatisation exactement comme ci-dessus, avec la source `habit` dans `iris automations`. Voir [PERSONALIZATION.md](PERSONALIZATION.md#habitudes-et-suggestions).

## Limites

- Une automatisation = une action. « Chaque matin lance Spotify et le terminal » ne programme que la première ; dis-les séparément (ou déclare une commande `[[commands]]` qui fait les deux).
- Pas de planning « toutes les 2 heures » ni « le 1er du mois » : quotidien, jours de la semaine, ou une seule fois.
- Les automatisations vivent dans le processus `iris run` : si le service ne tourne pas, rien ne s'exécute. C'est voulu (aucune commande déclenchée hors de ta session graphique), et c'est ce qui permet de refuser proprement les actions critiques.
