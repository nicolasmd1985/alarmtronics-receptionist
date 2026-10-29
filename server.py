#!/usr/bin/env python3
"""
server.py - Real-Time AI Inbound Voice Receptionist for Alarmtronics
Powered by Google Gemini Live API (gemini-3.1-flash-live-preview)
Ultra-low-latency bidirectional WebSockets for Telnyx TeXML Media Streams.

Stack:
- Telephony Carrier: Telnyx TeXML Bidirectional WebSockets (PCMU 8000Hz)
- Real-Time Voice AI: Google Gemini Live API (Multimodal Speech-to-Speech)
- Persona & Voice: Alarmtronics Dispatcher (Voice: Aoede)
- Ingress: Cloudflare Tunnel / Public HTTPS & WSS
- Storage: SQLite (data/leads.db) + JSON (data/leads.json)
"""

import os
import sys
import json
import time
import base64
import asyncio
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import numpy as np
import scipy.signal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AlarmtronicsReceptionist")

# Global Paths & Config
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "leads.db"
JSON_LOG_PATH = DATA_DIR / "leads.json"

# Core Settings
COMPANY_NAME = os.getenv("COMPANY_NAME", "Alarmtronics")
OWNER_NAME = os.getenv("OWNER_NAME", "Alarmtronics")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Aoede")
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "").strip()
TELNYX_PHONE_NUMBER = os.getenv("TELNYX_PHONE_NUMBER", "+14073050475")

# Initialize GenAI Client
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"Google GenAI Client initialized successfully for Live model: {GEMINI_LIVE_MODEL}")
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}")
else:
    logger.warning("GEMINI_API_KEY not configured. Calls will not be able to connect to Live API.")

# ==============================================================================
# 1. High-Performance ITU-T G.711 u-law Codec & Resampling Engine
# ==============================================================================

def _generate_ulaw_tables():
    """Generates O(1) lookup tables for G.711 mu-law decoding and encoding."""
    decode_table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        u = ~i & 0xFF
        sign = u & 0x80
        exponent = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        decode_table[i] = -sample if not sign else sample

    encode_table = np.zeros(65536, dtype=np.uint8)
    BIAS = 0x84
    CLIP = 32635
    for s in range(-32768, 32768):
        sample = s
        sign = 0x80 if sample < 0 else 0
        if sample < 0:
            sample = -sample
        if sample > CLIP:
            sample = CLIP
        sample += BIAS
        exponent = 7
        for exp in range(7):
            if sample <= (0xFF << (exp + 3)):
                exponent = exp
                break
        mantissa = (sample >> (exponent + 3)) & 0x0F
        encode_table[s + 32768] = (~(sign | (exponent << 4) | mantissa)) & 0xFF

    return decode_table, encode_table

ULAW_DECODE_LUT, ULAW_ENCODE_LUT = _generate_ulaw_tables()

def ulaw_to_pcm16_8k(ulaw_bytes: bytes) -> np.ndarray:
    """Decode raw G.711 mu-law 8kHz bytes into signed 16-bit PCM numpy array."""
    indices = np.frombuffer(ulaw_bytes, dtype=np.uint8)
    return ULAW_DECODE_LUT[indices]

def pcm16_to_ulaw(pcm16_samples: np.ndarray) -> bytes:
    """Encode signed 16-bit PCM numpy array into G.711 mu-law bytes."""
    indices = (pcm16_samples.astype(np.int32) + 32768).astype(np.uint16)
    return ULAW_ENCODE_LUT[indices].tobytes()

def resample_8k_to_16k(pcm16_8k: np.ndarray) -> np.ndarray:
    """Upsample 8kHz PCM16 to 16kHz PCM16 for Gemini Live input."""
    resampled = scipy.signal.resample_poly(pcm16_8k.astype(np.float32), 2, 1)
    return np.clip(resampled, -32768, 32767).astype(np.int16)

