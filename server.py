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
import csv
import io
import json
import time
import base64
import asyncio
import sqlite3
import logging
import threading
import argparse
from collections import deque
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import httpx
import numpy as np
import scipy.signal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

from crm_ui import render_leads_crm_html

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
CONFIG_PATH = DATA_DIR / "config.json"

# Core Settings
COMPANY_NAME = os.getenv("COMPANY_NAME", "Alarmtronics")
OWNER_NAME = os.getenv("OWNER_NAME", "Alarmtronics")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Aoede")
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "").strip()
TELNYX_PHONE_NUMBER = os.getenv("TELNYX_PHONE_NUMBER", "+14073050475")
FORWARD_TO_NUMBER = os.getenv("FORWARD_TO_NUMBER", "+19043850725").strip()
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()

# ==============================================================================
# Persistent Call Forwarding State Management
# ==============================================================================

def load_forwarding_config() -> Dict[str, Any]:
    """Loads forwarding configuration from data/config.json with environment fallback."""
    default_active = os.getenv("CALL_FORWARDING_ACTIVE", "false").lower() in ("true", "1", "yes")
    default_allow_transfer = os.getenv("ALLOW_HUMAN_TRANSFER", "true").lower() in ("true", "1", "yes")
    default_config = {
        "call_forwarding_active": default_active,
        "allow_human_transfer": default_allow_transfer,
        "forward_to_number": FORWARD_TO_NUMBER or "+19043850725",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if not CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error creating config.json: {e}")
        return default_config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if "call_forwarding_active" not in cfg:
                cfg["call_forwarding_active"] = default_active
            if "allow_human_transfer" not in cfg:
                cfg["allow_human_transfer"] = default_allow_transfer
            if "forward_to_number" not in cfg or not cfg["forward_to_number"] or cfg["forward_to_number"] == "+19043850726":
                cfg["forward_to_number"] = FORWARD_TO_NUMBER or "+19043850725"
            return cfg
    except Exception as e:
        logger.error(f"Error reading config.json: {e}")
        return default_config

def save_forwarding_config(
    active: Optional[bool] = None,
    allow_transfer: Optional[bool] = None,
    forward_to: Optional[str] = None
) -> Dict[str, Any]:
    """Atomically updates and saves call forwarding settings to data/config.json."""
    cfg = load_forwarding_config()
    if active is not None:
        cfg["call_forwarding_active"] = bool(active)
    if allow_transfer is not None:
        cfg["allow_human_transfer"] = bool(allow_transfer)
    if forward_to:
        cfg["forward_to_number"] = str(forward_to).strip()
    cfg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        tmp_path = CONFIG_PATH.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        tmp_path.replace(CONFIG_PATH)
        logger.info(
            f"[FORWARDING CONFIG UPDATED] Active: {cfg['call_forwarding_active']} | "
            f"Allow Transfer: {cfg.get('allow_human_transfer', True)} | Target: {cfg['forward_to_number']}"
        )
    except Exception as e:
        logger.error(f"Error saving config.json: {e}")
    return cfg

def toggle_forwarding_config() -> Dict[str, Any]:
    """Inverts the current call forwarding state and persists the change."""
    cfg = load_forwarding_config()
    new_active = not cfg.get("call_forwarding_active", False)
    return save_forwarding_config(active=new_active)

def toggle_human_transfer_config() -> Dict[str, Any]:
    """Inverts the permission for AI to transfer to human and persists the change."""
    cfg = load_forwarding_config()
    new_allow = not cfg.get("allow_human_transfer", True)
    return save_forwarding_config(allow_transfer=new_allow)

def set_operational_mode(mode: str) -> Dict[str, Any]:
    """Sets one of three presets:
    - 'direct': Immediate manual call forwarding to Nicolas.
    - 'ai_hybrid': AI answers; transfers to Nicolas ONLY if caller asks.
    - 'ai_only': 100% Autonomous AI (no transfers even if asked).
    """
    mode = (mode or "").strip().lower()
    if mode == "direct":
        return save_forwarding_config(active=True)
    elif mode == "ai_hybrid":
        return save_forwarding_config(active=False, allow_transfer=True)
    elif mode == "ai_only":
        return save_forwarding_config(active=False, allow_transfer=False)
    return load_forwarding_config()

def format_status_indicator(cfg: Optional[Dict[str, Any]] = None) -> str:
    """Returns the standardized visual status badge string."""
    if cfg is None:
        cfg = load_forwarding_config()
    if cfg.get("call_forwarding_active", False):
        return f"[DESVÍO: ACTIVO -> {cfg.get('forward_to_number', FORWARD_TO_NUMBER)}]"
    else:
        allow_trans = cfg.get("allow_human_transfer", True)
        if allow_trans:
            return f"[IA ATENDIENDO + TRANSFERENCIA A HUMANO SI LO PIDEN]"
        else:
            return f"[SOLO IA - ATENCIÓN Y REGISTRO 100% AUTÓNOMO (SIN TRANSFERENCIA)]"

# In-memory registry for calls pending transfer to Nicolas
PENDING_TRANSFERS: Dict[str, Dict[str, Any]] = {}

def prune_pending_transfers():
    """Removes stale pending transfer records older than 10 minutes."""
    now = time.time()
    expired = [sid for sid, data in PENDING_TRANSFERS.items() if now - data.get("timestamp", 0) > 600]
    for sid in expired:
        PENDING_TRANSFERS.pop(sid, None)

async def transfer_call_control_v2(call_control_id: str, target_phone: str) -> bool:
    """Executes Telnyx Call Control v2 transfer action if API key is configured."""
    if not TELNYX_API_KEY or not call_control_id:
        return False
    try:
        url = f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/transfer"
        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "to": target_phone,
            "from": TELNYX_PHONE_NUMBER,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 202):
                logger.info(f"[TELNYX CCv2 TRANSFER] Transfer action initiated for {call_control_id} to {target_phone}")
                return True
            else:
                logger.warning(f"[TELNYX CCv2 TRANSFER FAILED] Status: {resp.status_code} | Body: {resp.text}")
    except Exception as e:
        logger.error(f"[TELNYX CCv2 TRANSFER ERROR] {e}")
    return False

# Initialize GenAI Client (explicitly using v1beta required by Gemini Live BidiGenerateContent WebSocket API)
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={"api_version": "v1beta"},
        )
        logger.info(f"Google GenAI Client (v1beta) initialized successfully for Live model: {GEMINI_LIVE_MODEL}")
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}")
else:
    logger.warning("GEMINI_API_KEY not configured. Calls will not be able to connect to Live API.")

# ==============================================================================
# 1. High-Performance ITU-T G.711 u-law Codec & Stateful Streaming DSP Engine
# ==============================================================================

def _generate_ulaw_tables():
    """Generates exact ITU-T G.711 mu-law O(1) lookup tables (verified 0xFF=+0, 0x80=+32124, 0x00=-32124)."""
    decode_table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        u = (~i) & 0xFF
        sign = u & 0x80
        exponent = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = (((mantissa << 3) + 0x84) << exponent) - 0x84
        decode_table[i] = -sample if sign else sample

    encode_table = np.zeros(65536, dtype=np.uint8)
    BIAS = 0x84
    CLIP = 32635
    for s in range(-32768, 32768):
        sign = 0x80 if s < 0 else 0
        mag = -s if s < 0 else s
        if mag > CLIP:
            mag = CLIP
        mag += BIAS
        # Segment exponent: biased mag in [0x84..0x7FFF] has bit_length in [8..15] -> exponent [0..7]
        exponent = max(0, min(7, mag.bit_length() - 8))
        mantissa = (mag >> (exponent + 3)) & 0x0F
        encode_table[s + 32768] = (~(sign | (exponent << 4) | mantissa)) & 0xFF

    return decode_table, encode_table

ULAW_DECODE_LUT, ULAW_ENCODE_LUT = _generate_ulaw_tables()

# Pre-computed zero-overhead Butterworth SOS filters for stateful telephony streaming
HPF_8K_SOS = scipy.signal.butter(2, 85.0, btype="high", fs=8000, output="sos")
UP_LPF_16K_SOS = scipy.signal.butter(4, 3650.0, btype="low", fs=16000, output="sos")
DOWN_LPF_24K_SOS = scipy.signal.butter(4, 3550.0, btype="low", fs=24000, output="sos")

