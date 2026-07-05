"""Pont Twilio Programmable Voice <-> Gemini Live (Live Translate).

Reçoit un appel via Twilio Media Streams (<Connect><Stream>, WebSocket,
mu-law 8 kHz base64), transcode l'audio vers/depuis le format attendu par
Gemini Live (PCM16 16 kHz en entrée, PCM16 24 kHz en sortie), et relaie le
function calling vers agent/voice/gate.py.

Chemin *push* de la voix (§9) : sur `flag_blocked_at_gate`, le bridge notifie
l'orchestrateur (`/events/field-truth`) qui rejoue exactement le flux de la
démo scriptée (lecture terminal ciblée -> ligne surfacée -> gate humain). Il
pousse aussi `call_started` et la transcription live vers le Site Office.

DEMO-ONLY : téléphonie réelle = ngrok + numéro Twilio. Testé au téléphone.
Voir CLAUDE.md pour les garde-fous et les pièges (transcodage, sessions
Gemini Live ~15 min).
"""

import asyncio
import audioop
import base64
import json
import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from google import genai
from google.genai import types

from .gate import flag_blocked_at_gate

load_dotenv()  # charge .env (secrets Gemini/Twilio) — cf. CLAUDE.md

# Logging robuste : basicConfig est un no-op sous le CLI uvicorn (uvicorn possède
# déjà des handlers), donc on attache explicitement un handler au logger "bridge"
# pour être sûr de voir les logs quel que soit le mode de lancement.
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()  # LOG_LEVEL=DEBUG pour tout tracer
logging.basicConfig(level=_LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bridge")
logger.setLevel(_LOG_LEVEL)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)
logger.propagate = False  # évite les doublons via le root/uvicorn

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
ORCH_URL = os.environ.get("ORCH_URL", "http://localhost:5000")  # orchestrateur (contrat interne)

TWILIO_RATE = 8000       # mu-law 8 kHz, tel que reçu/attendu par Twilio Media Streams
GEMINI_IN_RATE = 16000   # PCM16 attendu en entrée par Gemini Live
GEMINI_OUT_RATE = 24000  # PCM16 produit en sortie par Gemini Live

_client: genai.Client | None = None
app = FastAPI()


def get_client() -> genai.Client:
    """Client Gemini paresseux : le module s'importe sans GEMINI_API_KEY
    (tests hors-ligne) ; la clé n'est requise qu'à la première connexion Live."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


async def _notify(path: str, payload: dict) -> None:
    """Notifie l'orchestrateur (fire-and-forget). Un orchestrateur indisponible
    ne doit JAMAIS interrompre l'appel : on avale toute erreur."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as http:
            await http.post(f"{ORCH_URL}{path}", json=payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify %s a échoué (orchestrateur down ?): %s", path, exc)


def _notify_bg(path: str, payload: dict) -> None:
    asyncio.create_task(_notify(path, payload))


SYSTEM_INSTRUCTION = """
Tu es l'agent qui débloque les expéditions coincées pour un transitaire
(freight forwarder). Tu es au téléphone avec un chauffeur, souvent debout au
portique d'un terminal.

- Réponds toujours dans la langue du chauffeur (détection automatique),
  en phrases courtes et concrètes.
- Ne fais jamais confiance à un seul statut ("libéré", "prêt à expédier") :
  les systèmes se contredisent. Pose des questions pour obtenir la référence
  exacte affichée devant le chauffeur (numéro de facture, ticket, ordre de
  libération) avant de conclure quoi que ce soit.
- Si le blocage implique une dépense (détention, frais impayés, amende),
  tu ne payes et ne libères JAMAIS toi-même. Relance pour obtenir la
  référence exacte, puis appelle l'outil flag_blocked_at_gate pour remonter
  le cas au desk humain, qui validera avant toute action.
"""

TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="flag_blocked_at_gate",
                description=(
                    "Remonte au desk humain un blocage constaté au gate du "
                    "terminal (détention, frais impayés, document manquant). "
                    "Ne déclenche aucun paiement ni libération : l'action réelle "
                    "attend une validation humaine."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "container_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID du conteneur, ex: MSKU4471",
                        ),
                        "reason": types.Schema(
                            type=types.Type.STRING,
                            description="Raison du blocage rapportée par le chauffeur",
                        ),
                        "amount_usd": types.Schema(
                            type=types.Type.NUMBER,
                            description="Montant en USD si connu, sinon 0",
                        ),
                        "reference": types.Schema(
                            type=types.Type.STRING,
                            description="Référence exacte obtenue du chauffeur (facture, ticket...)",
                        ),
                    },
                    required=["container_id", "reason"],
                ),
            )
        ]
    )
]

TOOL_IMPLS = {"flag_blocked_at_gate": flag_blocked_at_gate}


