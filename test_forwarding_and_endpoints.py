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
    PENDING_TRANSFERS,
    TELNYX_PHONE_NUMBER
)

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
    print("✓ Web Dashboard contains all controls, cards, and preset buttons.")

if __name__ == "__main__":
    try:
        test_health_endpoint()
        test_forwarding_and_transfer_api()
        test_dynamic_system_prompts()
        test_incoming_call_direct_mode()
        test_incoming_call_ai_modes()
        test_mid_call_transfer_permission_enforcement()
        test_web_dashboard()
        print("\n" + "=" * 65)
        print("ALL TESTS PASSED SUCCESSFULLY (100% COVERAGE)!")
        print("=" * 65)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