def ulaw_to_pcm16_8k(ulaw_bytes: bytes) -> np.ndarray:
    """Decode raw G.711 mu-law 8kHz bytes into signed 16-bit PCM numpy array."""
    indices = np.frombuffer(ulaw_bytes, dtype=np.uint8)
    return ULAW_DECODE_LUT[indices]

def pcm16_to_ulaw(pcm16_samples: np.ndarray) -> bytes:
    """Encode signed 16-bit PCM numpy array into exact ITU-T G.711 mu-law bytes."""
    clipped = np.clip(pcm16_samples, -32768, 32767)
    indices = (clipped.astype(np.int32) + 32768).astype(np.uint16)
    return ULAW_ENCODE_LUT[indices].tobytes()

def _soft_limit_pcm16(samples: np.ndarray, threshold: float = 28000.0) -> np.ndarray:
    """Smoothly soft-limits peaks above threshold to avoid harsh digital clipping."""
    out = samples.astype(np.float64, copy=False)
    headroom = 32767.0 - threshold
    pos_mask = out > threshold
    neg_mask = out < -threshold
    if np.any(pos_mask):
        out = out.copy()
        out[pos_mask] = threshold + headroom * np.tanh((out[pos_mask] - threshold) / headroom)
    if np.any(neg_mask):
        if not np.any(pos_mask):
            out = out.copy()
        out[neg_mask] = -threshold - headroom * np.tanh((-out[neg_mask] - threshold) / headroom)
    return np.clip(np.rint(out), -32768, 32767).astype(np.int16)

class TelephonyAudioProcessor:
    """Per-call stateful streaming DSP processor.
    Eliminates chunk-boundary clicks/50Hz modulation, strips PSTN hum/DC offset,
    normalizes quiet cell-phone speech gently for ASR, and prevents aliasing on 24kHz->8kHz.
    """

    def __init__(self):
        self.hpf_8k_zi = np.zeros((HPF_8K_SOS.shape[0], 2), dtype=np.float64)
        self.up_16k_zi = np.zeros((UP_LPF_16K_SOS.shape[0], 2), dtype=np.float64)
        self.down_24k_zi = np.zeros((DOWN_LPF_24K_SOS.shape[0], 2), dtype=np.float64)
        self.down_24k_remainder = np.empty(0, dtype=np.int16)
        self.agc_gain = 1.0

    def inbound_ulaw_to_pcm16_16k(self, ulaw_bytes: bytes) -> tuple[np.ndarray, float]:
        """Stateful 8kHz G.711 mu-law -> conditioned 16kHz PCM16 for Gemini Live ASR."""
        if not ulaw_bytes:
            return np.empty(0, dtype=np.int16), 0.0

        pcm_8k = ulaw_to_pcm16_8k(ulaw_bytes).astype(np.float64)
        # 1. Strip DC offset, 60Hz hum, and cellular low-end rumble
        hp_8k, self.hpf_8k_zi = scipy.signal.sosfilt(HPF_8K_SOS, pcm_8k, zi=self.hpf_8k_zi)
        rms = float(np.sqrt(np.mean(hp_8k * hp_8k))) if hp_8k.size else 0.0

        # 2. Smooth speech AGC: gently lift quiet callers without amplifying line hiss
        if rms > 180.0:
            desired_gain = min(2.4, max(0.8, 2200.0 / rms))
            alpha = 0.25 if desired_gain < self.agc_gain else 0.08
            self.agc_gain += alpha * (desired_gain - self.agc_gain)
        else:
            # Relax gradually toward unity during silence
            self.agc_gain += 0.03 * (1.0 - self.agc_gain)

        conditioned_8k = hp_8k * self.agc_gain

        # 3. Stateful 2x upsampling: zero-stuff + low-pass reconstruction filter (gain=2.0)
        upsampled = np.zeros(conditioned_8k.size * 2, dtype=np.float64)
        upsampled[0::2] = conditioned_8k * 2.0
        filtered_16k, self.up_16k_zi = scipy.signal.sosfilt(UP_LPF_16K_SOS, upsampled, zi=self.up_16k_zi)
        return _soft_limit_pcm16(filtered_16k), rms

    def outbound_pcm16_24k_to_ulaw(self, raw_24k: bytes) -> bytes:
        """Stateful 24kHz PCM16 -> anti-aliased 8kHz G.711 mu-law (zero boundary clicks)."""
        if not raw_24k:
            return b""
        # Guarantee even byte length for int16 view
        usable_len = len(raw_24k) - (len(raw_24k) % 2)
        if usable_len <= 0:
            return b""
        samples = np.frombuffer(raw_24k[:usable_len], dtype=np.int16)
        if self.down_24k_remainder.size > 0:
            samples = np.concatenate((self.down_24k_remainder, samples))

        rem = samples.size % 3
        if rem:
            self.down_24k_remainder = samples[-rem:].copy()
            samples = samples[:-rem]
        else:
            self.down_24k_remainder = np.empty(0, dtype=np.int16)

        if samples.size == 0:
            return b""

        filtered_24k, self.down_24k_zi = scipy.signal.sosfilt(
            DOWN_LPF_24K_SOS, samples.astype(np.float64), zi=self.down_24k_zi
        )
        decimated_8k = _soft_limit_pcm16(filtered_24k[::3])
        return pcm16_to_ulaw(decimated_8k)

def resample_8k_to_16k(pcm16_8k: np.ndarray) -> np.ndarray:
    """Stateless 8kHz -> 16kHz helper (for one-shot scripts/tests)."""
    resampled = scipy.signal.resample_poly(pcm16_8k.astype(np.float32), 2, 1)
    return np.clip(resampled, -32768, 32767).astype(np.int16)

def resample_24k_to_8k(pcm16_24k: np.ndarray) -> np.ndarray:
    """Stateless 24kHz -> 8kHz helper with clean anti-aliasing (for one-shot scripts/tests)."""
    filtered = scipy.signal.sosfiltfilt(DOWN_LPF_24K_SOS, pcm16_24k.astype(np.float64)) if pcm16_24k.size > 24 else pcm16_24k.astype(np.float64)
    return _soft_limit_pcm16(filtered[::3])

# ==============================================================================
# 2. Conversational Persona & System Instructions
# ==============================================================================

TRANSFER_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="transfer_to_human",
            description="Transfers the active telephone call to Nicolas or human support when requested by the caller.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reason": types.Schema(
                        type="STRING",
                        description="Reason the caller requested to speak with Nicolas or a human.",
                    )
                },
                required=["reason"],
            ),
        )
    ]
)

def build_system_prompt(allow_human_transfer: bool = True) -> str:
    """Builds conversational persona instructions dynamically based on operational mode."""
    if allow_human_transfer:
        transfer_rule = (
            "- Call Transfer Rule (TRANSFER ALLOWED): If the caller explicitly asks to speak to Nicolas, a supervisor, human support, or a live operator (e.g., 'pásame con Nicolas', 'let me talk to Nicolas', 'can I speak to a person', 'connect me to support'):\n"
            "  1. Politely and warmly say: 'Certainly! Please hold a moment while I transfer your call to Nicolas right now.'\n"
            "  2. Call the transfer_to_human tool immediately."
        )
    else:
        transfer_rule = (
            "- Call Transfer Rule (TRANSFER DISABLED / AI-ONLY MODE): Direct live transfer is disabled for this shift. If the caller asks to speak to Nicolas, a supervisor, or a live person:\n"
            "  1. Warmly explain: 'Nicolas and our service supervisors are currently in the field, but I am logging all your details directly onto the supervisor dispatch queue so our team can follow up with you. Could you please provide the street address where service is needed?'\n"
            "  2. DO NOT call any transfer tool and do not promise a live transfer. Proceed collecting Name, Issue, Address, and Phone Number so the ticket is saved."
        )

    return f"""You are the professional, friendly, and efficient voice receptionist for {COMPANY_NAME}, specializing in residential and commercial Fire Alarms and Burglar/Intrusion Security Alarms.

Your primary goal is to collect 4 specific pieces of information from the caller, ONE STEP AT A TIME:
1. Caller's Full Name
2. Alarm Problem / Issue (e.g., beeping keypad, fire trouble alert, false alarm, sensor fault, battery issue)
3. Property Service Address (where the alarm system is located)
4. Callback Phone Number

Conversational Rules:
- Speak ONLY in plain, natural English at all times.
- Keep every answer natural, polite, and strictly under 25 words per response.
- Ask for ONLY ONE missing item at a time. NEVER ask multiple questions in a single response.
- Progression steps:
  - Step 1: Once you know the Name and Issue -> ask for Service Address: "Got it, [Name]. What is the street address of the property where the alarm is located?"
  - Step 2: Once you have the Address -> ask for Callback Phone Number: "Thank you. And what is your best callback phone number?"
  - Step 3: If the caller provides their phone number first, acknowledge it and ask for the Service Address: "Got your number, thank you. What is the property service address?"
  - Step 4 (Conclude and Hang Up): Once you have all 4 items (Name, Issue, Address, and Phone Number), wrap up the call professionally.
    CRITICAL DISPATCH RULE: NEVER promise or say that a technician is dispatched immediately or is on the way now. Instead, explain that the Alarmtronics service supervisor has received the ticket and will review the details to coordinate the best available technician, and our office will follow up with them to schedule.
    Conclude with this warm farewell:
    "Thank you, [Name]. I have logged your service ticket for [Address]. Our service supervisor will review the details and contact you to coordinate a technician. Have a wonderful day, goodbye!"
- Always end your final farewell message with "Have a wonderful day, goodbye!" so the call can conclude and hang up properly.
- Emergency Safety Rule: If the caller reports an active fire, smoke, or physical danger, urge them immediately: "If you are in physical danger or there is an active fire, please hang up and call 911 immediately."
{transfer_rule}
- Never repeat questions already answered. Never repeat the initial greeting.
"""