def resample_24k_to_8k(pcm16_24k: np.ndarray) -> np.ndarray:
    """Downsample Gemini 24kHz PCM16 to 8000Hz PCM16 (exact 3:1 decimation)."""
    resampled = scipy.signal.resample_poly(pcm16_24k.astype(np.float32), 1, 3)
    return np.clip(resampled, -32768, 32767).astype(np.int16)

# ==============================================================================
# 2. Conversational Persona & System Instructions
# ==============================================================================

SYSTEM_PROMPT = f"""You are the professional and courteous voice receptionist for {COMPANY_NAME}, specializing in commercial and residential Fire Alarms and Burglar/Intrusion Security Alarms.

Your primary goal is to collect 4 specific pieces of information from the caller, ONE STEP AT A TIME:
1. Caller's Full Name
2. Alarm Problem / Issue (e.g., beeping keypad, fire trouble alert, false alarm, sensor fault, battery issue)
3. Property Service Address (where the alarm system is located)
4. Callback Phone Number

Conversational Rules:
- Speak ONLY in plain English at all times.
- Keep every answer natural, polite, and strictly under 20 words per response.
- Ask for ONLY ONE missing item at a time. NEVER ask multiple questions in a single response.
- Progression steps:
  - Step 1: Once you know the Name and Issue -> ask for Service Address: "Got it, [Name]. What is the address of the property where the alarm is located?"
  - Step 2: Once you have the Address -> ask for Callback Phone Number: "Thank you. And what is your best callback phone number?"
  - Step 3: If the caller provides their phone number first, acknowledge it and ask for the Service Address: "Got your number, thank you. What is the property service address?"
  - Step 4: Once you have Name, Issue, Address, and Phone Number, conclude the call warmly:
    "Thank you, [Name]. A technician has been dispatched for [Address] and will call you shortly. Have a great day!"
- Emergency Safety Rule: If the caller reports an active fire, smoke, or physical danger, urge them immediately: "If you are in physical danger or there is an active fire, please hang up and call 911 immediately."
- Never repeat questions already answered. Never repeat the initial greeting.
"""

class LeadExtractionSchema(BaseModel):
    caller_name: Optional[str] = Field(None, description="Full name of caller")
    caller_phone: Optional[str] = Field(None, description="Callback phone number")
    service_address: Optional[str] = Field(None, description="Street address or property location of the alarm system")
    system_type: str = Field("unknown", description="fire_alarm, burglar_alarm, cctv_security, or other")
    issue_description: Optional[str] = Field(None, description="Detailed description of the alarm problem, beeping, or failure")
    urgency: str = Field("normal", description="emergency, urgent, or normal")
    summary: str = Field(..., description="1-2 sentence executive briefing for the on-call technician")

async def extract_structured_lead(transcript_text: str, caller_from: str) -> LeadExtractionSchema:
    """Parses full call transcript into a validated Pydantic Lead Schema for Alarmtronics."""
    fallback_lead = LeadExtractionSchema(
        caller_name=None,
        caller_phone=caller_from or None,
        service_address=None,
        system_type="unknown",
        issue_description=None,
        urgency="normal",
        summary="Alarm service call completed.",
    )

    if not gemini_client or not transcript_text.strip():
        return fallback_lead

    try:
        prompt = (
            f"Analyze this completed customer service telephone call for Alarmtronics (fire and burglar alarm systems) and extract the service dispatch ticket details.\n"
            f"Caller ID phone number detected by carrier: {caller_from}\n\n"
            f"--- TRANSCRIPT ---\n{transcript_text}\n--- END TRANSCRIPT ---"
        )

        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-flash-lite-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LeadExtractionSchema,
                temperature=0.1,
            ),
        )

        if response and response.text:
            data = json.loads(response.text)
            lead = LeadExtractionSchema(**data)
            if not lead.caller_phone and caller_from:
                lead.caller_phone = caller_from
            return lead
    except Exception as e:
        logger.error(f"Structured lead extraction failed: {e}")

    return fallback_lead

