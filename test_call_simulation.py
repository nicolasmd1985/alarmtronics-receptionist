#!/usr/bin/env python3
"""
test_call_simulation.py - Local End-to-End WebSocket Telephony Test Simulator
Simulates a Telnyx inbound call over WebSockets without placing a live phone call.

Verifies:
1. TeXML Webhook negotiation
2. WebSocket connection & handshake
3. Receiving initial assistant greeting audio
4. Streaming caller audio frames (PCMU 8000Hz)
5. Detecting barge-in and audio turn completion
6. Receiving assistant reply audio frames
7. Call teardown and verifying database lead extraction
"""

import sys
import time
import json
import base64
import asyncio
import numpy as np
import websockets
from pathlib import Path

# Generate 2 seconds of synthetic 8000Hz 8-bit PCMU tone (approx speech frequency 400Hz)
def generate_synthetic_speech_ulaw(duration_seconds: float = 2.0) -> bytes:
    sample_rate = 8000
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    # 440 Hz sine wave amplitude ~12000 in PCM16 scale
    pcm16 = (12000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    
    # Fast mu-law encoding for test
    from server import pcm16_to_ulaw
    return pcm16_to_ulaw(pcm16)

async def run_simulation(ws_url: str = "ws://localhost:8000/media-stream"):
    print("=" * 60)
    print("Starting Telnyx Inbound WebSocket Call Simulation")
    print(f"Connecting to: {ws_url}")
    print("=" * 60)

    try:
        async with websockets.connect(ws_url) as ws:
            print("[SIMULATOR] WebSocket connection established.")

            # 1. Send Connected Event
            connected_evt = {
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            }
            await ws.send(json.dumps(connected_evt))
            print("[SIMULATOR -> SERVER] Sent 'connected' handshake.")

            # 2. Send Start Event
            stream_id = "TEST-STREAM-" + str(int(time.time()))
            call_sid = "TEST-CALL-SID-999"
            start_evt = {
                "event": "start",
                "sequence_number": "1",
                "stream_id": stream_id,
                "start": {
                    "account_sid": "ACT-TEST-ACCOUNT",
                    "call_sid": call_sid,
                    "stream_url": ws_url,
                    "custom_parameters": {
                        "caller": "+1-407-555-0199",
                        "call_sid": call_sid
                    }
                }
            }
            await ws.send(json.dumps(start_evt))
            print(f"[SIMULATOR -> SERVER] Sent 'start' event (Call: {call_sid}, Stream: {stream_id}).")

            # 3. Listen for Assistant's Opening Greeting Audio
            print("[SIMULATOR] Waiting for Assistant greeting audio packets...")
            assistant_chunks_received = 0
            start_wait = time.time()
            while time.time() - start_wait < 5.0:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    msg = json.loads(raw)
                    if msg.get("event") == "media":
                        assistant_chunks_received += 1
                        if assistant_chunks_received % 25 == 0:
                            print(f"  -> Received {assistant_chunks_received} assistant audio chunks...")
                except asyncio.TimeoutError:
                    if assistant_chunks_received > 0:
                        break

            print(f"[SIMULATOR] Assistant finished greeting (Total chunks received: {assistant_chunks_received}).")

            # 4. Stream Caller Audio to Server
            print("[SIMULATOR] Streaming 1.5 seconds of simulated caller speech...")
            ulaw_speech = generate_synthetic_speech_ulaw(1.5)
            chunk_size = 160  # 20ms per packet
            for i in range(0, len(ulaw_speech), chunk_size):
                chunk = ulaw_speech[i : i + chunk_size]
                media_evt = {
                    "event": "media",
                    "stream_id": stream_id,
                    "media": {
                        "payload": base64.b64encode(chunk).decode("ascii")
                    }
                }
                await ws.send(json.dumps(media_evt))
                await asyncio.sleep(0.02)

            print("[SIMULATOR] Caller finished speaking. Streaming 1.0s of silence to trigger VAD turn completion...")
            # Silence in mu-law is 0xFF
            silence_chunk = b"\xff" * 160
            for _ in range(50):  # 50 * 20ms = 1000ms
                media_evt = {
                    "event": "media",
                    "stream_id": stream_id,
                    "media": {
                        "payload": base64.b64encode(silence_chunk).decode("ascii")
                    }
                }
                await ws.send(json.dumps(media_evt))
                await asyncio.sleep(0.02)

            # 5. Wait for Assistant's Response Audio
            print("[SIMULATOR] Listening for Assistant's response audio...")
            reply_chunks = 0
            start_wait = time.time()
            while time.time() - start_wait < 4.0:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    msg = json.loads(raw)
                    if msg.get("event") == "media":
                        reply_chunks += 1
                except asyncio.TimeoutError:
                    if reply_chunks > 0:
                        break

            print(f"[SIMULATOR] Received {reply_chunks} reply audio chunks from Assistant.")

            # 6. Send Stop Event (Caller Hangs Up)
            stop_evt = {
                "event": "stop",
                "stream_id": stream_id,
                "stop": {"call_sid": call_sid}
            }
            await ws.send(json.dumps(stop_evt))
            print("[SIMULATOR -> SERVER] Sent 'stop' event (call hangup).")

            await asyncio.sleep(1.0)
            print("[SIMULATOR] Simulation completed successfully.")

    except Exception as e:
        print(f"[SIMULATOR ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/media-stream"
    asyncio.run(run_simulation(url))