SYSTEM_PROMPT = build_system_prompt(True)

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
                duration_seconds REAL,
                status TEXT DEFAULT 'nuevo',
                notes TEXT DEFAULT ''
            )
        """)
        conn.commit()
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        for col, col_def in [
            ("service_address", "TEXT"),
            ("system_type", "TEXT"),
            ("issue_description", "TEXT"),
            ("status", "TEXT DEFAULT 'nuevo'"),
            ("notes", "TEXT DEFAULT ''"),
        ]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {col_def}")
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
                    urgency, language, summary, transcript_json, duration_seconds,
                    status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nuevo', '')
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

class ForwardingUpdateRequest(BaseModel):
    active: Optional[bool] = None
    allow_transfer: Optional[bool] = None
    target: Optional[str] = None
    mode: Optional[str] = None

class OperationalModeRequest(BaseModel):
    mode: str

@app.get("/forwarding")
async def get_forwarding_status():
    """Returns current call forwarding and AI transfer configuration."""
    prune_pending_transfers()
    cfg = load_forwarding_config()
    is_active = cfg.get("call_forwarding_active", False)
    allow_transfer = cfg.get("allow_human_transfer", True)
    mode = "direct" if is_active else ("ai_hybrid" if allow_transfer else "ai_only")
    return {
        "call_forwarding_active": is_active,
        "allow_human_transfer": allow_transfer,
        "forward_to_number": cfg.get("forward_to_number", FORWARD_TO_NUMBER),
        "operational_mode": mode,
        "status_indicator": format_status_indicator(cfg),
        "updated_at": cfg.get("updated_at"),
    }

@app.post("/forwarding/toggle")
async def toggle_forwarding_endpoint():
    """Toggles call forwarding state on/off in real-time."""
    cfg = toggle_forwarding_config()
    indicator = format_status_indicator(cfg)
    logger.info(f"[API] Call forwarding toggled: {indicator}")
    return await get_forwarding_status()

@app.post("/forwarding/toggle-transfer")
async def toggle_transfer_endpoint():
    """Toggles AI permission to transfer to human when requested by caller."""
    cfg = toggle_human_transfer_config()
    indicator = format_status_indicator(cfg)
    logger.info(f"[API] Human transfer permission toggled: {indicator}")
    return await get_forwarding_status()

@app.post("/forwarding/mode")
async def set_mode_endpoint(body: OperationalModeRequest):
    """Sets operational mode ('direct', 'ai_hybrid', 'ai_only')."""
    cfg = set_operational_mode(body.mode)
    indicator = format_status_indicator(cfg)
    logger.info(f"[API] Operational mode set to '{body.mode}': {indicator}")
    return await get_forwarding_status()

@app.post("/forwarding")
async def update_forwarding_endpoint(body: ForwardingUpdateRequest):
    """Sets call forwarding state, transfer permissions, or target number."""
    if body.mode:
        cfg = set_operational_mode(body.mode)
    else:
        cfg = save_forwarding_config(
            active=body.active,
            allow_transfer=body.allow_transfer,
            forward_to=body.target,
        )
    indicator = format_status_indicator(cfg)
    logger.info(f"[API] Forwarding config updated: {indicator}")
    return await get_forwarding_status()

@app.get("/", response_class=HTMLResponse)
async def root_dashboard(request: Request):
    """Provides a web dashboard displaying server status and configuration."""
    prune_pending_transfers()
    cfg = load_forwarding_config()
    is_active = cfg.get("call_forwarding_active", False)
    allow_transfer = cfg.get("allow_human_transfer", True)
    target_num = cfg.get("forward_to_number", FORWARD_TO_NUMBER)

    card1_class = "active" if is_active else "inactive"
    card1_badge = f"[DESVÍO DIRECTO: ACTIVO -> {target_num}]" if is_active else "[DESVÍO DIRECTO: INACTIVO (ATENDIENDO CON IA)]"
    card1_desc = (
        f"📞 ATENCIÓN MANUAL DIRECTA: Las llamadas entrantes timbran de inmediato en tu teléfono ({target_num}) para que contestes tú de forma manual. La IA está en pausa."
        if is_active else
        "🤖 ATENCIÓN VIRTUAL: Las llamadas entrantes son atendidas automáticamente por la recepcionista IA de Alarmtronics."
    )
    card1_btn = "Desactivar Desvío (Atender con IA)" if is_active else f"Activar Desvío Inmediato a {target_num}"

    card2_class = "active" if allow_transfer else "inactive-transfer"
    card2_badge = "[TRANSFERENCIA A HUMANO: PERMITIDA]" if allow_transfer else "[SOLO IA: ATENCIÓN Y REGISTRO 100% AUTÓNOMO]"
    card2_desc = (
        f"✅ Si el cliente durante la llamada pide hablar con un humano o con Nicolas, la IA anunciará un mensaje de espera y transferirá en vivo la llamada activa al {target_num}. Si no lo pide, la IA concluye y guarda el ticket normalmente."
        if allow_transfer else
        "🔒 SOLAMENTE IA: La recepcionista IA atiende el 100% de la llamada y guarda toda la información en la base de datos. Si el cliente pide hablar con un humano, la IA le indica cordialmente que registrará todos sus datos para que el equipo lo contacte, sin transferir la llamada."
    )
    card2_btn = "Cambiar a Solo IA (Desactivar Transferencia)" if allow_transfer else "Permitir Transferencia a Humano"

    host = PUBLIC_DOMAIN or request.headers.get("host") or "localhost:8000"
    scheme = "https" if "trycloudflare.com" in host or "voz." in host else request.url.scheme
    ws_scheme = "wss" if scheme == "https" else "ws"

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Alarmtronics AI Voice Receptionist & Dispatch</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b1120; color: #f8fafc; margin: 0; padding: 1.5rem; }}
            .card {{ background: #1e293b; border-radius: 12px; padding: 1.75rem; max-width: 880px; margin: 0 auto; box-shadow: 0 10px 25px -3px rgba(0,0,0,0.6); border: 1px solid #334155; }}
            h1 {{ color: #38bdf8; margin-top: 0; font-size: 1.6rem; display: flex; align-items: center; justify-content: space-between; }}
            .badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; background: #10b981; color: white; }}
            
            /* Quick Preset Buttons */
            .preset-container {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 1rem; margin: 1.25rem 0; display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }}
            .preset-label {{ font-size: 0.85rem; font-weight: 700; color: #94a3b8; margin-right: 0.5rem; }}
            .btn-preset {{ background: #1e293b; color: #f8fafc; border: 1px solid #475569; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; font-size: 0.85rem; cursor: pointer; transition: all 0.2s; }}
            .btn-preset:hover {{ background: #334155; border-color: #38bdf8; }}
            
            /* Control Cards */
            .control-card {{ border-radius: 10px; padding: 1.25rem; margin: 1rem 0; border: 2px solid; transition: all 0.3s ease; }}
            .control-card.active {{ background: rgba(239, 68, 68, 0.12); border-color: #ef4444; }}
            .control-card.inactive {{ background: rgba(16, 185, 129, 0.12); border-color: #10b981; }}
            .control-card.inactive-transfer {{ background: rgba(56, 189, 248, 0.12); border-color: #38bdf8; }}
            
            .status-badge {{ display: inline-block; padding: 0.35rem 0.85rem; border-radius: 8px; font-weight: 800; font-size: 0.95rem; letter-spacing: 0.5px; }}
            .control-card.active .status-badge {{ background: #ef4444; color: #ffffff; }}
            .control-card.inactive .status-badge {{ background: #10b981; color: #ffffff; }}
            .control-card.inactive-transfer .status-badge {{ background: #0284c7; color: #ffffff; }}
            
            .control-desc {{ margin: 0.75rem 0; font-size: 0.92rem; color: #cbd5e1; line-height: 1.45; }}
            .btn-toggle {{ background: #38bdf8; color: #0b1120; border: none; padding: 0.6rem 1.3rem; border-radius: 8px; font-weight: 700; font-size: 0.9rem; cursor: pointer; transition: background 0.2s; }}
            .btn-toggle:hover {{ background: #7dd3fc; }}
            .btn-toggle:disabled {{ opacity: 0.6; cursor: not-allowed; }}
            
            .code-box {{ background: #030712; padding: 1rem; border-radius: 8px; font-family: monospace; overflow-x: auto; margin: 1rem 0; border: 1px solid #1e293b; color: #34d399; font-size: 0.88rem; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.92rem; }}
            td, th {{ padding: 0.6rem; text-align: left; border-bottom: 1px solid #334155; }}
            a {{ color: #38bdf8; text-decoration: none; font-weight: 600; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>
                <span>Alarmtronics Telephony Dispatch</span>
                <span class="badge">LIVE MULTIMODAL</span>
            </h1>
            <p>Línea Telnyx: <strong>{TELNYX_PHONE_NUMBER}</strong> | Destino Desvío: <strong>{target_num}</strong> (Nicolas)</p>

            <!-- Quick Presets -->
            <div class="preset-container">
                <span class="preset-label">Modos Rápidos:</span>
                <button class="btn-preset" onclick="setMode('direct')">📞 1. Desvío Directo</button>
                <button class="btn-preset" onclick="setMode('ai_hybrid')">🤖 2. IA + Transferencia</button>
                <button class="btn-preset" onclick="setMode('ai_only')">🔒 3. Solo IA (Sin Transferir)</button>
            </div>

            <!-- Card 1: Desvío Directo Inmediato -->
            <div id="card1" class="control-card {card1_class}">
                <div id="card1Badge" class="status-badge">{card1_badge}</div>
                <div id="card1Desc" class="control-desc">{card1_desc}</div>
                <button id="card1Btn" class="btn-toggle" onclick="toggleForwarding()">{card1_btn}</button>
            </div>

            <!-- Card 2: Permisos de Transferencia a Humano en modo IA -->
            <div id="card2" class="control-card {card2_class}">
                <div id="card2Badge" class="status-badge">{card2_badge}</div>
                <div id="card2Desc" class="control-desc">{card2_desc}</div>
                <button id="card2Btn" class="btn-toggle" onclick="toggleTransfer()">{card2_btn}</button>
            </div>

            <h3>Configuración Telnyx TeXML</h3>
            <div class="code-box">
                Webhook URL: {scheme}://{host}/incoming-call<br>
                HTTP Method: POST<br>
                Media Stream URL: {ws_scheme}://{host}/media-stream<br>
                After-Stream Redirect: {scheme}://{host}/incoming-call-after-stream
            </div>

            <h3>Estado de Componentes</h3>
            <table>
                <tr><th>Componente</th><th>Tecnología</th><th>Estado</th></tr>
                <tr><td>Transporte Telefónico</td><td>Telnyx TeXML RTP (PCMU 8000Hz)</td><td>CONECTADO</td></tr>
                <tr><td>Desvío de Llamadas</td><td>TeXML &lt;Dial&gt; / Call Control v2</td><td>OPERACIONAL</td></tr>
                <tr><td>Motor de Voz IA</td><td>Google Gemini Live API ({GEMINI_LIVE_MODEL})</td><td>LISTO</td></tr>
                <tr><td>Transferencia Mid-Call</td><td>Gemini Tool (`transfer_to_human`)</td><td>CONFIGURABLE</td></tr>
                <tr><td>Base de Datos</td><td>SQLite ({DB_PATH.name}) + JSON Audit</td><td>SINCRONIZADO</td></tr>
            </table>

            <div style="margin-top: 1.5rem; display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center;">
                <a href="/leads" style="display:inline-flex;align-items:center;gap:0.5rem;background:#38bdf8;color:#0b1120;padding:0.65rem 1.25rem;border-radius:8px;font-weight:800;text-decoration:none;">📋 Abrir CRM de Llamadas y Tickets (/leads)</a>
                <a href="/api/leads" target="_blank" style="font-size:0.85rem;color:#94a3b8;">API JSON (/api/leads)</a>
            </div>
        </div>

        <script>
            async function toggleForwarding() {{
                const btn = document.getElementById('card1Btn');
                btn.disabled = true;
                btn.innerText = 'Actualizando...';
                try {{
                    const res = await fetch('/forwarding/toggle', {{ method: 'POST' }});
                    const data = await res.json();
                    updateUI(data);
                }} catch (err) {{
                    alert('Error al alternar desvío: ' + err);
                }} finally {{
                    btn.disabled = false;
                }}
            }}

            async function toggleTransfer() {{
                const btn = document.getElementById('card2Btn');
                btn.disabled = true;
                btn.innerText = 'Actualizando...';
                try {{
                    const res = await fetch('/forwarding/toggle-transfer', {{ method: 'POST' }});
                    const data = await res.json();
                    updateUI(data);
                }} catch (err) {{
                    alert('Error al alternar transferencia: ' + err);
                }} finally {{
                    btn.disabled = false;
                }}
            }}

            async function setMode(mode) {{
                try {{
                    const res = await fetch('/forwarding/mode', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ mode: mode }})
                    }});
                    const data = await res.json();
                    updateUI(data);
                }} catch (err) {{
                    alert('Error al cambiar modo: ' + err);
                }}
            }}

            function updateUI(data) {{
                // Card 1: Desvío Directo
                const c1 = document.getElementById('card1');
                const c1b = document.getElementById('card1Badge');
                const c1d = document.getElementById('card1Desc');
                const c1btn = document.getElementById('card1Btn');

                if (data.call_forwarding_active) {{
                    c1.className = 'control-card active';
                    c1b.innerText = '[DESVÍO DIRECTO: ACTIVO -> ' + data.forward_to_number + ']';
                    c1d.innerText = '📞 ATENCIÓN MANUAL DIRECTA: Las llamadas entrantes timbran de inmediato en tu teléfono (' + data.forward_to_number + ') para que contestes tú de forma manual. La IA está en pausa.';
                    c1btn.innerText = 'Desactivar Desvío (Atender con IA)';
                }} else {{
                    c1.className = 'control-card inactive';
                    c1b.innerText = '[DESVÍO DIRECTO: INACTIVO (ATENDIENDO CON IA)]';
                    c1d.innerText = '🤖 ATENCIÓN VIRTUAL: Las llamadas entrantes son atendidas automáticamente por la recepcionista IA de Alarmtronics.';
                    c1btn.innerText = 'Activar Desvío Inmediato a ' + data.forward_to_number;
                }}

                // Card 2: Permisos de Transferencia en Modo IA
                const c2 = document.getElementById('card2');
                const c2b = document.getElementById('card2Badge');
                const c2d = document.getElementById('card2Desc');
                const c2btn = document.getElementById('card2Btn');

                if (data.allow_human_transfer) {{
                    c2.className = 'control-card active';
                    c2b.innerText = '[TRANSFERENCIA A HUMANO: PERMITIDA]';
                    c2d.innerText = '✅ Si el cliente durante la llamada pide hablar con un humano o con Nicolas, la IA anunciará un mensaje de espera y transferirá en vivo la llamada activa al ' + data.forward_to_number + '. Si no lo pide, la IA concluye y guarda el ticket normalmente.';
                    c2btn.innerText = 'Cambiar a Solo IA (Desactivar Transferencia)';
                }} else {{
                    c2.className = 'control-card inactive-transfer';
                    c2b.innerText = '[SOLO IA: ATENCIÓN Y REGISTRO 100% AUTÓNOMO]';
                    c2d.innerText = '🔒 SOLAMENTE IA: La recepcionista IA atiende el 100% de la llamada y guarda toda la información en la base de datos. Si el cliente pide hablar con un humano, la IA le indica cordialmente que registrará todos sus datos para que el equipo lo contacte, sin transferir la llamada.';
                    c2btn.innerText = 'Permitir Transferencia a Humano';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker & monitoring."""
    cfg = load_forwarding_config()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "engine": "gemini-live-multimodal",
        "live_model": GEMINI_LIVE_MODEL,
        "voice": GEMINI_VOICE,
        "gemini_active": gemini_client is not None,
        "call_forwarding": {
            "active": cfg.get("call_forwarding_active", False),
            "target": cfg.get("forward_to_number", FORWARD_TO_NUMBER),
            "status": format_status_indicator(cfg),
        },
    }

