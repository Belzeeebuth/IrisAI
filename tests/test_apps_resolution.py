"""Retrouver n'importe quelle application installée, même mal transcrite."""

from __future__ import annotations

import pytest

from iris.actions.apps import AppResolver, _prefix_of_words, _same_shape, match_score
from iris.nlu.intents import IntentParser

parse = IntentParser([]).parse

DESKTOP_FILES = {
    "org.prismlauncher.PrismLauncher.desktop": """
        [Desktop Entry]
        Type=Application
        Name=Prism Launcher
        Comment=Discover, manage, and play Minecraft instances
        Exec=prismlauncher %U
        Keywords=game;minecraft;mc;
        StartupWMClass=PrismLauncher
        Terminal=false
    """,
    "com.obsproject.Studio.desktop": """
        [Desktop Entry]
        Type=Application
        Name=OBS Studio
        Exec=obs
    """,
    "libreoffice-writer.desktop": """
        [Desktop Entry]
        Type=Application
        Name=LibreOffice Writer
        Name[fr]=LibreOffice Texte
        Exec=libreoffice --writer %U
    """,
    "steam-3551340.desktop": """
        [Desktop Entry]
        Type=Application
        Name=Football Manager 26
        Exec=steam steam://rungameid/3551340
    """,
    "mimeinfo-handler.desktop": """
        [Desktop Entry]
        Type=Application
        Name=Gestionnaire de types
        Exec=handler %u
        NoDisplay=true
    """,
    "not-an-app.desktop": """
        [Desktop Entry]
        Type=Link
        Name=Raccourci
        Exec=rien
    """,
}


@pytest.fixture
def resolver(fake_system, tmp_path, monkeypatch):
    """Un résolveur qui ne voit que les applications décrites ci-dessus."""
    applications = tmp_path / "applications"
    applications.mkdir()
    for name, body in DESKTOP_FILES.items():
        text = "\n".join(line.strip() for line in body.strip().splitlines())
        (applications / name).write_text(text + "\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "vide"))
    return AppResolver()


# ---------------------------------------------------------------- note de correspondance
@pytest.mark.parametrize(
    ("asked", "name", "expected"),
    [
        ("prism launcher", "prism launcher", 100.0),  # exact
        ("libre office writer", "libreoffice writer", 92.0),  # aux espaces près
        ("prism", "prism launcher", 84.0),  # préfixe sur un mot entier
        ("launcher prism", "prism launcher", 76.0),  # mêmes mots, ordre libre
        ("office writer", "libreoffice writer", 68.0),  # sous-chaîne
    ],
)
def test_match_score_franc(asked, name, expected):
    assert match_score(asked, name) == expected


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("prismenscher", "prism launcher"),  # transcription phonétique
        ("prism lensure", "prism launcher"),  # un mot juste, l'autre approché
        ("discorde", "discord"),
    ],
)
def test_match_score_approche(asked, name):
    assert 0 < match_score(asked, name) < 68.0


@pytest.mark.parametrize(
    ("asked", "name"),
    [
        ("obsidienne", "obs"),  # un nom court ne doit pas capter un mot plus long
        ("football manager", "foot"),
        ("machin truc", "prism launcher"),
        ("la musique", "obs studio"),
        ("", "prism launcher"),
        # « Claude Code » transcrit « cloud code » avait ouvert l'éditeur : un mot
        # entier de la demande restait inexpliqué par le nom retenu.
        ("cloud code", "code"),
        ("cloud code", "opencode"),
        ("cloud code", "editeur de code"),
        ("last clot good", "code"),
    ],
)
def test_match_score_refuse(asked, name):
    assert match_score(asked, name) == 0.0


def test_un_mot_inexplique_ne_suffit_pas():
    """Le rapprochement approximatif exige la même forme : autant de mots, taille voisine."""
    assert _same_shape(["prism", "lensure"], ["prism", "launcher"])
    assert not _same_shape(["cloud", "code"], ["code"])
    assert not _same_shape(["cloud", "code"], ["opencode"])
    assert not _same_shape(["cloud", "code"], ["editeur", "de", "code"])


def test_prefix_sarrete_sur_un_mot():
    assert _prefix_of_words("prism", "prism launcher")
    assert _prefix_of_words("prism launcher", "prism")
    assert not _prefix_of_words("obs", "obsidienne")
    assert not _prefix_of_words("foot", "football manager")


