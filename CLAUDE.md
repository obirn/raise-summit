# CLAUDE.md

Contexte projet pour tout agent (Claude Code / Antigravity) travaillant dans ce repo.
Lis ce fichier en entier avant de modifier du code. Les règles de la section
**Garde-fous** ne sont jamais optionnelles.

---

## Ce que fait le projet

Agent qui **débloque les expéditions coincées** chez un transitaire (freight
forwarder). Un transitaire moyen gère ~400 expéditions/jour ; chaque conteneur
touche 3+ systèmes qui ne se parlent pas :

- **TMS** interne (vieux, sans API)
- **Portail douane** (login + écrans séparés)
- **Portail compagnie maritime** (encore un autre)
- + parfois un **4ᵉ système hyper-local** : le gate du terminal, sans API,
  invisible depuis les 3 autres.

Un conteneur se bloque sans que personne ne le voie : les sources se
contredisent (« prêt à expédier » / « documents manquants » / « libéré »).
Coût du blocage : **surestarie ~150 $/jour** + tournées camion gâchées.

L'agent : lit l'état réel éparpillé, **diagnostique la vraie cause** (savoir
*laquelle* des sources contradictoires dit vrai, et donc *où* agir), exécute la
correction de bout en bout, et mène le conteneur jusqu'à « libéré ».

## La valeur (ce n'est PAS « juste plus vite »)

Le nœud n'est pas la vitesse de saisie, c'est le **diagnostic multi-systèmes**.
Un humain met 20-40 min à démêler un conteneur bloqué ; un RPA scripté ne sait
pas diagnostiquer (il exécute une tâche connue) ; lire la doc ne suffit pas
(la doc ne dit pas *pourquoi ce conteneur-ci* est coincé — seul le croisement
de l'état réel le dit).

**Cas de référence — MSKU4471.** Les 3 systèmes disent tous « libéré / prêt »
et se trompent tous. Le camion part, le portique le refuse : détention impayée
de 340 $ qui n'existe QUE dans le système de gate du terminal. La seule source
de vérité à cet instant, c'est **la bouche du chauffeur, dans sa langue, debout
au portique**. L'agent prend l'appel, comprend, repose une question dans sa
langue pour obtenir la référence exacte, remonte au desk, exécute la libération
après validation humaine, et rappelle le chauffeur dans sa langue.

Les 4 capacités et pourquoi chacune est irremplaçable dans ce cas :

- **LT (aller-retour, pas traduction)** : conversation bidirectionnelle avec le
  chauffeur dans sa langue. Sans elle, pas de référence → pas d'action.
- **CU (Computer Use)** : agir sur des systèmes fermés sans API (facturation
  du portail maritime, paiement/libération).
- **Diagnostic** : identifier la source qui dit vrai parmi les contradictoires.
- **Antigravity** : tient l'état du conteneur sur tout le process, vérifie
  chaque étape, reprend par ID si ça casse (re-vérif le lendemain matin).

---

## Stack

| Brique | Techno | Rôle |
|---|---|---|
| Téléphonie | Twilio Programmable Voice + Media Streams | numéro appelable, audio bidirectionnel via `<Connect><Stream>` (WebSocket, μ-law 8 kHz base64) |
| Voix/langue | Gemini Live API — `gemini-3.1-flash-live-preview` | audio multilingue IN/OUT natif + raisonnement + function calling |
| Actions systèmes fermés | Computer Use | navigue les portails comme un humain |
| État / orchestration | Antigravity | board conteneurs, reprise par ID, re-vérif |

### Choix de modèle — NE PAS se tromper

- **Agent vocal** → `gemini-3.1-flash-live-preview`. C'est notre défaut : il
  comprend, relance, et appelle les tools. **C'est ce dont le cas MSKU4471 a
  besoin.**
- **Traduction pure** → `gemini-3.5-live-translate-preview` (+ `translation_config`).
  Ne fait QUE traduire, ne raisonne pas, n'appelle aucun tool. **Ne pas
  l'utiliser pour la boucle agent** — seulement pour un canal de relais passif.

---

## Structure du repo

```
.
├── CLAUDE.md                    # ce fichier
├── twilio_gemini_bridge.py      # pont Twilio <-> Gemini Live (audio + tools)
├── tools/                       # actions CU / desk exposées à l'agent
│   └── gate.py                  # flag_blocked_at_gate, etc.
├── cu/                          # workers Computer Use (portails sans API)
├── board/                       # intégration Antigravity (état conteneur)
└── .env                         # secrets (jamais commité)
```

## Commandes

```bash
# Install (Python 3.13 : audioop retiré de la stdlib, d'où audioop-lts)
pip install "google-genai>=1.0" websockets fastapi uvicorn audioop-lts

# Lancer le serveur du bridge
python twilio_gemini_bridge.py           # écoute sur :8080

# Exposer en dev + brancher le numéro Twilio
ngrok http 8080
# puis pointer la Voice URL du numéro Twilio -> https://<ngrok>/voice
# et remplacer TON_HOST par <ngrok> dans le TwiML (wss://<ngrok>/ws)
```

## Variables d'environnement

- `GEMINI_API_KEY` — clé Gemini. **Doit avoir des restrictions d'API explicites**
  (depuis le 19/06/2026, une clé non restreinte renvoie une erreur).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — compte Twilio.

---

## Garde-fous (NON négociables)

1. **L'agent ne paie JAMAIS tout seul.** Toute dépense (ex : détention impayée)
   est remontée au desk via `flag_blocked_at_gate` et validée par un humain
   avant que le worker CU exécute le paiement. C'est ce qui nous protège de
   l'objection responsabilité — ne jamais court-circuiter cette étape.
2. **Toujours parler dans la langue du chauffeur.** Détection auto ; réponses
   courtes et concrètes. Le « aller-retour » (relance pour obtenir la référence)
   est le cœur de la valeur — ne jamais le remplacer par un sous-titre passif.
3. **Ne jamais faire confiance à une seule source.** Le diagnostic vient du
   *croisement* des systèmes ; un statut isolé (« libéré ») peut mentir.
4. **Toujours mettre à jour le board Antigravity** avec l'ID conteneur et
   planifier une re-vérif — c'est ce qui permet de reprendre si ça casse.

## Pièges connus (déjà rencontrés)

- **Transcodage audio = source d'erreur n°1.** Twilio = μ-law 8 kHz ;
  Gemini = PCM 16 bits (16 kHz in, 24 kHz out). Les `audioop.ratecv` du bridge
  font la conversion. Sur Python 3.13 il FAUT `audioop-lts`.
- **Stream bidirectionnel** : un seul `<Connect><Stream>` par appel.
- **Sessions Gemini Live** : expiration ~15 min avec message `GoAway` (~30 s
  avant). OK pour un appel court ; prévoir une reconnexion pour les démos longues.

## Conventions

- Un tool = une action réelle nommée explicitement (`flag_blocked_at_gate`),
  jamais une action générique floue.
- Logguer systématiquement `input_transcription` (chauffeur) et
  `output_transcription` (agent) pour le board et le debug.
- Async partout (bridge Twilio ↔ Gemini) : ne pas bloquer la boucle.