VALID_LEAD_STATUSES = {"nuevo", "en_progreso", "agendado", "resuelto", "descartado"}
VALID_LEAD_URGENCIES = {"emergency", "urgent", "normal"}

class LeadUpdateRequest(BaseModel):
    status: Optional[str] = None
    urgency: Optional[str] = None
    notes: Optional[str] = None

def _hydrate_lead_row(row: sqlite3.Row) -> Dict[str, Any]:
    r = dict(row)
    r["status"] = (r.get("status") or "nuevo").lower()
    r["notes"] = r.get("notes") or ""
    if r.get("transcript_json"):
        try:
            r["transcript"] = json.loads(r["transcript_json"])
        except Exception:
            r["transcript"] = []
    else:
        r["transcript"] = []
    return r

def _query_leads(limit: int = 500) -> List[Dict[str, Any]]:
    init_database()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY timestamp DESC, id DESC LIMIT ?", (max(1, min(limit, 2000)),))
        return [_hydrate_lead_row(row) for row in cursor.fetchall()]

@app.get("/leads")
async def leads_crm_page(request: Request):
    """Serves the Alarmtronics Leads CRM UI (or JSON if explicitly requested via ?format=json or Accept: application/json)."""
    fmt = (request.query_params.get("format") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    if fmt == "json" or ("application/json" in accept and "text/html" not in accept):
        rows = _query_leads(limit=500)
        return JSONResponse({"count": len(rows), "leads": rows})

    cfg = load_forwarding_config()
    target_num = cfg.get("forward_to_number", FORWARD_TO_NUMBER)
    html = render_leads_crm_html(
        company_name=COMPANY_NAME,
        telnyx_number=TELNYX_PHONE_NUMBER,
        forward_number=target_num,
    )
    return HTMLResponse(content=html)

@app.get("/api/leads")
async def api_list_leads(
    limit: int = 500,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    q: Optional[str] = None,
):
    """Returns captured leads from SQLite as JSON for the CRM and integrations."""
    rows = _query_leads(limit=limit)
    if status and status != "all":
        st = status.lower()
        rows = [r for r in rows if (r.get("status") or "nuevo").lower() == st]
    if urgency and urgency != "all":
        urg = urgency.lower()
        rows = [r for r in rows if (r.get("urgency") or "normal").lower() == urg]
    if q and q.strip():
        needle = q.strip().lower()
        rows = [
            r for r in rows
            if needle in " ".join(
                str(r.get(k) or "") for k in ("caller_name", "caller_phone", "caller_from_number", "service_address", "issue_description", "summary", "notes", "call_sid")
            ).lower()
        ]
    return {"count": len(rows), "leads": rows}

@app.get("/api/leads/export.csv")
async def api_export_leads_csv():
    """Exports all captured CRM leads as an Excel-compatible UTF-8 CSV."""
    rows = _query_leads(limit=2000)
    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Microsoft Excel
    writer = csv.writer(buf)
    writer.writerow([
        "ID", "Fecha (UTC)", "Cliente", "Teléfono", "Caller ID",
        "Dirección de Servicio", "Tipo de Sistema", "Problema",
        "Urgencia", "Estado CRM", "Duración (s)", "Resumen IA", "Notas", "Call SID"
    ])
    for r in rows:
        writer.writerow([
            r.get("id"),
            r.get("timestamp") or "",
            r.get("caller_name") or "",
            r.get("caller_phone") or "",
            r.get("caller_from_number") or "",
            r.get("service_address") or "",
            r.get("system_type") or "",
            r.get("issue_description") or r.get("reason_for_call") or "",
            r.get("urgency") or "normal",
            r.get("status") or "nuevo",
            round(float(r.get("duration_seconds") or 0), 1),
            r.get("summary") or "",
            r.get("notes") or "",
            r.get("call_sid") or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alarmtronics_leads.csv"'},
    )

@app.patch("/api/leads/{lead_id}")
async def api_update_lead(lead_id: int, body: LeadUpdateRequest):
    """Updates CRM workflow status, urgency, or internal supervisor notes for a lead."""
    init_database()
    updates = []
    params: List[Any] = []
    if body.status is not None:
        st = body.status.strip().lower()
        if st not in VALID_LEAD_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {st}")
        updates.append("status = ?")
        params.append(st)
    if body.urgency is not None:
        urg = body.urgency.strip().lower()
        if urg not in VALID_LEAD_URGENCIES:
            raise HTTPException(status_code=400, detail=f"Invalid urgency: {urg}")
        updates.append("urgency = ?")
        params.append(urg)
    if body.notes is not None:
        updates.append("notes = ?")
        params.append(body.notes)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        params.append(lead_id)
        cursor.execute(f"UPDATE leads SET {', '.join(updates)} WHERE id = ?", params)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        conn.commit()
        row = cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return _hydrate_lead_row(row)

@app.delete("/api/leads/{lead_id}")
async def api_delete_lead(lead_id: int):
    """Deletes a call record (e.g. test call or spam) from the SQLite CRM."""
    init_database()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lead not found")
        conn.commit()
    return {"deleted": True, "id": lead_id}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call_webhook(request: Request):
    """Telnyx TeXML & Call Control Inbound Webhook."""
    caller_from = "+1-Unknown"
    call_sid = "CALL_" + str(int(time.time()))
    call_control_id = None
    content_type = request.headers.get("content-type", "")

    try:
        if "application/json" in content_type:
            body = await request.json()
            payload = body.get("data", {}).get("payload", {})
            caller_from = payload.get("from", caller_from)
            call_control_id = payload.get("call_control_id") or body.get("data", {}).get("call_control_id")
            call_sid = call_control_id or call_sid
        else:
            form = await request.form()
            caller_from = form.get("From", caller_from)
            call_sid = form.get("CallSid", form.get("call_control_id", call_sid))
            call_control_id = form.get("call_control_id")
    except Exception as e:
        logger.warning(f"Could not parse incoming call body: {e}")

    cfg = load_forwarding_config()
    target = cfg.get("forward_to_number", FORWARD_TO_NUMBER)
    host = PUBLIC_DOMAIN or request.headers.get("host") or "localhost:8000"
    scheme = "https" if "trycloudflare.com" in host or "voz." in host or request.url.scheme == "https" else request.url.scheme
    ws_scheme = "wss" if scheme == "https" else "ws"
    stream_url = f"{ws_scheme}://{host}/media-stream"
    dial_status_url = f"{scheme}://{host}/dial-status"

    # 1. Immediate Call Forwarding if Active
    if cfg.get("call_forwarding_active", False):
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("\n" + "=" * 80)
        print(f"[{timestamp_str}] [CALL FORWARDED - IMMEDIATE MANUAL ANSWER]")
        print(f"Incoming From : {caller_from}")
        print(f"Call SID      : {call_sid}")
        print(f"Forwarded To  : {target} (Nicolas)")
        print(f"Mode          : DIRECT CALL FORWARDING (AI Receptionist Bypassed)")
        print(f"Status        : Ringing destination phone for manual answering")
        print("=" * 80 + "\n")
        logger.info(f"[CALL FORWARDED] From: {caller_from} -> To: {target} | SID: {call_sid}")

        # If Call Control v2 JSON event and API key present:
        if "application/json" in content_type and call_control_id and TELNYX_API_KEY:
            asyncio.create_task(transfer_call_control_v2(call_control_id, target))
            return JSONResponse({"status": "forwarded", "to": target, "call_control_id": call_control_id})

        # TeXML Dial response (with authorized Caller ID and Number encapsulation):
        texml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial action="{dial_status_url}" method="POST" callerId="{TELNYX_PHONE_NUMBER}" timeout="25">
        <Number>{target}</Number>
    </Dial>
</Response>
"""
        return Response(content=texml_response.strip(), media_type="application/xml")

    # 2. Inactive Forwarding: Route to AI Voice Receptionist
    allow_transfer = cfg.get("allow_human_transfer", True)
    logger.info(f"[INCOMING CALL -> AI] SID: {call_sid} | From: {caller_from} | Allow Transfer: {allow_transfer} | Stream: {stream_url}")

    if allow_transfer:
        # AI Hybrid Mode: Stream to AI with action hook on <Connect> so terminating stream on transfer triggers Dial to Nicolas
        action_url = f"{scheme}://{host}/incoming-call-after-stream?call_sid={call_sid}"
        texml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect action="{action_url}" method="POST">
        <Stream url="{stream_url}" bidirectionalMode="rtp" bidirectionalCodec="PCMU">
            <Parameter name="caller" value="{caller_from}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
</Response>
"""
    else:
        # Solo IA (100% Autonomous Mode): Pure stream then hang up cleanly, never transfers
        texml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" bidirectionalMode="rtp" bidirectionalCodec="PCMU">
            <Parameter name="caller" value="{caller_from}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
    <Hangup />
</Response>
"""
    return Response(content=texml_response.strip(), media_type="application/xml")

@app.api_route("/dial-status", methods=["GET", "POST"])
async def dial_status_webhook(request: Request):
    """Logs Telnyx <Dial> completion/failure status and SIP response codes."""
    params = dict(request.query_params)
    try:
        form = await request.form()
        params.update(dict(form))
    except Exception:
        pass
    dial_status = params.get("DialCallStatus", "unknown")
    sip_code = params.get("DialSipResponseCode", "N/A")
    logger.info(f"[DIAL STATUS CALLBACK] Status: {dial_status} | SIP Code: {sip_code} | Details: {params}")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup />
</Response>
"""
    return Response(content=xml.strip(), media_type="application/xml")

@app.api_route("/incoming-call-after-stream", methods=["GET", "POST"])
async def incoming_call_after_stream(request: Request):
    """TeXML webhook invoked after WebSocket stream completes."""
    call_sid = request.query_params.get("call_sid") or "UNKNOWN_SID"
    caller_from = request.query_params.get("caller") or "+1-Unknown"
    try:
        form = await request.form()
        call_sid = form.get("CallSid", form.get("call_control_id", call_sid))
        caller_from = form.get("From", caller_from)
    except Exception:
        pass

    cfg = load_forwarding_config()
    allow_transfer = cfg.get("allow_human_transfer", True)
    transfer_info = PENDING_TRANSFERS.pop(call_sid, None)
    if transfer_info and transfer_info.get("transfer") and allow_transfer:
        target = transfer_info.get("target") or cfg.get("forward_to_number", FORWARD_TO_NUMBER)
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("\n" + "=" * 80)
        print(f"[{timestamp_str}] [EXECUTING TeXML MID-CALL TRANSFER]")
        print(f"Call SID     : {call_sid}")
        print(f"Caller       : {caller_from}")
        print(f"Dialing To   : {target} (Nicolas)")
        print(f"Reason       : {transfer_info.get('reason', 'Caller requested transfer')}")
        print(f"Status       : Bridging caller to destination phone now")
        print("=" * 80 + "\n")
        logger.info(f"[MID-CALL TRANSFER EXECUTED] Dialing {target} for SID {call_sid}")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{TELNYX_PHONE_NUMBER}" timeout="25">
        <Number>{target}</Number>
    </Dial>
</Response>
"""
        return Response(content=xml.strip(), media_type="application/xml")

    # Normal completion hangup
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup />
</Response>
"""
    return Response(content=xml.strip(), media_type="application/xml")

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
        self.hangup_scheduled = False
        self.transfer_requested = False
        self.transfer_reason = ""
        self.clear_requested = False
        self.speech_frames_streak = 0
        self.bargein_frames_streak = 0
        self.greeting_preroll: deque[bytes] = deque(maxlen=6)
        self.dsp = TelephonyAudioProcessor()
        self.audio_out_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.inbound_audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self.dialogue_history: List[Dict[str, str]] = []
        self.current_user_text: List[str] = []
        self.current_model_text: List[str] = []

    def clear_audio_output(self):
        """Immediately drains queued outbound audio and signals the continuous pacer to flush."""
        self.clear_requested = True
        while not self.audio_out_queue.empty():
            try:
                self.audio_out_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("[WEBSOCKET] Client connected.")

    session: Optional[CallSession] = None
    if not gemini_client:
        logger.error("GenAI client not initialized. Cannot service call.")
        await websocket.close()
        return

    # Task A: Continuous ring-buffer pacer sending exact 20ms (160-byte) PCMU frames
    # with monotonic clock drift compensation and ZERO mid-sentence silence padding.
    async def audio_sender_loop(s: CallSession):
        chunk_size = 160  # 20ms of 8kHz PCMU
        pending = bytearray()
        next_send_time: Optional[float] = None
        try:
            while not s.is_closing:
                if s.clear_requested:
                    pending.clear()
                    next_send_time = None
                    s.clear_requested = False

                # Fill buffer from queue
                if len(pending) < chunk_size:
                    try:
                        timeout = 0.06 if len(pending) > 0 else None
                        frame = await asyncio.wait_for(s.audio_out_queue.get(), timeout=timeout)
                        if frame is None or s.is_closing:
                            break
                        if s.clear_requested:
                            pending.clear()
                            next_send_time = None
                            s.clear_requested = False
                            continue
                        pending.extend(frame)
                    except asyncio.TimeoutError:
                        # Stream paused cleanly at end-of-turn: flush final partial <20ms tail
                        if len(pending) > 0 and not s.clear_requested:
                            chunk = bytes(pending).ljust(chunk_size, b"\xff")
                            pending.clear()
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
                        next_send_time = None
                        continue

                # Drain any additional queued frames non-blockingly so chunks stitch seamlessly
                while not s.audio_out_queue.empty():
                    try:
                        extra = s.audio_out_queue.get_nowait()
                        if extra is None:
                            s.is_closing = True
                            break
                        pending.extend(extra)
                    except asyncio.QueueEmpty:
                        break

                while len(pending) >= chunk_size and not s.is_closing:
                    if s.clear_requested:
                        pending.clear()
                        next_send_time = None
                        s.clear_requested = False
                        break

                    chunk = bytes(pending[:chunk_size])
                    del pending[:chunk_size]

                    now = time.monotonic()
                    if next_send_time is None or (now - next_send_time) > 0.08:
                        next_send_time = now
                    delay = next_send_time - now
                    if delay > 0.001:
                        await asyncio.sleep(delay)
                    next_send_time += 0.020

                    if s.is_closing or s.clear_requested:
                        continue

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
                        s.is_closing = True
                        break
        except asyncio.CancelledError:
            pass

    async def schedule_hangup(s: CallSession):
        if s.hangup_scheduled:
            return
        s.hangup_scheduled = True
        try:
            logger.info(f"[AUTO HANGUP] Scheduling automatic hangup for SID: {s.call_sid}...")
            # Wait for all buffered audio to be dispatched to Telnyx
            while not s.audio_out_queue.empty() and not s.is_closing:
                await asyncio.sleep(0.15)
            # Grace period for Telnyx/carrier audio playback to finish cleanly
            await asyncio.sleep(2.5)
            if not s.is_closing:
                logger.info(f"[AUTO HANGUP] Goodbye audio finished. Terminating WebSocket stream for SID: {s.call_sid}.")
                s.is_closing = True
                await websocket.close(code=1000, reason="Call completed normally")
        except Exception as e:
            logger.warning(f"[AUTO HANGUP EXCEPTION]: {e}")

    async def schedule_transfer(s: CallSession):
        if s.hangup_scheduled:
            return
        s.hangup_scheduled = True
        target = PENDING_TRANSFERS.get(s.call_sid, {}).get("target", FORWARD_TO_NUMBER)
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("\n" + "=" * 80)
        print(f"[{timestamp_str}] [MID-CALL TRANSFER INITIATED]")
        print(f"Call SID     : {s.call_sid}")
        print(f"Caller Phone : {s.caller_phone}")
        print(f"Transfer To  : {target} (Nicolas)")
        print(f"Reason       : {s.transfer_reason or 'Caller requested transfer'}")
        print(f"Status       : Announcing courtesy transfer message & transferring...")
        print("=" * 80 + "\n")
        logger.info(f"[MID-CALL TRANSFER] Initiating transfer for Call SID {s.call_sid} to {target}")

        try:
            # Wait for all buffered audio (courtesy message) to be dispatched to Telnyx
            while not s.audio_out_queue.empty() and not s.is_closing:
                await asyncio.sleep(0.15)
            # Grace period for Telnyx RTP delivery to caller's ear
            await asyncio.sleep(2.5)

            # If Call Control v2 API is available with a valid carrier ID, trigger it concurrently
            if TELNYX_API_KEY and not s.call_sid.startswith("CALL_"):
                asyncio.create_task(transfer_call_control_v2(s.call_sid, target))

            if not s.is_closing:
                logger.info(f"[MID-CALL TRANSFER] Closing WebSocket stream to trigger TeXML Dial continuation.")
                s.is_closing = True
                await websocket.close(code=1000, reason="Transferring call to Nicolas")
        except Exception as e:
            logger.warning(f"[SCHEDULE TRANSFER EXCEPTION]: {e}")

    sender_task: Optional[asyncio.Task] = None
    pusher_task: Optional[asyncio.Task] = None
    receiver_task: Optional[asyncio.Task] = None

    try:
        # Load active configuration for this call
        call_cfg = load_forwarding_config()
        allow_human_transfer = call_cfg.get("allow_human_transfer", True)
        call_prompt = build_system_prompt(allow_human_transfer)
        call_tools = [TRANSFER_TOOL] if allow_human_transfer else None

        logger.info(f"[CALL SESSION CONFIG] AI Answering | Allow Human Transfer: {allow_human_transfer}")

        # Establish Gemini Live Session with telephony-tuned VAD and Function Calling
        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(parts=[types.Part(text=call_prompt)]),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE)
                )
            ),
            tools=call_tools,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=300,
                    silence_duration_ms=700,
                )
            ),
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

                                # Handle Gemini Live Tool Call (Only if human transfer is enabled)
                                if allow_human_transfer and hasattr(response, "tool_call") and response.tool_call and response.tool_call.function_calls:
                                    for fc in response.tool_call.function_calls:
                                        if fc.name == "transfer_to_human":
                                            reason = "Caller requested transfer to Nicolas"
                                            if fc.args and isinstance(fc.args, dict):
                                                reason = fc.args.get("reason", reason)
                                            logger.info(f"[CALL TRANSFER TOOL] Gemini Live called transfer_to_human: {reason}")
                                            s.transfer_requested = True
                                            s.transfer_reason = reason
                                            target_num = load_forwarding_config().get("forward_to_number", FORWARD_TO_NUMBER)
                                            PENDING_TRANSFERS[s.call_sid] = {
                                                "transfer": True,
                                                "target": target_num,
                                                "reason": reason,
                                                "timestamp": time.time(),
                                            }
                                            try:
                                                tool_resp = types.LiveClientToolResponse(
                                                    function_responses=[
                                                        types.FunctionResponse(
                                                            name="transfer_to_human",
                                                            id=fc.id,
                                                            response={"status": "transfer_in_progress", "destination": target_num}
                                                        )
                                                    ]
                                                )
                                                await live_ws.send(tool_response=tool_resp)
                                            except Exception as te:
                                                logger.warning(f"Error sending tool response: {te}")

                                content = response.server_content
                                if not content:
                                    continue

                                # Handle native interruption (Barge-In)
                                if content.interrupted:
                                    logger.info("[BARGE-IN] Interruption detected by Gemini. Clearing audio buffer.")
                                    s.assistant_speaking = False
                                    s.clear_audio_output()
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
                                            if allow_human_transfer:
                                                user_lower = user_full.lower()
                                                caller_transfer_triggers = [
                                                    "speak to nicolas", "talk to nicolas", "with nicolas",
                                                    "pasame con nicolas", "pásame con nicolas", "hablar con nicolas",
                                                    "comunícame con nicolas", "comunicame con nicolas",
                                                    "speak to a human", "talk to a human", "speak to a person",
                                                    "talk to a person", "talk to an operator", "speak to support",
                                                    "connect me to support", "transfer me", "real person", "human agent"
                                                ]
                                                if any(trig in user_lower for trig in caller_transfer_triggers):
                                                    s.transfer_requested = True
                                                    s.transfer_reason = f"Caller intent: '{user_full}'"
                                                    target_num = load_forwarding_config().get("forward_to_number", FORWARD_TO_NUMBER)
                                                    PENDING_TRANSFERS[s.call_sid] = {
                                                        "transfer": True,
                                                        "target": target_num,
                                                        "reason": s.transfer_reason,
                                                        "timestamp": time.time(),
                                                    }
                                        s.current_user_text.clear()

                                    if s.current_model_text:
                                        model_full = "".join(s.current_model_text).strip()
                                        if model_full:
                                            logger.info(f"[ASSISTANT SPEECH]: {model_full}")
                                            s.dialogue_history.append({"role": "assistant", "content": model_full})

                                            if allow_human_transfer:
                                                model_lower = model_full.lower()
                                                assistant_transfer_triggers = [
                                                    "transfer your call", "transfer you to nicolas",
                                                    "transferring you to nicolas", "transferring you now",
                                                    "transfer you now", "connecting you to nicolas",
                                                    "connect you to nicolas", "hold a moment while i transfer",
                                                    "hold while i transfer", "transfer you right now"
                                                ]
                                                if any(kw in model_lower for kw in assistant_transfer_triggers):
                                                    s.transfer_requested = True
                                                    if not s.transfer_reason:
                                                        s.transfer_reason = "Assistant announced transfer"
                                                    target_num = load_forwarding_config().get("forward_to_number", FORWARD_TO_NUMBER)
                                                    PENDING_TRANSFERS[s.call_sid] = {
                                                        "transfer": True,
                                                        "target": target_num,
                                                        "reason": s.transfer_reason,
                                                        "timestamp": time.time(),
                                                    }

                                            if s.transfer_requested:
                                                logger.info(f"[MID-CALL TRANSFER DETECTED] Scheduling transfer execution to Nicolas.")
                                                asyncio.create_task(schedule_transfer(s))
                                            else:
                                                # Automated call conclusion detection
                                                goodbye_keywords = [
                                                    "goodbye",
                                                    "have a wonderful day",
                                                    "have a great day",
                                                    "have a good day",
                                                    "bye-bye",
                                                    "take care",
                                                    "supervisor will review",
                                                    "coordinate a technician",
                                                ]
                                                model_lower = model_full.lower()
                                                caller_turns = [t for t in s.dialogue_history if t["role"] == "caller"]
                                                if len(caller_turns) >= 2 and any(kw in model_lower for kw in goodbye_keywords):
                                                    logger.info(f"[AUTO HANGUP DETECTED] Assistant concluded call. Scheduling disconnect.")
                                                    asyncio.create_task(schedule_hangup(s))

                                        s.current_model_text.clear()

                                # Process streaming audio output from Gemini
                                if content.model_turn and content.model_turn.parts:
                                    s.assistant_speaking = True
                                    for part in content.model_turn.parts:
                                        if hasattr(part, "function_call") and part.function_call and part.function_call.name == "transfer_to_human":
                                            s.transfer_requested = True
                                            s.transfer_reason = "Function call part in turn"
                                            PENDING_TRANSFERS[s.call_sid] = {
                                                "transfer": True,
                                                "target": load_forwarding_config().get("forward_to_number", FORWARD_TO_NUMBER),
                                                "reason": s.transfer_reason,
                                                "timestamp": time.time(),
                                            }

                                        if part.inline_data and part.inline_data.data:
                                            ulaw_bytes = s.dsp.outbound_pcm16_24k_to_ulaw(part.inline_data.data)
                                            if ulaw_bytes:
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
                    start_meta = data.get("start", {})
                    stream_id = (
                        data.get("stream_id")
                        or data.get("streamSid")
                        or start_meta.get("stream_id")
                        or start_meta.get("streamSid")
                        or "STR_DEFAULT"
                    )
                    custom_params = (
                        start_meta.get("custom_parameters")
                        or start_meta.get("customParameters")
                        or {}
                    )
                    call_sid = (
                        custom_params.get("call_sid")
                        or start_meta.get("call_sid")
                        or start_meta.get("callSid")
                        or start_meta.get("call_control_id")
                        or data.get("call_sid")
                        or data.get("call_control_id")
                        or "UNKNOWN_SID"
                    )
                    caller_phone = (
                        custom_params.get("caller")
                        or start_meta.get("from")
                        or "+1-Unknown"
                    )

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

                    # Stateful G.711 decode + 85Hz HPF + gentle AGC + click-free 16kHz upsampling
                    ulaw_bytes = base64.b64decode(b64_payload)
                    pcm16_16k, rms = session.dsp.inbound_ulaw_to_pcm16_16k(ulaw_bytes)
                    if pcm16_16k.size == 0:
                        continue
                    frame_bytes = pcm16_16k.tobytes()

                    # Check for sustained barge-in or natural completion of opening greeting
                    if session.greeting_active:
                        session.greeting_preroll.append(frame_bytes)
                        elapsed = time.time() - session.start_time
                        if elapsed > 0.8 and rms > 580:
                            session.speech_frames_streak += 1
                        else:
                            session.speech_frames_streak = 0

                        if session.speech_frames_streak >= 3:
                            logger.info("[BARGE-IN] Caller interrupted opening greeting.")
                            session.greeting_active = False
                            session.speech_frames_streak = 0
                            session.clear_audio_output()
                            await websocket.send_text(json.dumps({
                                "event": "clear",
                                "stream_id": session.stream_id,
                                "streamSid": session.stream_id,
                            }))
                            # Forward pre-roll frames so the caller's very first syllable is preserved
                            for pre in session.greeting_preroll:
                                inbound_buffer.extend(pre)
                            session.greeting_preroll.clear()
                            frame_bytes = b""
                        elif elapsed >= greeting_duration:
                            session.greeting_active = False
                            session.greeting_preroll.clear()

                    # Continuous full-duplex audio streaming to Gemini Live (never starve VAD!)
                    if not session.greeting_active:
                        if session.assistant_speaking:
                            if rms >= 1050:
                                session.bargein_frames_streak += 1
                            else:
                                session.bargein_frames_streak = 0

                            if session.bargein_frames_streak >= 4:
                                logger.info("[BARGE-IN] Caller voice detected during assistant speech.")
                                session.assistant_speaking = False
                                session.bargein_frames_streak = 0
                                session.clear_audio_output()
                                await websocket.send_text(json.dumps({
                                    "event": "clear",
                                    "stream_id": session.stream_id,
                                    "streamSid": session.stream_id,
                                }))
                            elif rms < 420 and frame_bytes:
                                # Gently attenuate quiet echo floor instead of dropping frames
                                attenuated = (pcm16_16k.astype(np.float32) * 0.35).astype(np.int16)
                                frame_bytes = attenuated.tobytes()
                        else:
                            session.bargein_frames_streak = 0

                        if frame_bytes:
                            inbound_buffer.extend(frame_bytes)

                        # Stream 40ms frames (640 samples = 1280 bytes) for responsive VAD & ASR
                        while len(inbound_buffer) >= 1280:
                            chunk_to_send = bytes(inbound_buffer[:1280])
                            del inbound_buffer[:1280]
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
                if session.transfer_requested:
                    lead.summary = f"[TRANSFERRED TO NICOLAS ({session.transfer_reason})] {lead.summary}"
                save_lead_record(session.call_sid, session.caller_phone, lead, session.dialogue_history, duration)

