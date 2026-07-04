"""Actions CU/desk exposées à l'agent vocal.

Un tool = une action réelle nommée explicitement (voir CLAUDE.md). Ces
fonctions sont appelées par le bridge en réponse au function calling de
Gemini Live ; leur signature (noms et types de paramètres) doit rester en
phase avec la FunctionDeclaration correspondante dans twilio_gemini_bridge.py.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("tools.gate")

BOARD_LOG_PATH = os.environ.get("BOARD_LOG_PATH", "board_events.jsonl")


def flag_blocked_at_gate(
    container_id: str,
    reason: str,
    amount_usd: float = 0,
    reference: str = "",
) -> dict:
    """Remonte un blocage gate au desk humain — ne paie et ne libère JAMAIS seul.

    Garde-fou n°1 de CLAUDE.md : toute dépense (détention, frais impayés)
    doit être validée par un humain avant qu'un worker CU n'exécute quoi que
    ce soit. Cette fonction se contente d'écrire l'événement pour le board et
    de le journaliser ; l'exécution réelle (paiement, libération) est un
    processus séparé, déclenché seulement après validation humaine.
    """
    event = {
        "type": "flag_blocked_at_gate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "container_id": container_id,
        "reason": reason,
        "amount_usd": amount_usd,
        "reference": reference,
        "status": "pending_human_validation",
    }
    logger.warning("GATE BLOCKED — validation humaine requise: %s", event)
    with open(BOARD_LOG_PATH, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"status": "pending_human_validation", "container_id": container_id}
