# Contribuer

1. `uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"`
2. `.venv/bin/pytest` doit rester vert ; `.venv/bin/ruff check iris tests` et `ruff format` aussi.
3. Une intention = une règle + un gestionnaire + des phrases **fr et en** + un test (voir `docs/ARCHITECTURE.md`).
4. Pas de dépendance dure nouvelle sans repli : Iris doit démarrer avec numpy seul.
5. Rien ne doit sortir de la machine par défaut (`privacy.allow_cloud`).
6. Retours terrain bienvenus (issues) : modèle Whisper utilisé, CPU, seuils VAD/wake qui fonctionnent chez toi, variantes de « Iris » transcrites par Whisper.