# ==============================================================================
# 6. Interactive CLI Keyboard Listener & Main Server Runner
# ==============================================================================

def console_keyboard_listener():
    """Background listener for interactive CLI console control."""
    if not sys.stdin.isatty():
        return
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            cmd = line.strip().lower()
            if cmd in ("f", "1", "toggle"):
                cfg = toggle_forwarding_config()
                indicator = format_status_indicator(cfg)
                print(f"\n>>> [CALL FORWARDING TOGGLED] Now: {indicator}\n")
            elif cmd in ("t", "2", "transfer"):
                cfg = toggle_human_transfer_config()
                indicator = format_status_indicator(cfg)
                print(f"\n>>> [HUMAN TRANSFER PERMISSION TOGGLED] Now: {indicator}\n")
            elif cmd in ("s", "status"):
                indicator = format_status_indicator()
                print(f"\n>>> Current Telephony State: {indicator}\n")
            elif cmd in ("h", "help", "?"):
                print("\n" + "-" * 65)
                print("Interactive Keyboard Commands:")
                print("  f or 1  -> Alternar Desvío Directo Inmediato (Activo <-> Inactivo)")
                print("  t or 2  -> Alternar Permiso de Transferencia IA (Permitida <-> Solo IA)")
                print("  s       -> Imprimir Estado Actual")
                print("  h       -> Mostrar Esta Ayuda")
                print("-" * 65 + "\n")
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="Alarmtronics AI Voice Receptionist Server")
    parser.add_argument("--status", action="store_true", help="Print current operational status and exit")
    parser.add_argument("--toggle-forward", action="store_true", help="Toggle direct call forwarding and exit")
    parser.add_argument("--forward-on", action="store_true", help="Activate direct call forwarding to Nicolas and exit")
    parser.add_argument("--forward-off", action="store_true", help="Deactivate direct forwarding (attend with AI) and exit")
    parser.add_argument("--transfer-on", action="store_true", help="Allow AI to transfer live calls to human when requested")
    parser.add_argument("--transfer-off", action="store_true", help="Disable AI mid-call live transfer (force AI-only autonomous mode)")
    parser.add_argument("--mode", type=str, choices=["direct", "ai_hybrid", "ai_only"], help="Set operational preset mode")
    parser.add_argument("--set-forward-number", type=str, help="Update forwarding destination phone number and exit")
    args, unknown = parser.parse_known_args()

    if args.status:
        print(format_status_indicator())
        sys.exit(0)
    elif args.toggle_forward:
        cfg = toggle_forwarding_config()
        print(f"Toggled: {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.forward_on:
        cfg = save_forwarding_config(active=True)
        print(f"Direct Forwarding Enabled: {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.forward_off:
        cfg = save_forwarding_config(active=False)
        print(f"Direct Forwarding Disabled: {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.transfer_on:
        cfg = save_forwarding_config(allow_transfer=True)
        print(f"Human Transfer Allowed: {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.transfer_off:
        cfg = save_forwarding_config(allow_transfer=False)
        print(f"Solo IA Mode (Transfers Disabled): {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.mode:
        cfg = set_operational_mode(args.mode)
        print(f"Mode set to '{args.mode}': {format_status_indicator(cfg)}")
        sys.exit(0)
    elif args.set_forward_number:
        cfg = save_forwarding_config(forward_to=args.set_forward_number)
        print(f"Updated destination: {format_status_indicator(cfg)}")
        sys.exit(0)

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    cfg = load_forwarding_config()

    print("=" * 70)
    print(f"Starting Alarmtronics Live AI Receptionist on http://{host}:{port}")
    print(f"Engine: Google Gemini Live API ({GEMINI_LIVE_MODEL}) | Voice: {GEMINI_VOICE}")
    print(f"Telnyx Phone Number : {TELNYX_PHONE_NUMBER}")
    print(f"Forward Destination : {cfg.get('forward_to_number', FORWARD_TO_NUMBER)} (Nicolas)")
    print(f"STATUS              : {format_status_indicator(cfg)}")
    print("=" * 70)
    if sys.stdin.isatty():
        print("[CONSOLE MENU] 'f'=Toggle Desvío | 't'=Toggle Transfer Humano | 's'=Status | 'h'=Help")
        print("=" * 70)
        threading.Thread(target=console_keyboard_listener, daemon=True).start()

    uvicorn.run("server:app", host=host, port=port, reload=False)
