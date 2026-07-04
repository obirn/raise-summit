"""Pont Twilio Programmable Voice <-> Gemini Live.

Reçoit un appel via Twilio Media Streams (<Connect><Stream>, WebSocket,
mu-law 8 kHz base64), transcode l'audio vers/depuis le format attendu par
Gemini Live (PCM16 16 kHz en entrée, PCM16 24 kHz en sortie), et relaie le
function calling vers les tools de tools/.

Voir CLAUDE.md pour les garde-fous (ne jamais payer seul, toujours
diagnostiquer avant d'agir) et les pièges connus (transcodage audio,
sessions Gemini Live limitées à ~15 min).
"""

import asyncio
import audioop
import base64
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from google import genai
from google.genai import types

from tools.gate import flag_blocked_at_gate

load_dotenv()  # charge .env (secrets Gemini/Twilio) — cf. CLAUDE.md

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bridge")

GEMINI_MODEL = "gemini-3.1-flash-live-preview"

TWILIO_RATE = 8000       # mu-law 8 kHz, tel que reçu/attendu par Twilio Media Streams
GEMINI_IN_RATE = 16000   # PCM16 attendu en entrée par Gemini Live
GEMINI_OUT_RATE = 24000  # PCM16 produit en sortie par Gemini Live

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
app = FastAPI()

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
    return impl(**args)


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

    while call_active:
        try:
            async with client.aio.live.connect(
                model=GEMINI_MODEL, config=_live_config(resumption_handle)
            ) as session:
                logger.info(
                    "Gemini Live connecté callSid=%s (reprise=%s)",
                    call_sid,
                    bool(resumption_handle),
                )
                call_active, resumption_handle = await _run_session(
                    websocket, session, stream_sid, call_sid, resample_state, resumption_handle
                )
        except WebSocketDisconnect:
            logger.info("Twilio websocket déconnecté callSid=%s", call_sid)
            call_active = False

    logger.info("Call terminé callSid=%s", call_sid)


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
        async for raw in _iter_twilio_messages(websocket):
            msg = json.loads(raw)
            event = msg.get("event")
            if event == "media":
                ulaw = base64.b64decode(msg["media"]["payload"])
                pcm_8k = audioop.ulaw2lin(ulaw, 2)
                pcm_16k, resample_state["in"] = audioop.ratecv(
                    pcm_8k, 2, 1, TWILIO_RATE, GEMINI_IN_RATE, resample_state["in"]
                )
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm_16k, mime_type=f"audio/pcm;rate={GEMINI_IN_RATE}")
                )
            elif event == "stop":
                logger.info("Twilio stop callSid=%s", call_sid)
                call_active = False
                return
        call_active = False

    async def pump_gemini_to_twilio():
        nonlocal call_active, go_away, resumption_handle
        async for response in session.receive():
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
                    logger.info("[chauffeur] %s", server_content.input_transcription.text)
                if server_content.output_transcription and server_content.output_transcription.text:
                    logger.info("[agent] %s", server_content.output_transcription.text)

            if response.tool_call:
                for fc in response.tool_call.function_calls:
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
        call_active = False

    tasks = [asyncio.create_task(pump_twilio_to_gemini()), asyncio.create_task(pump_gemini_to_twilio())]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        exc = task.exception()
        if exc is not None:
            raise exc

    return (call_active or go_away), resumption_handle


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