def _dispatch_tool(name: str, args: dict) -> dict:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        logger.error("Tool inconnu appelé par le modèle: %s", name)
        return {"error": f"unknown tool {name}"}
    logger.info("Tool call %s(%s)", name, args)
    result = impl(**args)
    # Chemin push : la référence obtenue du chauffeur rejoint le board + le
    # Site Office. Le gate humain reste souverain (paiement seulement après
    # /approve dans l'orchestrateur).
    container_id = args.get("container_id")
    if container_id:
        _notify_bg("/events/field-truth", {
            "container_id": container_id,
            "blocker_type": "unpaid_detention",
            "reference": args.get("reference", ""),
            "lang": "es",
            "raw_transcript": args.get("reason", ""),
        })
    return result


def _live_config(resumption_handle: str | None = None) -> types.LiveConnectConfig:
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=SYSTEM_INSTRUCTION,
        tools=TOOLS,
        session_resumption=types.SessionResumptionConfig(handle=resumption_handle),
    )


@app.post("/voice")
async def voice(request: Request) -> Response:
    """TwiML de réponse à l'appel entrant : ouvre le stream audio bidirectionnel."""
    host = request.headers["host"]
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="wss://{host}/ws" />'
        "</Connect></Response>"
    )
    return Response(content=twiml, media_type="text/xml")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await _bridge_call(websocket)


async def _iter_twilio_messages(websocket: WebSocket):
    try:
        while True:
            yield await websocket.receive_text()
    except WebSocketDisconnect:
        return


async def _bridge_call(websocket: WebSocket) -> None:
    stream_sid = None
    call_sid = None

    async for raw in _iter_twilio_messages(websocket):
        msg = json.loads(raw)
        event = msg.get("event")
        if event == "start":
            stream_sid = msg["start"]["streamSid"]
            call_sid = msg["start"].get("callSid")
            logger.info("Call started callSid=%s streamSid=%s", call_sid, stream_sid)
            _notify_bg("/events/call-started", {})  # "driver on the line" (id encore inconnu)
            break
        if event == "stop":
            return
        # ignore "connected" et tout autre event préliminaire

    if stream_sid is None:
        return

    # état de ré-échantillonnage conservé sur toute la durée de l'appel pour
    # éviter les artefacts (clics) entre deux chunks audio consécutifs.
    resample_state = {"in": None, "out": None}
    resumption_handle = None
    call_active = True
    session_i = 0

    while call_active:
        session_i += 1
        try:
            logger.info("Ouverture session Gemini #%d callSid=%s (reprise=%s)",
                        session_i, call_sid, bool(resumption_handle))
            async with get_client().aio.live.connect(
                model=GEMINI_MODEL, config=_live_config(resumption_handle)
            ) as session:
                logger.info("Gemini Live connecté callSid=%s (session #%d)", call_sid, session_i)
                call_active, resumption_handle = await _run_session(
                    websocket, session, stream_sid, call_sid, resample_state, resumption_handle
                )
                logger.info("Retour _run_session #%d callSid=%s -> call_active=%s (reprise=%s)",
                            session_i, call_sid, call_active, bool(resumption_handle))
        except WebSocketDisconnect:
            logger.info("Twilio websocket déconnecté callSid=%s (session #%d)", call_sid, session_i)
            call_active = False
        except Exception:  # noqa: BLE001 — on veut voir POURQUOI la session meurt
            logger.exception("Erreur inattendue dans la session Gemini callSid=%s (session #%d)",
                             call_sid, session_i)
            call_active = False

    logger.info("Call terminé callSid=%s (après %d session(s) Gemini)", call_sid, session_i)