# ==============================================================================
# 3. Persistence Layer (SQLite + JSON)
# ==============================================================================

def init_database():
    """Initializes local SQLite database schema for lead persistence."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                call_sid TEXT,
                caller_from_number TEXT,
                caller_name TEXT,
                caller_phone TEXT,
                service_address TEXT,
                system_type TEXT,
                issue_description TEXT,
                reason_for_call TEXT,
                urgency TEXT,
                language TEXT,
                summary TEXT,
                transcript_json TEXT,
                duration_seconds REAL
            )
        """)
        conn.commit()
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        for col in ["service_address", "system_type", "issue_description"]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} TEXT")
        conn.commit()
    logger.info(f"Database initialized at {DB_PATH}")

def save_lead_record(call_sid: str, caller_from: str, lead: LeadExtractionSchema, transcript: List[Dict[str, str]], duration: float):
    """Saves call records to SQLite and appends to data/leads.json."""
    transcript_str = json.dumps(transcript, ensure_ascii=False)
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO leads (
                    call_sid, caller_from_number, caller_name, caller_phone,
                    service_address, system_type, issue_description, reason_for_call,
                    urgency, language, summary, transcript_json, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_sid, caller_from, lead.caller_name, lead.caller_phone,
                lead.service_address, lead.system_type, lead.issue_description, lead.issue_description,
                lead.urgency, "en", lead.summary, transcript_str, duration
            ))
            conn.commit()
        logger.info(f"Service ticket saved to SQLite for Call SID: {call_sid}")
    except Exception as e:
        logger.error(f"SQLite save error: {e}")

    try:
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_sid": call_sid,
            "caller_from": caller_from,
            "lead": lead.model_dump(),
            "duration_seconds": round(duration, 2),
            "transcript": transcript,
        }
        leads_list = []
        if JSON_LOG_PATH.exists():
            try:
                with open(JSON_LOG_PATH, "r", encoding="utf-8") as f:
                    leads_list = json.load(f)
            except Exception:
                leads_list = []
        leads_list.append(record)
        with open(JSON_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(leads_list, f, indent=2, ensure_ascii=False)
        logger.info(f"Lead appended to {JSON_LOG_PATH}")
    except Exception as e:
        logger.error(f"JSON save error: {e}")

# ==============================================================================
# 4. FastAPI Application Lifecycle & Endpoints
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield
    logger.info("Shutting down Alarmtronics Voice Receptionist services...")

app = FastAPI(
    title="Alarmtronics AI Voice Receptionist",
    description="Live Multimodal Voice Telephony Dispatcher for Alarmtronics powered by Telnyx and Google Gemini Live API.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def root_dashboard(request: Request):
    """Provides a web dashboard displaying server status and configuration."""
    host = PUBLIC_DOMAIN or request.headers.get("host") or "localhost:8000"
    scheme = "https" if "trycloudflare.com" in host or "voz." in host else request.url.scheme
    ws_scheme = "wss" if scheme == "https" else "ws"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Alarmtronics AI Voice Receptionist</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b1120; color: #f8fafc; margin: 0; padding: 2rem; }}
            .card {{ background: #1e293b; border-radius: 12px; padding: 1.75rem; max-width: 820px; margin: 0 auto; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); border: 1px solid #334155; }}
            h1 {{ color: #38bdf8; margin-top: 0; font-size: 1.6rem; }}
            .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; background: #10b981; color: white; }}
            .code-box {{ background: #030712; padding: 1rem; border-radius: 8px; font-family: monospace; overflow-x: auto; margin: 1rem 0; border: 1px solid #1e293b; color: #34d399; font-size: 0.9rem; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.95rem; }}
            td, th {{ padding: 0.6rem; text-align: left; border-bottom: 1px solid #334155; }}
            a {{ color: #38bdf8; text-decoration: none; font-weight: 600; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Alarmtronics Dispatch Telephony <span class="badge">LIVE MULTIMODAL</span></h1>
            <p>Carrier Phone Number: <strong>{TELNYX_PHONE_NUMBER}</strong> (Telnyx)</p>
            <p>Company: <strong>{COMPANY_NAME}</strong> (Fire & Intrusion Alarms)</p>
            <p>Engine: <strong>Google Gemini Live API ({GEMINI_LIVE_MODEL})</strong></p>
            <p>Voice Persona: <strong>{GEMINI_VOICE} (Neural Conversational Voice)</strong></p>
            
            <h3>Telnyx TeXML Webhook Configuration</h3>
            <div class="code-box">
                Webhook URL: {scheme}://{host}/incoming-call<br>
                HTTP Method: POST<br>
                Media Stream URL: {ws_scheme}://{host}/media-stream
            </div>

            <h3>Real-Time Architecture Status</h3>
            <table>
                <tr><th>Component</th><th>Technology</th><th>Status</th></tr>
                <tr><td>Telephony Transport</td><td>Telnyx TeXML Bi-directional RTP (PCMU 8000Hz)</td><td>CONNECTED</td></tr>
                <tr><td>Voice AI Engine</td><td>Gemini Live API (Direct Audio Streaming)</td><td>READY</td></tr>
                <tr><td>Interruption (Barge-In)</td><td>Native Multimodal VAD & Instant Clear Buffer</td><td>ACTIVE</td></tr>
                <tr><td>Persistence</td><td>SQLite ({DB_PATH.name}) + JSON</td><td>SYNCED</td></tr>
            </table>

            <p style="margin-top: 1.5rem;"><a href="/leads" target="_blank">&rarr; View Captured Service Tickets (JSON API)</a></p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker & monitoring."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "engine": "gemini-live-multimodal",
        "live_model": GEMINI_LIVE_MODEL,
        "voice": GEMINI_VOICE,
        "gemini_active": gemini_client is not None,
    }

@app.get("/leads")
async def list_leads():
    """Returns captured leads from SQLite."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY timestamp DESC LIMIT 50")
        rows = [dict(row) for row in cursor.fetchall()]
        for r in rows:
            if r.get("transcript_json"):
                try:
                    r["transcript"] = json.loads(r["transcript_json"])
                except Exception:
                    pass
        return {"count": len(rows), "leads": rows}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call_webhook(request: Request):
    """Telnyx TeXML Inbound Webhook returning bidirectional media stream XML."""
    caller_from = "+1-Unknown"
    call_sid = "CALL_" + str(int(time.time()))
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            caller_from = body.get("data", {}).get("payload", {}).get("from", caller_from)
            call_sid = body.get("data", {}).get("payload", {}).get("call_control_id", call_sid)
        else:
            form = await request.form()
            caller_from = form.get("From", caller_from)
            call_sid = form.get("CallSid", form.get("call_control_id", call_sid))
    except Exception as e:
        logger.warning(f"Could not parse incoming call body: {e}")

    host = PUBLIC_DOMAIN or request.headers.get("host") or "localhost:8000"
    ws_scheme = "wss" if "trycloudflare.com" in host or "voz." in host or request.url.scheme == "https" else "ws"
    stream_url = f"{ws_scheme}://{host}/media-stream"

    logger.info(f"[INCOMING CALL] SID: {call_sid} | From: {caller_from} | Dispatching TeXML Stream to: {stream_url}")

    texml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" bidirectionalMode="rtp" bidirectionalCodec="PCMU">
            <Parameter name="caller" value="{caller_from}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
</Response>
"""
    return Response(content=texml_response.strip(), media_type="application/xml")

# ==============================================================================
# 5. Full-Duplex Bidirectional WebSocket Gateway (Telnyx <-> Gemini Live)
# ==============================================================================

GREETING_PATH = DATA_DIR / "greeting.ulaw"
if not GREETING_PATH.exists():
    fallback_greeting = BASE_DIR / "greeting.ulaw"
    if fallback_greeting.exists():
        GREETING_PATH = fallback_greeting

GREETING_ULAW = GREETING_PATH.read_bytes() if GREETING_PATH.exists() else b""
OPENING_GREETING_TEXT = (
    "Thank you for calling Alarmtronics. I am your virtual receptionist. "
    "Could you please provide your name and tell me what issue you are experiencing with your alarm system today?"
)

class CallSession:
    def __init__(self, stream_id: str, call_sid: str, caller_phone: str, websocket: WebSocket):
        self.stream_id = stream_id
        self.call_sid = call_sid
        self.caller_phone = caller_phone
        self.websocket = websocket
        self.start_time = time.time()
        self.is_closing = False
        self.greeting_active = True
        self.assistant_speaking = False
        self.audio_out_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.inbound_audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.dialogue_history: List[Dict[str, str]] = []
        self.current_user_text: List[str] = []
        self.current_model_text: List[str] = []

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("[WEBSOCKET] Client connected.")

    session: Optional[CallSession] = None
    if not gemini_client:
        logger.error("GenAI client not initialized. Cannot service call.")
        await websocket.close()
        return

    # Task A: Dedicated sender loop that paces 20ms frames to Telnyx
    async def audio_sender_loop(s: CallSession):
        chunk_size = 160  # 20ms of 8kHz PCMU
        try:
            while not s.is_closing:
                frame = await s.audio_out_queue.get()
                if frame is None or s.is_closing:
                    break

                for i in range(0, len(frame), chunk_size):
                    if s.is_closing:
                        break
                    chunk = frame[i : i + chunk_size]
                    if len(chunk) < chunk_size:
                        chunk = chunk.ljust(chunk_size, b"\xff")

                    payload = base64.b64encode(chunk).decode("ascii")
                    msg = {
                        "event": "media",
                        "stream_id": s.stream_id,
                        "streamSid": s.stream_id,
                        "media": {"payload": payload},
                    }
                    try:
                        await websocket.send_text(json.dumps(msg))
                    except Exception:
                        break
                    await asyncio.sleep(0.019)  # 20ms pacing cadence
        except asyncio.CancelledError:
            pass

    sender_task: Optional[asyncio.Task] = None
    pusher_task: Optional[asyncio.Task] = None
    receiver_task: Optional[asyncio.Task] = None

    try:
        # Establish Gemini Live Session
        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(parts=[types.Part(text=SYSTEM_PROMPT)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE)
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        async with gemini_client.aio.live.connect(model=GEMINI_LIVE_MODEL, config=live_config) as live_ws:
            # Task B: Continuous multi-turn receiver loop from Gemini Live
            async def receive_from_gemini(s: CallSession):
                try:
                    while not s.is_closing:
                        try:
                            async for response in live_ws.receive():
                                if s.is_closing:
                                    break

                                content = response.server_content
                                if not content:
                                    continue

                                # Handle native interruption (Barge-In)
                                if content.interrupted:
                                    logger.info("[BARGE-IN] Interruption detected by Gemini. Clearing audio buffer.")
                                    s.assistant_speaking = False
                                    while not s.audio_out_queue.empty():
                                        try:
                                            s.audio_out_queue.get_nowait()
                                        except asyncio.QueueEmpty:
                                            break
                                    clear_msg = {
                                        "event": "clear",
                                        "stream_id": s.stream_id,
                                        "streamSid": s.stream_id,
                                    }
                                    await websocket.send_text(json.dumps(clear_msg))

                                # Capture live transcription
                                if content.input_transcription and content.input_transcription.text:
                                    text = content.input_transcription.text
                                    s.current_user_text.append(text)

                                if content.output_transcription and content.output_transcription.text:
                                    text = content.output_transcription.text
                                    s.current_model_text.append(text)

                                if content.turn_complete:
                                    s.assistant_speaking = False
                                    if s.current_user_text:
                                        user_full = "".join(s.current_user_text).strip()
                                        if user_full:
                                            logger.info(f"[CALLER SPEECH]: {user_full}")
                                            s.dialogue_history.append({"role": "caller", "content": user_full})
                                        s.current_user_text.clear()

                                    if s.current_model_text:
                                        model_full = "".join(s.current_model_text).strip()
                                        if model_full:
                                            logger.info(f"[ASSISTANT SPEECH]: {model_full}")
                                            s.dialogue_history.append({"role": "assistant", "content": model_full})
                                        s.current_model_text.clear()

                                # Process streaming audio output from Gemini
                                if content.model_turn and content.model_turn.parts:
                                    s.assistant_speaking = True
                                    for part in content.model_turn.parts:
                                        if part.inline_data and part.inline_data.data:
                                            raw_24k = part.inline_data.data
                                            samples_24k = np.frombuffer(raw_24k, dtype=np.int16)
                                            # Resample 24kHz to 8000Hz (exact 3:1 decimation)
                                            samples_8k = resample_24k_to_8k(samples_24k)
                                            # Encode to G.711 mu-law bytes
                                            ulaw_bytes = pcm16_to_ulaw(samples_8k)
                                            await s.audio_out_queue.put(ulaw_bytes)

                        except asyncio.CancelledError:
                            break
                        except Exception as e:
                            if s.is_closing:
                                break
                            logger.warning(f"[GEMINI TURN CYCLE]: {e}")
                            await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[GEMINI RECEIVE ERROR] {e}", exc_info=True)

            # Task C: Real-Time Audio Pusher to Gemini Live
            async def gemini_audio_pusher(s: CallSession):
                try:
                    while not s.is_closing:
                        chunk = await s.inbound_audio_queue.get()
                        if chunk is None or s.is_closing:
                            break
                        await live_ws.send_realtime_input(
                            audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                        )
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"[GEMINI PUSHER ERROR] {e}", exc_info=True)

            inbound_buffer = bytearray()
            greeting_duration = (len(GREETING_ULAW) / 8000.0) if GREETING_ULAW else 3.0

            # Main Loop: Receive from Telnyx WebSocket
            while True:
                raw_msg = await websocket.receive_text()
                data = json.loads(raw_msg)
                event = data.get("event")

                if event == "connected":
                    logger.info("[TELNYX] Handshake connected event received.")

                elif event == "start":
                    stream_id = data.get("stream_id") or data.get("streamSid") or data.get("start", {}).get("stream_id", "STR_DEFAULT")
                    start_meta = data.get("start", {})
                    call_sid = start_meta.get("call_sid") or data.get("call_sid", "UNKNOWN_SID")
                    custom_params = start_meta.get("custom_parameters", {})
                    caller_phone = custom_params.get("caller", "+1-Unknown")

                    session = CallSession(stream_id, call_sid, caller_phone, websocket)
                    logger.info(f"[TELNYX] Stream started: {stream_id} for Call SID: {call_sid}")

                    # Launch audio sender, receiver, and pusher tasks
                    sender_task = asyncio.create_task(audio_sender_loop(session))
                    receiver_task = asyncio.create_task(receive_from_gemini(session))
                    pusher_task = asyncio.create_task(gemini_audio_pusher(session))

                    # Queue pre-rendered greeting audio for instant zero-latency playback
                    if GREETING_ULAW:
                        await session.audio_out_queue.put(GREETING_ULAW)
                        session.dialogue_history.append({"role": "assistant", "content": OPENING_GREETING_TEXT})
                        logger.info(f"[ASSISTANT GREETING]: {OPENING_GREETING_TEXT}")

                elif event == "media":
                    if not session:
                        continue

                    media = data.get("media", {})
                    b64_payload = media.get("payload")
                    if not b64_payload:
                        continue

                    # Decode mu-law to 8kHz PCM16, resample to 16kHz
                    ulaw_bytes = base64.b64decode(b64_payload)
                    pcm16_8k = ulaw_to_pcm16_8k(ulaw_bytes)
                    pcm16_16k = resample_8k_to_16k(pcm16_8k)

                    # Check for barge-in or completion of greeting
                    if session.greeting_active:
                        elapsed = time.time() - session.start_time
                        rms = np.sqrt(np.mean(pcm16_16k.astype(np.float64) ** 2))
                        # Caller interruptions after 1.5s grace period
                        if elapsed > 1.5 and rms > 950:
                            logger.info("[BARGE-IN] Caller interrupted opening greeting.")
                            session.greeting_active = False
                            while not session.audio_out_queue.empty():
                                try:
                                    session.audio_out_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            await websocket.send_text(json.dumps({
                                "event": "clear",
                                "stream_id": session.stream_id,
                                "streamSid": session.stream_id,
                            }))
                        elif elapsed >= greeting_duration:
                            session.greeting_active = False

                    # If greeting finished, stream caller audio to Gemini
                    if not session.greeting_active:
                        rms = np.sqrt(np.mean(pcm16_16k.astype(np.float64) ** 2))
                        # Suppress acoustic speaker echo during assistant speech unless caller interrupts
                        if session.assistant_speaking and rms < 900:
                            continue
                        elif session.assistant_speaking and rms >= 900:
                            logger.info("[BARGE-IN] Caller voice detected during assistant speech.")
                            session.assistant_speaking = False
                            while not session.audio_out_queue.empty():
                                try:
                                    session.audio_out_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            await websocket.send_text(json.dumps({
                                "event": "clear",
                                "stream_id": session.stream_id,
                                "streamSid": session.stream_id,
                            }))

                        inbound_buffer.extend(pcm16_16k.tobytes())
                        # 100ms chunks (1600 samples = 3200 bytes)
                        if len(inbound_buffer) >= 3200:
                            chunk_to_send = bytes(inbound_buffer[:3200])
                            inbound_buffer = inbound_buffer[3200:]
                            await session.inbound_audio_queue.put(chunk_to_send)

                elif event == "stop":
                    logger.info(f"[TELNYX] Stop event received for call {session.call_sid if session else 'UNKNOWN'}")
                    break

            if receiver_task:
                receiver_task.cancel()
            if pusher_task:
                await session.inbound_audio_queue.put(None)
                pusher_task.cancel()

    except WebSocketDisconnect:
        logger.info("[WEBSOCKET] Client disconnected.")
    except Exception as e:
        logger.error(f"[WEBSOCKET ERROR] {e}", exc_info=True)
    finally:
        if session:
            session.is_closing = True
            duration = time.time() - session.start_time
            logger.info(f"[CALL COMPLETED] SID: {session.call_sid} | Duration: {duration:.1f}s | Turns: {len(session.dialogue_history)}")

            if sender_task:
                await session.audio_out_queue.put(None)
                sender_task.cancel()

            # Record any remaining text fragments
            if session.current_user_text:
                user_rem = "".join(session.current_user_text).strip()
                if user_rem:
                    session.dialogue_history.append({"role": "caller", "content": user_rem})
            if session.current_model_text:
                model_rem = "".join(session.current_model_text).strip()
                if model_rem:
                    session.dialogue_history.append({"role": "assistant", "content": model_rem})

            if session.dialogue_history:
                transcript_text = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in session.dialogue_history])
                lead = await extract_structured_lead(transcript_text, session.caller_phone)
                save_lead_record(session.call_sid, session.caller_phone, lead, session.dialogue_history, duration)

# ==============================================================================
# 6. Main Server Runner
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print("=" * 65)
    print(f"Starting Alarmtronics Live AI Receptionist on http://{host}:{port}")
    print(f"Engine: Google Gemini Live API ({GEMINI_LIVE_MODEL}) | Voice: {GEMINI_VOICE}")
    print(f"Telnyx Phone Number: {TELNYX_PHONE_NUMBER}")
    print("=" * 65)
    uvicorn.run("server:app", host=host, port=port, reload=False)