# ---------------------------------------------------------------- résolution
@pytest.mark.parametrize(
    "query",
    ["prism launcher", "prism", "launcher prism", "prismenscher", "prism lensure"],
)
def test_nom_entendu_meme_approximatif(resolver, query):
    app = resolver.resolve(query)
    assert app is not None
    assert app.label == "Prism Launcher"
    assert app.argv == ["prismlauncher"]


def test_mot_cle_du_desktop(resolver):
    """« minecraft » n'est le nom d'aucune application : c'est un mot-clé de Prism Launcher."""
    assert resolver.resolve("minecraft").label == "Prism Launcher"


@pytest.mark.parametrize("query", ["le jeu minecraft", "jeu minecraft", "game minecraft"])
def test_le_mot_jeu_est_ignore(resolver, query):
    assert resolver.resolve(query).label == "Prism Launcher"


def test_intention_avec_le_mot_jeu():
    intent = parse("lance le jeu minecraft")
    assert intent is not None and intent.name == "open_app"
    assert intent.slot("app") == "minecraft"


def test_nom_court_ne_capte_pas_un_mot_plus_long(resolver):
    assert resolver.resolve("obs").label == "OBS Studio"
    assert resolver.resolve("obsidienne") is None


def test_espaces_en_trop(resolver):
    app = resolver.resolve("libre office writer")
    assert app is not None and app.argv == ["libreoffice", "--writer"]


def test_nom_francais_du_desktop(resolver):
    assert resolver.resolve("libreoffice texte").label == "LibreOffice Writer"


def test_nom_compose_avec_un_chiffre(resolver):
    app = resolver.resolve("football manager")
    assert app is not None and app.label == "Football Manager 26"


def test_classe_de_fenetre_retenue_pour_la_fermeture(resolver):
    app = resolver.resolve("prism launcher")
    assert "PrismLauncher" in app.match_keys
    assert "prism launcher" in app.match_keys


@pytest.mark.parametrize(
    "query", ["machin truc", "qwertyuiop", "raconte moi une blague", "gestionnaire de types"]
)
def test_rien_plutot_quun_mauvais_choix(resolver, query):
    assert resolver.resolve(query) is None


def test_entree_de_type_lien_ignoree(resolver):
    assert resolver.resolve("raccourci") is None


@pytest.mark.parametrize("query", ["claude code", "cloud code", "claude cli"])
def test_claude_code_lance_la_cli_pas_lediteur(resolver, fake_system, monkeypatch, query):
    """« lance Claude Code » ouvrait Neovim : la CLI n'existait comme alias nulle part."""
    monkeypatch.setenv("TERMINAL", "xdg-terminal-exec")
    fake_system.available.add("xdg-terminal-exec")
    app = resolver.resolve(query)
    assert app is not None and app.argv == ["xdg-terminal-exec", "-e", "claude"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("lance claude code", "open_app"),  # une application…
        ("ouvre claude code", "open_app"),
        ("lance claude cli", "open_app"),
        ("lance claude pour resumer ce fichier", "ask_agent"),  # …et non une consigne
        ("demande a claude de resumer ce fichier", "ask_agent"),
        ("lance un agent pour trier mes mails", "ask_agent"),
    ],
)
def test_claude_code_nest_pas_une_consigne_donnee_a_lagent(text, expected):
    intent = parse(text)
    assert intent is not None and intent.name == expected


@pytest.mark.parametrize(
    ("text", "expected_intent", "app"),
    [
        ("ferme complètement steam", "close_app", "steam"),
        ("ferme vraiment spotify", "close_app", "spotify"),
        ("quitte totalement discord", "close_app", "discord"),
        ("close completely discord", "close_app", "discord"),
        ("lance direct firefox", "open_app", "firefox"),
        ("ouvre tout de suite prism launcher", "open_app", "prism launcher"),
        ("lance juste spotify", "open_app", "spotify"),
    ],
)
def test_adverbes_entre_le_verbe_et_le_nom(text, expected_intent, app):
    """« ferme complètement Steam » cherchait une application nommée « complètement steam »."""
    intent = parse(text)
    assert intent is not None and intent.name == expected_intent
    assert intent.slot("app") == app
