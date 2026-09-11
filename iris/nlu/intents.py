"""Parseur d'intentions à base de règles (français + anglais).

Aucune dépendance : des expressions régulières appliquées au texte *canonique*
(voir ``iris.nlu.normalize``). Les commandes personnalisées de l'utilisateur
sont testées en premier, par correspondance floue.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from iris.config import CustomCommand
from iris.nlu.normalize import canonical, strip_politeness

DEVICE = r"(?:le |l'|la |the |my |mon |ma )?(?:pc|ordinateur|ordi|computer|system|systeme|machine|laptop|portable)"
ART = r"(?:l'|le |la |les |un |une |mon |ma |mes |the |my |a |an |this |ce |cet |cette )?"
APP_WORD = (
    r"(?:nouvelle |nouveau |nouvel |new )?"
    r"(?:application |app |appli |logiciel |programme |jeu |jeux |game "
    r"|page |onglet |fenetre |tab |window )?(?:de |d'|of )?"
)
APP_SUFFIX = r"(?:\s+(?:tab|window|page|onglet|fenetre))?"
WS_WORD = r"(?:workspace|bureau|espace de travail|espace|desktop)"
DIRECTION = r"(?P<direction>gauche|droite|haut|bas|left|right|up|down|suivant|next|precedent|prev)"
BT_ART = r"(?:mes |mon |ma |les |le |la |my |the |a |aux |au |to )?"


@dataclass
class Intent:
    name: str
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    text: str = ""
    requires_confirmation: bool = False
    command: CustomCommand | None = None

    def slot(self, key: str, default: Any = None) -> Any:
        return self.slots.get(key, default)


@dataclass(frozen=True)
class Rule:
    name: str
    patterns: Sequence[str]
    confirm: bool = False
    int_slots: Sequence[str] = ()

    def compiled(self) -> list[re.Pattern[str]]:
        return [re.compile(p) for p in self.patterns]


# L'ordre compte : les règles spécifiques précèdent les génériques (open_app / close_app).
RULES: list[Rule] = [
    # --- phase 4 : automatisations, rappels, alias, style, voix (en tête : elles contiennent d'autres phrases)
    Rule(
        "automation_list",
        [
            r"(?:quelles sont mes (?:automatisations|routines|programmations)|liste (?:mes |les |des )?(?:automatisations|rappels|programmations|routines)|"
            r"^mes (?:automatisations|rappels|routines)$|what are my (?:automations|reminders|routines)|list (?:my )?(?:automations|reminders))",
        ],
    ),
    Rule(
        "automation_delete",
        [
            r"^(?:supprime|efface|annule|retire|enleve|delete|remove|cancel)\s+(?:l'|la |le |les |mon |ma |mes |the |my )?"
            r"(?:automatisation|automation|rappel|reminder|programmation|routine)s?(?:\s+(?:de |du |d'|of |at |pour |for )?(?P<name>.+))?$",
        ],
    ),
    Rule(
        "reminder_create",
        [
            r"^(?:rappelle moi|remind me)\b(?P<rest>.*)$",
            r"^(?:dans \d+ ?(?:minutes?|min|heures?|h)|in \d+ ?(?:minutes?|min|hours?|h)|a \d{1,2}(?: ?h(?:eures?)?| ?\d{2})?(?: ?\d{2})?|"
            r"at \d{1,2}(?: ?\d{2})?(?: ?[ap]m)?|demain[^,]*|tomorrow[^,]*|ce soir[^,]*|tonight[^,]*)[,]?\s+(?:rappelle moi|remind me)\b(?P<rest2>.*)$",
        ],
    ),
    Rule(
        "automation_create",
        [
            r"\b(?:chaque|tous les|toutes les|every)\s+(?:matins?|soirs?|jours?|nuits?|midis?|days?|mornings?|evenings?|nights?|"
            r"weekdays?|weekends?|week ends?|jours? de (?:la )?semaine|jours? ouvres|lundis?|mardis?|mercredis?|jeudis?|vendredis?|"
            r"samedis?|dimanches?|mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)\b|"
            r"\b(?:en semaine|le week end|les week ends|on weekdays|on weekends)\b",
        ],
    ),
    Rule(
        "alias_learn",
        [
            r"^(?:quand je dis|lorsque je dis|when i say)\s+(?P<phrase>.+?)\s*,?\s+(?:c'est|ca veut dire|ca signifie|je veux dire|"
            r"je parle de|ouvre|lance|i mean|it means|that means|open|launch)\s+(?P<target>.+)$",
        ],
    ),
    Rule(
        "alias_list",
        [
            r"(?:quels sont mes alias|^mes alias$|liste (?:mes |des |les )?alias|what are my aliases|^my aliases$|list (?:my )?aliases)",
        ],
    ),
    Rule(
        "suggestions_off",
        [
            r"(?:arrete de (?:me )?(?:proposer|suggerer)|ne (?:me )?propose plus|plus de suggestions?|stop (?:suggesting|the suggestions)|no more suggestions)",
        ],
    ),
    Rule(
        "suggestions_on",
        [
            r"(?:propose moi a nouveau|reprends les suggestions|reactive les suggestions|resume (?:the )?suggestions|suggest again)",
        ],
    ),
    Rule(
        "habits_show",
        [
            r"(?:quelles sont mes habitudes|^mes habitudes$|^mes routines$|what are my habits|^my habits$)"
        ],
    ),
    Rule(
        "voice_speed",
        [
            r"^(?:parle|speak|talk)\s+(?:un peu |beaucoup |a bit |much )?(?P<dir>plus vite|plus rapidement|faster|quicker|plus lentement|moins vite|slower|more slowly)$",
            r"^(?:vitesse normale|parle normalement|parle a vitesse normale|normal speed|speak normally)$",
        ],
    ),
    Rule(
        "voice_change",
        [
            r"^(?:change de voix|prends une autre voix|autre voix|change (?:your |the )?voice|use another voice|next voice)$",
            r"^(?:utilise|prends|mets|use|switch to)\s+(?:la |the )?voix\s+(?:de |d')?(?P<voice>.+)$",
            r"^(?:use|switch to)\s+(?:the )?(?P<voice2>.+?)\s+voice$",
        ],
    ),
    Rule(
        "style_verbosity",
        [
            r"(?P<concise>sois (?:plus )?(?:concise|breve|courte)|reponses? (?:plus )?courtes?|parle moins|moins de blabla|be (?:more )?concise|shorter answers|talk less|be brief)|"
            r"(?P<chatty>sois (?:plus )?bavarde|parle plus|developpe (?:plus|davantage)|be (?:more )?chatty|talk more|longer answers)|"
            r"(?P<normal>reponses? normales?|verbosite normale|normal answers)",
        ],
    ),
    Rule(
        "style_tone",
        [
            r"^(?:sois|be|deviens|become)\s+(?:un peu |plus |more |less |moins |tres |very |really )?(?P<tone>direct|directe|franche|franc|cash|"
            r"chaleureuse|chaleureux|douce|doux|gentille|warm|friendly|coach|motivante|motivant|energique|energetic|motivating|joueuse|joueur|"
            r"taquine|taquin|drole|playful|funny|fun|pro|professionnelle|professionnel|serieuse|serieux|professional|serious|formelle|formal|"
            r"zen|calme|posee|pose|calm|relaxed)$",
        ],
    ),
    Rule(
        "language_switch",
        [
            r"^(?:parle|reponds|reponds moi|speak|answer|talk|reply)\s+(?:en |in )?(?P<lang>francais|anglais|french|english)$",
        ],
    ),
    Rule(
        "wake_add",
        [
            r"^(?:appelle toi|tu t'appelles|reponds aussi a|reponds au nom de|call yourself|answer to|your name is|also answer to)\s+(?P<name>[\w' -]{2,30})$",
        ],
    ),
    Rule(
        "stop",
        [
            r"^(?:stop|arrete|arrete toi|annule|cancel|laisse tomber|tais toi|chut|silence|"
            r"never ?mind|oublie|oublie ca|forget it|rien|c'est bon|c'est rien)$",
        ],
    ),
    Rule(
        "pause_listening",
        [
            r"^(?:mets toi en pause|mets toi en veille|pause toi|ne m'ecoute plus|arrete d'ecouter|"
            r"stop listening|go to sleep|sleep now|repos)(?: pendant (?P<minutes>\d+) ?(?:min|minutes?))?$",
        ],
        int_slots=("minutes",),
    ),
    Rule(
        "resume_listening",
        [
            r"^(?:reprends l'ecoute|reveille toi|resume listening|wake up|je suis la|reprends)$",
        ],
    ),
    Rule(
        "help",
        [
            r"(?:qu'est ce que tu (?:sais|peux) faire|que (?:sais|peux) tu faire|tu (?:sais|peux) faire quoi|"
            r"^aide$|^help$|what can you do|(?:tes|les|liste des|liste tes) commandes|aide moi)",
        ],
    ),
    Rule(
        "who_are_you",
        [
            r"(?:qui es tu|t'es qui|tu es qui|who are you|what are you|presente toi|c'est quoi ton nom|"
            r"comment tu t'appelles|what's your name|what is your name)",
        ],
    ),
    Rule(
        "greet", [r"^(?:bonjour|salut|hello|hi|hey|coucou|bonsoir|yo|good morning|good evening)$"]
    ),
    Rule(
        "thanks",
        [r"^(?:merci(?: beaucoup| bien)?|thanks|thank you|thx|super merci|parfait merci)$"],
    ),
    Rule(
        "time",
        [
            r"(?:quelle heure|il est quelle heure|l'heure qu'il est|(?:donne|dis) moi l'heure|^l'heure$|"
            r"what time|the time|tell me the time)",
        ],
    ),
    Rule(
        "date",
        [
            r"(?:quel jour|quelle date|la date d'aujourd'hui|(?:donne|dis) moi la date|on est le combien|"
            r"what(?:'s| is) the date|what day|today's date|^la date$)",
        ],
    ),
    # --- dictée --------------------------------------------------------------------------
    Rule(
        "dictation_stop",
        [
            r"^(?:fin de (?:la )?dictee|arrete la dictee|termine la dictee|stop (?:la )?dictee|stop dictation|end dictation)$",
        ],
    ),
    Rule(
        "dictation_start_enter",
        [
            r"^(?:mode (?:prompt|terminal)|dictee (?:terminal|prompt)|(?:prompt|terminal) mode|terminal dictation|dictation with enter)$",
        ],
    ),
    Rule(
        "dictation_start",
        [
            r"^(?:mode dictee|dictee|commence la dictee|passe en (?:mode )?dictee|active la dictee|start dictation|dictation mode|dictation)$",
        ],
    ),
    Rule(
        "type_text",
        [
            r"^(?:ecris|ecrit|tape|saisis|dicte|write|type)\s*[:]?\s+(?P<text>.+)$",
        ],
    ),
    # --- écrans --------------------------------------------------------------------------
    Rule(
        "monitor_move",
        [
            rf"(?:envoie|deplace|bouge|mets|move|send)\s+(?:cette |la |this |the |active |l')?(?:fenetre|window)?\s*"
            rf"(?:sur|vers|to|on)\s+(?:l'|the )?(?:ecran|moniteur|monitor|screen)\s+(?:de |du |on the )?{DIRECTION}",
            rf"(?:envoie|deplace|bouge|move|send)\s+(?:cette |la |this |the |active )?(?:fenetre|window)?\s*(?:sur|vers|to|on)\s+(?:the )?{DIRECTION}\s+(?:ecran|moniteur|monitor|screen)",
        ],
    ),
    Rule(
        "monitor_focus",
        [
            rf"(?:va|vas|passe|bascule|switch|go|focus)\s+(?:sur |to |on )?(?:l'|the )?(?:ecran|moniteur|monitor|screen)\s+(?:de |du |on the )?{DIRECTION}",
            rf"^(?:ecran|screen|monitor|moniteur)\s+(?:de )?{DIRECTION}$",
            rf"(?:focus|go to|switch to)\s+(?:the )?{DIRECTION}\s+(?:monitor|screen)",
        ],
    ),
    # --- périphériques -------------------------------------------------------------------
    Rule(
        "bluetooth_off",
        [
            r"(?:desactive|eteins|coupe|disable|turn off)\s+(?:le |the )?bluetooth|bluetooth\s+off",
        ],
    ),
    Rule(
        "bluetooth_on",
        [
            r"(?:active|allume|mets|enable|turn on)\s+(?:le |the )?bluetooth|bluetooth\s+on",
        ],
    ),
    Rule(
        "bluetooth_disconnect",
        [
            rf"^(?:deconnecte|debranche|disconnect)\s+(?:moi\s+)?(?P<device_raw>{BT_ART}(?P<device>.+?))(?:\s+(?:en|via|par|over|du|from)\s+bluetooth)?$",
        ],
    ),
    Rule(
        "bluetooth_connect",
        [
            rf"^(?:connecte|connect|appaire|pair|branche)\s+(?:moi\s+)?(?P<device_raw>{BT_ART}(?P<device>.+?))(?:\s+(?:en|via|par|over|au|to)\s+bluetooth)?$",
        ],
    ),
    Rule(
        "wifi_off",
        [r"(?:desactive|eteins|coupe|disable|turn off)\s+(?:le |the )?wi ?fi|wi ?fi\s+off"],
    ),
    Rule("wifi_on", [r"(?:active|allume|mets|enable|turn on)\s+(?:le |the )?wi ?fi|wi ?fi\s+on"]),
    Rule(
        "airplane_off",
        [
            r"(?:desactive|quitte|enleve|sors du|disable|turn off)\s+(?:le |the )?mode avion|airplane mode off"
        ],
    ),
    Rule(
        "airplane_on",
        [
            r"(?:active|mets|passe en|enable|turn on)\s+(?:le |the )?mode avion|airplane mode(?: on)?$|^mode avion$"
        ],
    ),
    Rule(
        "battery",
        [
            r"(?:niveau de (?:la )?batterie|combien de batterie|etat de la batterie|^(?:la |ma )?batterie$|battery(?: level| status)?$|how much battery)",
        ],
    ),
    Rule(
        "audio_output_switch",
        [
            r"(?:change|bascule|switch)\s+(?:de |la |the )?(?:sortie audio|sortie son|sortie|audio output|sound output|output)|sortie audio suivante|next audio output",
        ],
    ),
    # --- notifications -------------------------------------------------------------------
    Rule(
        "notifications_dismiss",
        [
            r"(?:efface|ferme|vide|supprime|nettoie|dismiss|clear)\s+(?:mes |les |my |the |toutes les |all )?notifications",
        ],
    ),
    Rule(
        "notifications_read",
        [
            r"(?:lis|lire|donne|montre|resume|read|show)\s+(?:moi\s+)?(?:mes |les |my |the )?(?:dernieres |recent |latest )?notifications|"
            r"^(?:mes |les |my )?notifications$|quelles sont mes notifications|what are my notifications|"
            r"(?:j'ai|y a t il) (?:des )?notifications",
        ],
    ),
    Rule(
        "dnd_off",
        [
            r"(?:desactive|enleve|quitte|disable|turn off)\s+(?:le mode )?(?:ne pas deranger|do not disturb|dnd)|(?:ne pas deranger|do not disturb) off",
        ],
    ),
    Rule(
        "dnd_on",
        [
            r"(?:active|mets|passe en|enable|turn on)\s+(?:le mode )?(?:ne pas deranger|do not disturb|dnd)|^(?:mode )?ne pas deranger$|^do not disturb$",
        ],
    ),
    # --- mémoire ------------------------------------------------------------------------
    Rule(
        "forget_all",
        [
            r"^(?:oublie tout|efface ta memoire|vide ta memoire|forget everything|clear your memory)$"
        ],
    ),
    Rule("forget", [r"^(?:oublie|forget)\s+(?:que |that )?(?P<fact>.+)$"]),
    Rule(
        "remember",
        [
            r"^(?:retiens|souviens toi|rappelle toi|memorise|prends note|remember|keep in mind|note bien)\s+(?:bien )?(?:que |that )?(?P<fact>.+)$",
        ],
    ),
    Rule(
        "recall",
        [
            r"(?:qu'est ce que tu sais (?:de|sur) moi|que sais tu (?:de|sur) moi|de quoi te souviens tu|de quoi tu te souviens|"
            r"ta memoire|tes souvenirs|what do you know about me|what do you remember)",
        ],
    ),
    # --- projets et sessions ----------------------------------------------------------------
    Rule(
        "open_project",
        [
            r"^(?:ouvre|lance|open|launch|va dans|go to)\s+(?:moi\s+)?(?:le |the )?(?:projet|project)\s+(?P<name>.+)$",
        ],
    ),
    Rule(
        "session_resume",
        [
            r"^(?:reprends|reprend|restaure|resume|restore)\s+(?:ma |la |my |the )?(?:derniere |last |previous )?session"
            r"(?:\s+(?:de|of)\s+[\w ]+?)?(?:\s+(?:d'hier|precedente|d'avant|of yesterday|from yesterday))?$",
        ],
    ),
    # --- tâches et agents ---------------------------------------------------------------------
    Rule(
        "task_status",
        [
            r"^(?:ou en est|ou en sont|comment avance|comment avancent|etat de|etat des|status of|how is|how's|how are)\s+"
            r"(?:la |le |les |mes |ma |mon |the |my )?(?P<name>.+?)\s*$",
            r"^(?:mes taches|les taches|etat des taches|taches en cours|tasks|task status|running tasks|mes agents)$",
        ],
    ),
    Rule(
        "task_result",
        [
            r"^(?:lis|donne|montre|read|show)\s+(?:moi\s+)?(?:le |la |the )?(?:resultat|sortie|reponse|result|output|answer)"
            r"(?:\s+(?:de |du |de la |of |of the )(?:la |the )?(?P<name>.+?))?$",
            r"^(?:qu'a (?:repondu|dit|fait|trouve)|qu'est ce qu'a (?:repondu|dit|fait|trouve))\s+(?P<agent>claude|opencode|codex|gemini|l'agent)$",
            r"^what did (?P<agent2>claude|opencode|codex|gemini|the agent) (?:say|answer|do|find)$",
        ],
    ),
    Rule(
        "task_cancel",
        [
            r"^(?:annule|arrete|stoppe|interromps|cancel|abort)\s+"
            r"(?!(?:la |le |les |the )?(?:musique|lecture|music|son|volume|dictee|dictation|ecoute|listening)\b)"
            r"(?:la |le |les |the )?(?:tache |task )?(?P<name>.+)$",
        ],
    ),
    Rule(
        "task_watch",
        [
            r"^(?:surveille|surveilles|watch|monitor|suis|garde un oeil sur|keep an eye on)\s+(?:la |le |les |the |my |ma |mon )?(?P<name>.+)$",
        ],
    ),
    Rule(
        "task_run",
        [
            r"^(?:lance|execute|run|start)\s+(?:la |the )?(?:tache|task|job)\s+(?P<name>.+)$",
        ],
    ),
    # --- sessions ------------------------------------------------------------------------
    Rule(
        "session_save",
        [
            r"^(?:sauvegarde|enregistre|sauve|save)\s+(?:cette |la |ma |this |the |my )?session(?:\s+(?:sous|comme|as))?\s+(?:le nom )?(?P<name>.+)$",
        ],
    ),
    Rule(
        "session_open",
        [
            r"^(?:ouvre|lance|charge|restaure|reprends|open|launch|restore|load|resume)\s+(?:moi\s+)?(?:ma |la |my |the )?session\s+(?:de |du |d')?(?P<name>.+)$",
        ],
    ),
    # --- fenêtres et workspaces ------------------------------------------------------------
    Rule(
        "close_all",
        [
            r"^(?:ferme|quitte|close|quit)\s+(?:tout|toutes? (?:les )?(?:applications|applis|apps|fenetres)|"
            r"all(?: (?:the )?(?:apps|applications|windows))?)$",
        ],
        confirm=True,
    ),
    Rule(
        "window_close",
        [
            r"^(?:ferme|close|kill|quitte)\s+(?:cette |cet |la |this |the |active |current )?(?:fenetre|window|page|onglet|tab)"
            r"(?: (?:active|courante|actuelle))?$",
        ],
    ),
    Rule("window_fullscreen", [r"(?:plein ecran|fullscreen|full screen)"]),
    Rule("window_floating", [r"(?:flottant|flottante|floating)"]),
    Rule(
        "window_move_workspace",
        [
            r"(?:envoie|deplace|bouge|mets|move|send)\s+(?:cette |la |this |the |active |l'|the active )?"
            r"(?:fenetre|window|app|application)?\s*(?:sur|vers|au|dans|to|on)\s+(?:le |the )?"
            rf"{WS_WORD}\s+(?:numero |number |n )?(?P<n>\d+)",
        ],
        int_slots=("n",),
    ),
    Rule(
        "workspace_next",
        [
            rf"{WS_WORD}\s+(?:suivant|d'apres|next)|(?:next|prochain)\s+{WS_WORD}",
        ],
    ),
    Rule(
        "workspace_prev",
        [
            rf"{WS_WORD}\s+(?:precedent|d'avant|previous)|(?:previous|prev)\s+{WS_WORD}",
        ],
    ),
    Rule(
        "workspace_switch",
        [
            rf"\b{WS_WORD}\s+(?:numero |number |n )?(?P<n>\d+)\b",
        ],
        int_slots=("n",),
    ),
    # --- volume --------------------------------------------------------------------------
    Rule(
        "volume_mute",
        [
            r"(?:coupe|desactive|eteins|arrete|mute)\s+(?:le |the )?(?:son|volume|audio|sound|micro)|"
            r"^(?:mute|silence|sourdine)$|(?:mets? (?:en )?sourdine|en sourdine)",
        ],
    ),
    Rule(
        "volume_unmute",
        [
            r"(?:remets|reactive|retablis|rallume|unmute|restore)\s+(?:le |the )?(?:son|volume|audio|sound)|"
            r"^unmute$|enleve (?:la )?sourdine",
        ],
    ),
    Rule(
        "volume_set",
        [
            r"(?:volume|son|sound)\s+(?:a|sur|to|at)?\s*(?P<n>\d{1,3})\s*%?(?:\s|$)",
            r"(?:mets?|regle|set|put)\s+(?:le |the )?(?:volume|son)\s+(?:a|sur|to|at)\s+(?P<n>\d{1,3})",
        ],
        int_slots=("n",),
    ),
    Rule(
        "volume_up",
        [
            r"(?:monte|augmente|hausse|remonte|increase|raise|turn up|up|boost)\s+(?:le |the |un peu le )?"
            r"(?:son|volume|sound)(?:\s+(?:de|of|by)\s+(?P<n>\d{1,3})\s*%?)?",
            r"(?:son|volume|sound)\s+(?:plus fort|up|louder)(?:\s+(?:de|by)\s+(?P<n>\d{1,3}))?",
            r"^(?:plus fort|louder)$",
        ],
        int_slots=("n",),
    ),
    Rule(
        "volume_down",
        [
            r"(?:baisse|diminue|reduis|descends|decrease|lower|turn down|down)\s+(?:le |the |un peu le )?"
            r"(?:son|volume|sound)(?:\s+(?:de|of|by)\s+(?P<n>\d{1,3})\s*%?)?",
            r"(?:son|volume|sound)\s+(?:moins fort|down|quieter|lower)(?:\s+(?:de|by)\s+(?P<n>\d{1,3}))?",
            r"^(?:moins fort|quieter)$",
        ],
        int_slots=("n",),
    ),
    # --- luminosité ----------------------------------------------------------------------
    Rule(
        "brightness_set",
        [
            r"(?:luminosite|brightness)\s+(?:a|sur|to|at)?\s*(?P<n>\d{1,3})\s*%?(?:\s|$)",
            r"(?:mets?|regle|set)\s+(?:la |the )?(?:luminosite|brightness)\s+(?:a|sur|to|at)\s+(?P<n>\d{1,3})",
        ],
        int_slots=("n",),
    ),
    Rule(
        "brightness_up",
        [
            r"(?:monte|augmente|hausse|increase|raise|turn up|up)\s+(?:la |the )?(?:luminosite|brightness)"
            r"(?:\s+(?:de|of|by)\s+(?P<n>\d{1,3}))?",
            r"(?:luminosite|brightness)\s+(?:plus forte?|up|higher)",
            r"(?:ecran|screen)\s+plus (?:lumineux|clair)|^brighter$",
        ],
        int_slots=("n",),
    ),
    Rule(
        "brightness_down",
        [
            r"(?:baisse|diminue|reduis|decrease|lower|turn down|down)\s+(?:la |the )?(?:luminosite|brightness)"
            r"(?:\s+(?:de|of|by)\s+(?P<n>\d{1,3}))?",
            r"(?:luminosite|brightness)\s+(?:moins forte?|down|lower)",
            r"(?:ecran|screen)\s+(?:moins lumineux|plus sombre)|^dimmer$",
        ],
        int_slots=("n",),
    ),
    # --- média ---------------------------------------------------------------------------
    Rule(
        "media_play_pause",
        [
            r"^(?:mets? (?:en )?pause|pause|play|lecture|reprends? (?:la )?(?:musique|lecture)|resume|"
            r"joue|mets? (?:la |de la )?musique|play (?:the )?music|stop (?:la )?musique|stop (?:the )?music|"
            r"arrete (?:la )?musique|pause (?:la )?musique|pause (?:the )?music)$",
        ],
    ),
    Rule(
        "media_next",
        [
            r"(?:musique|piste|chanson|morceau|titre|track|song)\s+(?:suivante?|d'apres|next)|"
            r"(?:next|prochaine?)\s+(?:musique|piste|chanson|morceau|titre|track|song)|^(?:suivant|suivante|next|skip)$",
        ],
    ),
    Rule(
        "media_prev",
        [
            r"(?:musique|piste|chanson|morceau|titre|track|song)\s+(?:precedente?|d'avant|previous)|"
            r"(?:previous|prev)\s+(?:track|song)|^(?:precedent|precedente|previous)$",
        ],
    ),
    # --- Omarchy -------------------------------------------------------------------------
    Rule(
        "theme_next",
        [
            r"(?:change|switch|next|passe au|suivant)\s+(?:de |the |au )?theme|theme\s+(?:suivant|next)|next theme",
        ],
    ),
    Rule(
        "theme_set",
        [
            r"(?:mets?|applique|active|utilise|set|use|apply|passe (?:au|en)|change pour le)\s+(?:le |the )?theme\s+(?P<name>.+)$",
        ],
    ),
    Rule(
        "night_light",
        [
            r"(?:mode nuit|lumiere de nuit|filtre (?:de )?lumiere bleue|night ?light|night mode|nightlight)",
        ],
    ),
    Rule(
        "screenshot",
        [
            r"(?:capture d'ecran|capture ecran|screenshot|screen shot|prends? (?:une )?capture|fais (?:une )?capture)",
        ],
    ),
    Rule(
        "lock_screen",
        [
            r"^(?:verrouille|bloque|lock)\s*(?:l'|le |la |the |my )?\s*(?:ecran|session|screen|computer|pc|ordinateur|ordi)?$",
        ],
    ),
    # --- alimentation (confirmation obligatoire) -----------------------------------------
    Rule(
        "suspend",
        [
            rf"(?:mets?|met|put)\s+(?:{DEVICE}\s+)?(?:en veille|to sleep|en sommeil)",
            rf"^(?:veille|suspend|suspends|hibernate|hiberne)(?:\s+{DEVICE})?$",
        ],
        confirm=True,
    ),
    Rule(
        "shutdown",
        [
            rf"(?:eteins|eteindre|arrete|shutdown|shut down|power off|turn off)\s+{DEVICE}",
        ],
        confirm=True,
    ),
    Rule(
        "reboot",
        [
            rf"(?:redemarre|redemarrer|reboot|restart)\s+{DEVICE}|^(?:reboot|redemarre)$",
        ],
        confirm=True,
    ),
    Rule(
        "type_and_enter",
        [
            r"^(?:envoie|send|submit|tape et valide|ecris et valide|dis au terminal|tell the terminal|prompt)\s*[:]?\s+"
            r"(?!(?:cette |la |this |the |active |l')?(?:fenetre|window|app|application)\b)(?!ca sur|ca vers|it to)(?P<text>.+)$",
        ],
    ),
    # --- parole --------------------------------------------------------------------------
    Rule("say", [r"^(?:dis|dis moi|repete|repete apres moi|say|repeat)\s+(?P<text>.+)$"]),
    # --- web -----------------------------------------------------------------------------
    Rule(
        "open_url",
        [
            r"^(?:ouvre|va sur|vas sur|lance|open|go to|goto|launch)\s+(?:le |la |the )?"
            r"(?:site |site web |website |page |url )?(?:https?://)?(?P<url>[\w.-]+\.[a-z]{2,}(?:/\S*)?)$",
        ],
    ),
    Rule(
        "web_search",
        [
            r"^(?:cherche|recherche|search|google|look up|lookup|find)\s+(?:moi\s+|for\s+|me\s+)?"
            r"(?P<query>.+?)(?:\s+(?:sur|on)\s+(?:le |the )?(?:web|internet|google|net))?$",
        ],
    ),
    Rule(
        "ask_agent",
        [
            r"^(?:demande a|ask|dis a|tell)\s+(?P<agent>claude|opencode|codex|gemini|l'agent|the agent)[,:]?\s+(?:de |d'|to )?(?P<prompt>.+)$",
            # « lance Claude Code » nomme une application, pas une consigne donnée à Claude.
            r"^(?:lance|run|start|launch)\s+(?P<agent2>un agent|an agent|l'agent|the agent"
            r"|claude(?!\s+(?:code|cli)\b)|opencode|codex|gemini)"
            r"\s*[:,]?\s+(?:pour |to |de |d')?(?P<prompt>.+)$",
        ],
    ),
    # --- applications (génériques, en dernier) -------------------------------------------
    Rule(
        "close_app",
        [
            rf"^(?:ferme|quitte|tue|close|quit|kill|exit)\s+(?P<app_raw>{ART}{APP_WORD}(?P<app>.+?){APP_SUFFIX})$",
        ],
    ),
    Rule(
        "open_app",
        [
            rf"^(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|execute|open|launch|start|run)\s+(?:moi\s+)?"
            rf"(?P<app_raw>{ART}{APP_WORD}(?P<app>.+?){APP_SUFFIX})$",
        ],
    ),
    Rule(
        "ask_llm",
        [
            r"^(?:question|explique(?: moi)?|raconte(?: moi)?|pourquoi|comment|qu'est ce que|qu'est ce qu'|c'est quoi|que penses tu|"
            r"qu'en penses tu|dis moi pourquoi|dis moi comment|donne moi une idee|conseille moi|explain|why|how do|how does|how can|"
            r"what is|what's|what are|tell me about|question)\b\s*[:]?\s*(?P<prompt>.*)$",
        ],
    ),
]

YES_WORDS = {
    "oui",
    "ouais",
    "ouaip",
    "ok",
    "okay",
    "d'accord",
    "confirme",
    "confirmer",
    "je confirme",
    "vas y",
    "go",
    "yes",
    "yeah",
    "yep",
    "yup",
    "sure",
    "do it",
    "affirmatif",
    "bien sur",
    "exact",
    "c'est bon",
    "fais le",
    "fais",
    "carrement",
    "absolument",
    "evidemment",
    "certainement",
}
NO_WORDS = {
    "non",
    "nan",
    "annule",
    "annuler",
    "cancel",
    "no",
    "nope",
    "stop",
    "surtout pas",
    "laisse tomber",
    "negatif",
    "pas maintenant",
    "not now",
    "never mind",
    "nevermind",
    "attends",
    "wait",
}


def parse_yes_no(text: str) -> bool | None:
    """Interprète une réponse à une demande de confirmation. None = incompréhensible."""
    t = strip_politeness(canonical(text))
    if not t:
        return None
    words = t.split()
    for no in NO_WORDS:
        if t == no or t.startswith(no + " ") or f" {no} " in f" {t} ":
            return False
    for yes in YES_WORDS:
        if t == yes or t.startswith(yes + " ") or t.startswith(yes + ","):
            return True
    if words and words[0] in {"oui", "yes", "ok"}:
        return True
    return None


CONFIRM_INTENTS = {r.name for r in RULES if r.confirm}
# Slots dont on veut le texte d'origine (accents, majuscules) plutôt que la forme canonique.
FREE_TEXT_SLOTS = (
    "text",
    "fact",
    "prompt",
    "query",
    "phrase",
    "target",
    "rest",
    "rest2",
    "voice",
    "voice2",
    "name",
)
_EDGE = re.compile(r"^[\s,;:!?.…\"'«»()-]+|[\s,;:!?.…\"'«»()-]+$")


def _recover_original(original: str, slot: str) -> str:
    """Retrouve dans la phrase d'origine le passage qui correspond au slot canonique
    (« bonjour a tous » → « Bonjour à tous », « ecrire un readme » → « écrire un README »)."""
    words = original.split()
    target = canonical(slot)
    n = len(target.split())
    for k in range(max(1, n - 2), min(len(words), n + 3) + 1):
        for i in range(len(words) - k, -1, -1):
            candidate = _EDGE.sub("", " ".join(words[i : i + k]))
            canon = canonical(candidate)
            if canon == target:
                return candidate
            if canon.endswith(" " + target) or canon.endswith(target):
                elided = re.sub(r"^\w{1,3}'", "", candidate)
                if canonical(elided) == target:
                    return elided
    return slot


INTENT_NAMES = [r.name for r in RULES]
_SESSION_VERB = re.compile(
    r"^(?:ouvre|lance|charge|restaure|reprends|open|launch|restore|load|resume)\s+(?:moi\s+)?"
)


class IntentParser:
    def __init__(
        self,
        custom_commands: Iterable[CustomCommand] = (),
        fuzzy_threshold: float = 0.85,
        rules: Sequence[Rule] = RULES,
        session_phrases: dict[str, Iterable[str]] | None = None,
        task_phrases: dict[str, Iterable[str]] | None = None,
    ) -> None:
        self._rules: list[tuple[Rule, list[re.Pattern[str]]]] = [(r, r.compiled()) for r in rules]
        self._custom = [(c, [canonical(p) for p in c.phrases]) for c in custom_commands]
        self._sessions = {
            name: [canonical(p) for p in phrases]
            for name, phrases in (session_phrases or {}).items()
        }
        self._tasks = {
            name: [canonical(p) for p in phrases] for name, phrases in (task_phrases or {}).items()
        }
        self._fuzzy = fuzzy_threshold

    # ------------------------------------------------------------------ public
    def parse(self, text: str) -> Intent | None:
        canon = strip_politeness(canonical(text))
        if not canon:
            return None

        custom = self._match_custom(canon, text)
        if custom is not None:
            return custom
        session = self._match_session(canon, text)
        if session is not None:
            return session
        task = self._match_task(canon, text)
        if task is not None:
            return task

        for rule, patterns in self._rules:
            for pattern in patterns:
                m = pattern.search(canon)
                if not m:
                    continue
                slots = {k: v.strip() for k, v in m.groupdict().items() if v}
                for key in FREE_TEXT_SLOTS:
                    if key in slots:
                        slots[key] = _recover_original(text, slots[key])
                for key in rule.int_slots:
                    if key in slots:
                        try:
                            slots[key] = int(slots[key])
                        except ValueError:
                            del slots[key]
                return Intent(
                    name=rule.name,
                    slots=slots,
                    confidence=0.9,
                    text=text,
                    requires_confirmation=rule.confirm,
                )
        return None

    def intent_names(self) -> list[str]:
        return [r.name for r, _ in self._rules]

    # ----------------------------------------------------------------- helpers
    def _match_session(self, canon: str, original: str) -> Intent | None:
        """« ouvre ma session vidéo » / « ma session vidéo » quand la phrase est déclarée dans [[sessions]]."""
        stripped = _SESSION_VERB.sub("", canon)
        for name, phrases in self._sessions.items():
            for phrase in phrases:
                if stripped == phrase or canon == phrase:
                    return Intent("session_open", {"name": name}, 1.0, original)
        return None

    def _match_task(self, canon: str, original: str) -> Intent | None:
        """Phrases déclarées dans [[tasks]] → task_run (« lance la compilation »)."""
        for name, phrases in self._tasks.items():
            for phrase in phrases:
                if canon == phrase or SequenceMatcher(None, canon, phrase).ratio() >= 0.93:
                    return Intent("task_run", {"name": name}, 1.0, original)
        return None

    def _match_custom(self, canon: str, original: str) -> Intent | None:
        best: tuple[float, CustomCommand] | None = None
        for command, phrases in self._custom:
            for phrase in phrases:
                if canon == phrase:
                    ratio = 1.0
                else:
                    ratio = SequenceMatcher(None, canon, phrase).ratio()
                if ratio >= self._fuzzy and (best is None or ratio > best[0]):
                    best = (ratio, command)
        if best is None:
            return None
        ratio, command = best
        return Intent(
            name="custom",
            slots={"command": command.name},
            confidence=ratio,
            text=original,
            requires_confirmation=command.confirm,
            command=command,
        )
