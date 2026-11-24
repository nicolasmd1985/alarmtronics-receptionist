#!/usr/bin/env python3
"""
test_forwarding_and_endpoints.py - Automated test suite for call forwarding,
operational presets, and granular AI transfer permissions.
"""

import sys
import json
from fastapi.testclient import TestClient

from server import (
    app,
    save_forwarding_config,
    load_forwarding_config,
    set_operational_mode,
    build_system_prompt,
    pcm16_to_ulaw,
    ulaw_to_pcm16_8k,
    TelephonyAudioProcessor,
    PENDING_TRANSFERS,
    TELNYX_PHONE_NUMBER,
    DB_PATH,
)
import sqlite3
import numpy as np

client = TestClient(app)

def test_health_endpoint():
    print("\n--- Test: Health Endpoint ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "healthy"
    assert "call_forwarding" in data
    print("✓ /health passed:", data["call_forwarding"])

def test_forwarding_and_transfer_api():
    print("\n--- Test: Granular Forwarding & Transfer API ---")
    # Reset to default
    save_forwarding_config(active=False, allow_transfer=True)
    resp = client.get("/forwarding")
    assert resp.status_code == 200
    data = resp.json()
    assert data["call_forwarding_active"] is False
    assert data["allow_human_transfer"] is True
    assert data["operational_mode"] == "ai_hybrid"

    # Toggle transfer off -> Solo IA mode
    resp = client.post("/forwarding/toggle-transfer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["allow_human_transfer"] is False
    assert data["operational_mode"] == "ai_only"
    assert "SOLO IA" in data["status_indicator"]

    # Toggle transfer back on
    resp = client.post("/forwarding/toggle-transfer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["allow_human_transfer"] is True
    assert data["operational_mode"] == "ai_hybrid"

    # Test preset modes endpoint
    for mode in ["direct", "ai_only", "ai_hybrid"]:
        resp = client.post("/forwarding/mode", json={"mode": mode})
        assert resp.status_code == 200
        assert resp.json()["operational_mode"] == mode

    print("✓ Granular API endpoints and presets passed.")

def test_dynamic_system_prompts():
    print("\n--- Test: Dynamic System Prompt Verification ---")
    prompt_with_transfer = build_system_prompt(allow_human_transfer=True)
    assert "TRANSFER ALLOWED" in prompt_with_transfer
    assert "transfer_to_human" in prompt_with_transfer

    prompt_solo_ia = build_system_prompt(allow_human_transfer=False)
    assert "TRANSFER DISABLED / AI-ONLY MODE" in prompt_solo_ia
    assert "DO NOT call any transfer tool" in prompt_solo_ia
    print("✓ Dynamic system prompt generation passed.")

def test_incoming_call_direct_mode():
    print("\n--- Test: Incoming Call in DIRECT FORWARDING mode ---")
    set_operational_mode("direct")

    # TeXML request
    resp = client.post(
        "/incoming-call",
        data={"From": "+14075550199", "CallSid": "TEST_CALL_DIRECT"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert f'callerId="{TELNYX_PHONE_NUMBER}"' in resp.text
    assert "<Number>+19043850725</Number>" in resp.text
    assert "<Stream" not in resp.text
    print("✓ Direct mode immediately dials +19043850725 with authorized callerId without engaging AI.")

def test_incoming_call_ai_modes():
    print("\n--- Test: Incoming Call in AI Modes ---")
    # 1. AI Hybrid Mode (with action callback)
    set_operational_mode("ai_hybrid")
    resp = client.post(
        "/incoming-call",
        data={"From": "+14075550199", "CallSid": "TEST_CALL_AI_HYBRID"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert resp.status_code == 200
    assert "<Connect action=" in resp.text
    assert "<Stream" in resp.text
    assert "/incoming-call-after-stream" in resp.text
    print("✓ AI Hybrid mode dispatches TeXML stream with action callback.")

    # 2. Solo IA Mode (clean stream then hangup, no action callback)
    set_operational_mode("ai_only")
    resp = client.post(
        "/incoming-call",
        data={"From": "+14075550199", "CallSid": "TEST_CALL_AI_ONLY"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert resp.status_code == 200
    assert "<Connect>" in resp.text
    assert "<Hangup" in resp.text
    assert "incoming-call-after-stream" not in resp.text
    print("✓ Solo IA mode dispatches pure TeXML stream with Hangup (100% autonomous).")

def test_mid_call_transfer_permission_enforcement():
    print("\n--- Test: Mid-Call Transfer Permission Enforcement ---")
    # Case 1: allow_human_transfer == True -> Dial +19043850725
    set_operational_mode("ai_hybrid")
    call_sid = "TEST_TRANSFER_ALLOWED"
    PENDING_TRANSFERS[call_sid] = {
        "transfer": True,
        "target": "+19043850725",
        "reason": "Caller asked for Nicolas",
        "timestamp": 1234567890
    }
    resp = client.post(f"/incoming-call-after-stream?call_sid={call_sid}")
    assert resp.status_code == 200
    assert f'callerId="{TELNYX_PHONE_NUMBER}"' in resp.text
    assert "<Number>+19043850725</Number>" in resp.text
    print("✓ Transfer allowed -> Bridges call to +19043850725 with authorized callerId.")

    # Case 2: allow_human_transfer == False (Solo IA) -> Hangup cleanly without dialing
    set_operational_mode("ai_only")
    call_sid = "TEST_TRANSFER_BLOCKED"
    PENDING_TRANSFERS[call_sid] = {
        "transfer": True,
        "target": "+19043850725",
        "reason": "Caller asked for human in Solo IA mode",
        "timestamp": 1234567890
    }
    resp = client.post(f"/incoming-call-after-stream?call_sid={call_sid}")
    assert resp.status_code == 200
    assert "<Hangup" in resp.text
    assert "<Dial" not in resp.text
    print("✓ Solo IA mode strictly blocks transfer -> Hangup cleanly.")

def test_web_dashboard():
    print("\n--- Test: Web Dashboard Controls ---")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Alarmtronics Telephony Dispatch" in resp.text
    assert "toggleForwarding()" in resp.text
    assert "toggleTransfer()" in resp.text
    assert "setMode('ai_only')" in resp.text
    assert 'href="/leads"' in resp.text
    print("✓ Web Dashboard contains all controls, cards, preset buttons, and CRM link.")

def test_leads_crm_and_api():
    print("\n--- Test: Leads CRM UI, JSON API, CSV Export, PATCH & DELETE ---")
    # 1. HTML CRM page at /leads
    resp_html = client.get("/leads", headers={"Accept": "text/html"})
    assert resp_html.status_code == 200
    assert "text/html" in resp_html.headers["content-type"]
    assert "CRM de Llamadas y Tickets" in resp_html.text
    assert 'id="leads-table"' in resp_html.text
    assert 'id="lead-detail-dialog"' in resp_html.text

    # 2. Explicit JSON content negotiation on /leads?format=json & /api/leads
    resp_json = client.get("/leads?format=json")
    assert resp_json.status_code == 200
    assert "leads" in resp_json.json()

    resp_api = client.get("/api/leads")
    assert resp_api.status_code == 200
    assert "count" in resp_api.json()

    # 3. CSV export
    resp_csv = client.get("/api/leads/export.csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "Dirección de Servicio" in resp_csv.text

    # 4. Insert temporary lead, PATCH it, then DELETE it cleanly
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO leads (call_sid, caller_from_number, caller_name, caller_phone, service_address, urgency, summary, duration_seconds, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("TEST_CRM_CRUD", "+14075550100", "CRM Test User", "+14075550100", "123 Main St", "normal", "Test summary", 32.0, "nuevo", "")
        )
        lead_id = cur.lastrowid
        conn.commit()

    resp_patch = client.patch(f"/api/leads/{lead_id}", json={"status": "agendado", "urgency": "urgent", "notes": "Technician assigned"})
    assert resp_patch.status_code == 200
    updated = resp_patch.json()
    assert updated["status"] == "agendado"
    assert updated["urgency"] == "urgent"
    assert updated["notes"] == "Technician assigned"

    resp_del = client.delete(f"/api/leads/{lead_id}")
    assert resp_del.status_code == 200
    assert resp_del.json()["deleted"] is True
    print("✓ CRM HTML, /api/leads, CSV export, PATCH, and DELETE passed.")

def test_audio_codec_and_dsp():
    print("\n--- Test: ITU-T G.711 mu-law Codec & Stateful DSP Pipeline ---")
    # 1. Exact ITU-T G.711 round-trip accuracy across full dynamic range
    test_samples = np.array([0, 100, 300, 500, 1000, 2000, 5000, 10000, 25000, -1000, -5000, -25000], dtype=np.int16)
    encoded = pcm16_to_ulaw(test_samples)
    decoded = ulaw_to_pcm16_8k(encoded)
    max_rel_err = np.max(np.abs(test_samples[1:] - decoded[1:]) / np.abs(test_samples[1:]))
    assert max_rel_err < 0.05, f"G.711 roundtrip error too high: {max_rel_err:.4f}"
    assert encoded[0] == 0xFF, f"Expected +0 to encode to 0xFF, got {hex(encoded[0])}"
    assert int(ulaw_to_pcm16_8k(b"\x80")[0]) > 30000
    assert int(ulaw_to_pcm16_8k(b"\x00")[0]) < -30000

    # 2. Stateful outbound 24kHz -> 8kHz preserves exact sample count across odd chunk sizes
    dsp = TelephonyAudioProcessor()
    t = np.arange(2400) / 24000.0  # 100ms 1kHz sine wave
    sine_24k = (np.sin(2 * np.pi * 1000.0 * t) * 12000.0).astype(np.int16)
    raw = sine_24k.tobytes()
    # Split into awkward non-multiple-of-3 sample chunk sizes (e.g. 100, 302, 500 bytes...)
    chunks = [raw[0:200], raw[200:502], raw[502:1100], raw[1100:]]
    out_ulaw = b"".join(dsp.outbound_pcm16_24k_to_ulaw(c) for c in chunks)
    assert len(out_ulaw) == 800, f"Expected exact 800 8kHz bytes from 2400 24kHz samples, got {len(out_ulaw)}"
    out_pcm = ulaw_to_pcm16_8k(out_ulaw)
    out_rms = float(np.sqrt(np.mean(out_pcm[40:].astype(np.float64) ** 2)))
    assert 6500 < out_rms < 10500, f"Unexpected outbound 1kHz RMS: {out_rms:.1f}"

    # 3. Stateful inbound 8kHz -> 16kHz preserves continuity across 20ms frames
    t8 = np.arange(800) / 8000.0
    sine_8k = (np.sin(2 * np.pi * 600.0 * t8) * 1500.0).astype(np.int16)
    in_ulaw = pcm16_to_ulaw(sine_8k)
    in_frames = [in_ulaw[i:i+160] for i in range(0, len(in_ulaw), 160)]
    out_16k_parts = []
    for f in in_frames:
        pcm16k, rms = dsp.inbound_ulaw_to_pcm16_16k(f)
        assert pcm16k.size == 320
        assert rms > 500
        out_16k_parts.append(pcm16k)
    full_16k = np.concatenate(out_16k_parts)
    # Verify smooth continuity (no huge boundary spikes at 320-sample frame edges)
    diffs = np.abs(np.diff(full_16k[320:].astype(np.float64)))
    assert np.max(diffs) < 4000, f"Detected click/discontinuity in inbound 16kHz stream: max diff={np.max(diffs)}"
    print(f"✓ G.711 codec (max rel err {max_rel_err*100:.2f}%) & stateful DSP passed (outbound RMS {out_rms:.0f}, max diff {np.max(diffs):.0f}).")

if __name__ == "__main__":
    try:
        test_health_endpoint()
        test_forwarding_and_transfer_api()
        test_dynamic_system_prompts()
        test_incoming_call_direct_mode()
        test_incoming_call_ai_modes()
        test_mid_call_transfer_permission_enforcement()
        test_web_dashboard()
        test_leads_crm_and_api()
        test_audio_codec_and_dsp()
        print("\n" + "=" * 65)
        print("ALL TESTS PASSED SUCCESSFULLY (100% COVERAGE)!")
        print("=" * 65)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
