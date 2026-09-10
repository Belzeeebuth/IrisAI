# Cerveau LLM

## Rôle

Le moteur de règles d'Iris répond instantanément et hors-ligne à ce qu'il connaît. Le LLM prend le relais pour :

1. **les phrases hors règles** (`llm.fallback_nlu = true`) : « il fait trop sombre là » → `{"action": "brightness_up"}` ; « c'est quoi la différence entre Wayland et X11 ? » → réponse parlée ; bruit ambiant → `{"ignore": true}` (silence) ;
2. **les questions ouvertes** (`llm.chat = true`) : « Iris, explique-moi… », « pourquoi… », « question : … » ;
3. **la personnalité** (`assistant.personality`) et le **contexte** (`llm.context`).

Une action proposée par le modèle est convertie en intention ordinaire : elle passe par les mêmes gestionnaires et les mêmes confirmations (« Veux-tu vraiment éteindre l'ordinateur ? »). Le modèle ne peut pas inventer une action absente de la liste des capacités.

## OpenCode Zen et OpenCode Go

[OpenCode](https://opencode.ai) propose deux offres, toutes deux avec une clé utilisable hors de l'outil OpenCode :

| | OpenCode Go | OpenCode Zen |
|---|---|---|
| Tarif | 10 $/mois, usage inclus par paliers (5 h / semaine / mois, montants selon le modèle) | paiement à l'usage, solde prépayé, sans marge |
| Modèles | ouverts : `glm-5.3-flash`, `glm-5.3`, `kimi-k2.6`, `kimi-k3`, `minimax-m3`, `minimax-m2.7`, `qwen3.7-plus`, `qwen3.8-max`, `deepseek-v4-flash`, `deepseek-v4-pro`, `gpt-5.6-luna`, `grok-4.6`, `mimo-v2.5`… | les mêmes + frontière : `claude-haiku-4-5`, `claude-sonnet-5`, `claude-opus-5`, `gpt-5.4-mini`, `gpt-5.5`, `gemini-3.5-flash`, `grok-4.6`… et des modèles gratuits (`big-pickle`, `mimo-v2.5-free`…) |
| Base URL | `https://opencode.ai/zen/go/v1` | `https://opencode.ai/zen/v1` |
| `provider` | `"opencode-go"` | `"opencode-zen"` |

Endpoints : `/chat/completions` (OpenAI-compatible : GPT, GLM, Kimi, MiniMax, DeepSeek, Grok…), `/messages` (Anthropic-compatible : Claude, Qwen). Iris choisit automatiquement (`llm.api = "auto"`), ou force `"chat"` / `"messages"`.

Recommandations pour un assistant vocal (latence + coût) : `glm-5.3-flash` ou `deepseek-v4-flash` (Go) ; `claude-haiku-4-5` ou `gpt-5.4-mini` (Zen) pour une meilleure compréhension du français familier.

## Configuration

```bash
# clé : https://opencode.ai/auth  (Go : souscrire puis copier la clé)
echo 'OPENCODE_API_KEY=sk-…' >> ~/.config/environment.d/iris.conf
systemctl --user import-environment OPENCODE_API_KEY && systemctl --user restart iris
```

```toml
[llm]
enabled = true
provider = "opencode-go"      # opencode-go | opencode-zen | openai | openrouter | ollama | custom
model = "glm-5.3-flash"
api_key_env = "OPENCODE_API_KEY"
timeout_s = 30.0
max_tokens = 400
temperature = 0.4
fallback_nlu = true
chat = true
context = true
history_turns = 6

[assistant]
personality = "Tutoie-moi, sois directe, un peu taquine, jamais mielleuse."

[privacy]
allow_cloud = true
```

Vérification : `iris llm info` (configuration effective, clé présente ?), `iris llm models` (modèles que ton compte voit), `iris llm test "présente-toi en une phrase"`, `iris llm decide "il fait trop sombre"` (décision brute).

### Local avec Ollama (aucune donnée ne sort)

```toml
[llm]
enabled = true
provider = "ollama"           # http://localhost:11434/v1
model = "qwen3:8b"            # ou llama3.1, gemma3…
api_key_env = ""
```

`privacy.allow_cloud` peut rester `false` : les URL `localhost` sont toujours permises.

### Autres endpoints OpenAI-compatibles

`provider = "openai"` (`OPENAI_API_KEY`), `"openrouter"` (`OPENROUTER_API_KEY`), ou `"custom"` avec `base_url = "https://…/v1"` et `api_key`.

## Ce que le modèle reçoit

- Le **prompt système** : persona (nom, ton, verbosité, `personality`, `system_prompt_extra`), la consigne de réponse (parlée, courte, sans markdown), la liste des capacités avec leurs paramètres, les phrases des commandes personnalisées et les noms de sessions, puis le contexte : heure, fenêtre active (classe + titre), workspace, batterie, trois dernières actions du journal.
- L'**historique** des `history_turns` derniers échanges (en RAM, effacé au redémarrage).
- La **phrase** transcrite. Jamais l'audio.

Réponse attendue (décision) : `{"action": "<intention>", "slots": {…}, "say": "…"}`, `{"reply": "…"}` ou `{"ignore": true}`. Iris tolère les blocs ```json et le texte autour ; une réponse non JSON est prononcée telle quelle.

## Coût et latence

Une décision consomme ~1 000 tokens d'entrée (prompt système + contexte) et quelques dizaines en sortie. Avec `glm-5.3-flash` (0,15 $ / M tokens en entrée), cent phrases hors règles par jour coûtent ~0,5 $ par mois. Latence typique 1-3 s ; le widget Waybar affiche « réfléchit » pendant ce temps et Iris reste muette (pas de « hmm »).

## Limites actuelles

- Appel synchrone (pas de streaming de la réponse).
- L'historique ne survit pas au redémarrage (mémoire persistante : phase 3).
- Le client est testé contre des réponses simulées ; les identifiants de modèles proviennent de la documentation OpenCode (septembre 2026) et peuvent évoluer : `iris llm models` fait foi.