async def _run_session(websocket, session, stream_sid, call_sid, resample_state, resumption_handle):
    """Fait tourner un aller-retour Twilio<->Gemini jusqu'à fin d'appel ou GoAway.

    Retourne (call_active, resumption_handle) pour permettre à _bridge_call de
    reconnecter une nouvelle session Gemini Live sans interrompre l'appel
    Twilio (les sessions Live expirent après ~15 min, cf. pièges connus).
    """
    call_active = True
    go_away = False

    async def pump_twilio_to_gemini():
        nonlocal call_active
        media_frames = 0
        async for raw in _iter_twilio_messages(websocket):
            msg = json.loads(raw)
            event = msg.get("event")
            if event == "media":
                media_frames += 1
                if media_frames % 250 == 0:
                    logger.debug("Twilio media: %d frames reçus (callSid=%s)", media_frames, call_sid)
                ulaw = base64.b64decode(msg["media"]["payload"])
                pcm_8k = audioop.ulaw2lin(ulaw, 2)
                pcm_16k, resample_state["in"] = audioop.ratecv(
                    pcm_8k, 2, 1, TWILIO_RATE, GEMINI_IN_RATE, resample_state["in"]
                )
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm_16k, mime_type=f"audio/pcm;rate={GEMINI_IN_RATE}")
                )
            elif event == "stop":
                logger.info("[twilio->gemini] STOP reçu (appelant a raccroché) callSid=%s après %d frames",
                            call_sid, media_frames)
                call_active = False
                return
            else:
                logger.info("[twilio->gemini] event non-media '%s' callSid=%s", event, call_sid)
        # sortie sans 'stop' = flux fermé côté Twilio
        logger.info("[twilio->gemini] flux Twilio terminé SANS 'stop' callSid=%s (%d frames)",
                    call_sid, media_frames)
        call_active = False

    async def pump_gemini_to_twilio():
        nonlocal call_active, go_away, resumption_handle
        # `session.receive()` se termine à CHAQUE `turn_complete` (fin de tour de
        # l'agent), pas à la fin de l'appel. On reboucle donc pour ré-écouter le
        # tour suivant (la réponse du chauffeur). Sinon l'appel raccrocherait
        # juste après la première question de l'agent. La fin réelle de l'appel
        # vient de Twilio ("stop"/déconnexion, géré par l'autre pump) ou d'un
        # GoAway (reconnexion par _bridge_call).
        turn = 0
        while call_active and not go_away:
            turn += 1
            saw_response = False
            async for response in session.receive():
                saw_response = True
                if response.go_away:
                    logger.warning(
                        "Gemini GoAway callSid=%s time_left=%s — reconnexion",
                        call_sid,
                        response.go_away.time_left,
                    )
                    go_away = True
                    return

                if response.session_resumption_update and response.session_resumption_update.resumable:
                    resumption_handle = response.session_resumption_update.new_handle

                server_content = response.server_content
                if server_content:
                    if server_content.interrupted:
                        # le chauffeur a coupé la parole de l'agent : on vide le
                        # buffer audio déjà envoyé à Twilio pour éviter le chevauchement.
                        await websocket.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))
                    if server_content.input_transcription and server_content.input_transcription.text:
                        text = server_content.input_transcription.text
                        logger.info("[chauffeur] %s", text)
                        _notify_bg("/events/transcript", {"speaker": "driver", "text": text})
                    if server_content.output_transcription and server_content.output_transcription.text:
                        text = server_content.output_transcription.text
                        logger.info("[agent] %s", text)
                        _notify_bg("/events/transcript", {"speaker": "agent", "text": text})

                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        logger.info("[gemini->twilio] tool_call tour=%d %s(%s) callSid=%s",
                                    turn, fc.name, fc.args, call_sid)
                        result = _dispatch_tool(fc.name, fc.args or {})
                        await session.send_tool_response(
                            function_responses=types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                        )

                audio = response.data
                if audio:
                    pcm_8k, resample_state["out"] = audioop.ratecv(
                        audio, 2, 1, GEMINI_OUT_RATE, TWILIO_RATE, resample_state["out"]
                    )
                    ulaw = audioop.lin2ulaw(pcm_8k, 2)
                    payload = base64.b64encode(ulaw).decode("ascii")
                    await websocket.send_text(
                        json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": payload}})
                    )
            # fin d'un tour (turn_complete) -> on reboucle sur receive() pour
            # écouter la réponse du chauffeur, l'appel reste ouvert. Si receive()
            # n'a rien renvoyé, la session Gemini est fermée -> on sort (évite un
            # spin ; _bridge_call reconnecte si l'appel Twilio tient toujours).
            logger.info("[gemini->twilio] fin tour=%d (saw_response=%s call_active=%s go_away=%s) callSid=%s",
                        turn, saw_response, call_active, go_away, call_sid)
            if not saw_response:
                logger.warning("[gemini->twilio] receive() VIDE au tour=%d -> session Gemini fermée "
                               "par le serveur callSid=%s", turn, call_sid)
                break
        logger.info("[gemini->twilio] sortie de boucle callSid=%s (call_active=%s go_away=%s après %d tours)",
                    call_sid, call_active, go_away, turn)
        call_active = False

    tasks = {
        "twilio->gemini": asyncio.create_task(pump_twilio_to_gemini()),
        "gemini->twilio": asyncio.create_task(pump_gemini_to_twilio()),
    }
    names = {task: name for name, task in tasks.items()}
    done, pending = await asyncio.wait(tasks.values(), return_when=asyncio.FIRST_COMPLETED)

    # Quel pump a terminé en premier, et pourquoi ? (c'est LA raison de la fermeture)
    disconnect: WebSocketDisconnect | None = None
    had_error = False
    for task in done:
        name = names[task]
        exc = task.exception()
        if exc is None:
            logger.info("[session] pump '%s' terminé normalement callSid=%s", name, call_sid)
        elif isinstance(exc, WebSocketDisconnect):
            logger.info("[session] pump '%s' -> WebSocketDisconnect callSid=%s", name, call_sid)
            disconnect = exc
        else:
            logger.error("[session] pump '%s' a levé %s callSid=%s — TRACEBACK ci-dessous",
                         name, type(exc).__name__, call_sid, exc_info=exc)
            had_error = True

    for task in pending:
        task.cancel()
        try:
            await task
        except BaseException:  # noqa: BLE001 — annulation attendue
            pass

    if disconnect is not None:
        raise disconnect
    if had_error:
        logger.info("[session] fin sur erreur -> on termine l'appel callSid=%s", call_sid)
        return False, resumption_handle

    logger.info("[session] terminée callSid=%s -> call_active=%s go_away=%s (reconnexion=%s)",
                call_sid, call_active, go_away, bool(call_active or go_away))
    return (call_active or go_away), resumption_handle


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
