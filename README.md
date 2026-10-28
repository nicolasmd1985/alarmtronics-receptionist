# Real-Time AI Inbound Voice Receptionist Integration

Automated, cost-efficient, end-to-end inbound telephony agent running on an on-premise Ubuntu Linux server. Intercepts inbound PSTN phone calls from Telnyx, transcribes caller speech in real-time with Voice Activity Detection (VAD), processes conversational dialogue using Google Gemini, synthesizes neural voice speech locally using Piper TTS, and streams audio back over full-duplex WebSockets.

---

## Architecture Overview

```
                      +---------------------------------------+
                      | PSTN Caller: Mobile / Landline Phone  |
                      +-------------------+-------------------+
                                          |
                                          v (Inbound Call)
                               +----------+----------+
                               |  Telnyx Carrier     |
                               |  +1-407-305-0475    |
                               +----------+----------+
                                          |
       1. HTTP POST Webhook               | 2. TeXML Connect Stream
       /incoming-call                     |    wss://<DOMAIN>/media-stream
                                          v
                      +-------------------+-------------------+
                      |   Cloudflare Tunnel (cloudflared)     |
                      |   voz.nicolasmahecha.com / quick      |
                      +-------------------+-------------------+
                                          |
                                          v (localhost:8000)
       +----------------------------------+----------------------------------+
       |                  FastAPI / WebSocket Audio Gateway                  |
       |                                                                     |
       |  [Inbound: PCMU 8kHz] ---> [G.711 Decode] ---> [Resample to 16kHz]  |
       |                                                       |             |
       |                                                       v             |
       |                                                [Energy VAD Engine]  |
       |                                                       |             |
       |                                                       v             |
       |                                             [faster-whisper STT]    |
       |                                                       |             |
       |                                                       v (Transcript)|
       |                                           [Google Gemini 2.5 Flash] |
       |                                                       |             |
       |                                                       v (Reply Text)|
       |                                                [Piper Neural TTS]   |
       |                                                       |             |
       |  [Outbound: PCMU 8kHz] <-- [G.711 Encode] <-- [Resample to 8kHz]    |
       +----------------------------------+----------------------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      |        Persistence & Insights         |
                      |   - SQLite (data/leads.db)            |
                      |   - JSON Log (data/leads.json)        |
                      |   - Structured Extraction (Pydantic)  |
                      +---------------------------------------+
```

---

## Directory Structure

```
phones_alarmtronics/
├── server.py                   # Main FastAPI & WebSocket telephony server
├── download_models.py          # Asset downloader for Piper TTS voices
├── test_call_simulation.py     # Local end-to-end WebSocket call simulator
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Build & dependency metadata
├── .env.example                # Environment configuration template
├── .env                        # Active local configuration (contains GEMINI_API_KEY)
├── deploy/
│   ├── cloudflared-config.yml  # Cloudflare Tunnel routing configuration
│   ├── cloudflared-receptionist.service  # Systemd unit for Cloudflare Tunnel
│   └── voice-receptionist.service        # Systemd unit for FastAPI server
├── models/                     # Neural speech models (es_ES and en_US)
│   ├── es_ES-davefx-medium.onnx
│   ├── es_ES-davefx-medium.onnx.json
│   ├── en_US-lessac-medium.onnx
│   └── en_US-lessac-medium.onnx.json
└── data/                       # Structured storage
    ├── leads.db                # SQLite database of captured caller leads
    └── leads.json              # Appended JSON audit log of call transcripts
```

---

## Quick Start & Verification

### 1. Set your Gemini API Key
Edit `.env` and paste your key:
```bash
GEMINI_API_KEY="AIzaSy..."
```

### 2. Verify Models
Piper models are already downloaded into `models/`. If needed:
```bash
source .venv/bin/activate
python3 download_models.py
```

### 3. Run the Server
```bash
source .venv/bin/activate
python3 server.py
```

### 4. Run the Local Telephony Simulator
In another terminal, simulate a real call without using phone credits:
```bash
source .venv/bin/activate
python3 test_call_simulation.py
```
Observe the assistant deliver the greeting, receive speech, detect silence, synthesize audio, and save the lead to `data/leads.db`!

---

## Ingress Setup (Cloudflare Tunnel)

### Option A: Zero-Config Quick Tunnel (Development)
Exposes `localhost:8000` via a temporary `trycloudflare.com` URL:
```bash
cloudflared tunnel --url http://localhost:8000
```
Outputs:
```
https://random-words.trycloudflare.com
```
Use this URL in Telnyx:
- Webhook: `https://random-words.trycloudflare.com/incoming-call`

### Option B: Subdomain Mapping on Namecheap (`voz.nicolasmahecha.com`)
Keep Namecheap BasicDNS as authoritative nameservers without changing them:

1. **Authenticate Cloudflare Tunnel**:
   ```bash
   cloudflared tunnel login
   ```
2. **Create the Tunnel**:
   ```bash
   cloudflared tunnel create voice-receptionist
   ```
   Note the generated `<TUNNEL_UUID>`.

3. **Namecheap DNS Record**:
   - Go to Namecheap -> Domain List -> `nicolasmahecha.com` -> **Advanced DNS**.
   - Add CNAME Record:
     - **Type:** `CNAME Record`
     - **Host:** `voz`
     - **Target:** `<TUNNEL_UUID>.cfargotunnel.com`
     - **TTL:** `Automatic` (or `1 min`)

4. **Configure Tunnel**:
   Update `~/.cloudflared/config.yml` with your `<TUNNEL_UUID>` (see `deploy/cloudflared-config.yml`).

5. **Start Daemon**:
   ```bash
   sudo cp deploy/cloudflared-receptionist.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared-receptionist
   ```

---

## Telnyx TeXML Application Configuration

1. Log in to [Telnyx Mission Control Portal](https://portal.telnyx.com/).
2. Navigate to **Voice** -> **TeXML Applications**.
3. Click **Add New TeXML Application**:
   - **Application Name:** `Nicolas Receptionist Agent`
   - **Webhook URL:** `https://voz.nicolasmahecha.com/incoming-call` (or your Quick Tunnel URL)
   - **HTTP Method:** `POST`
4. Assign Phone Number:
   - Go to **Numbers** -> **My Numbers**.
   - Locate `+1-407-305-0475`.
   - Edit settings: assign Connection to `Nicolas Receptionist Agent`.
   - Click **Save**.

---

## Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Operational dashboard with live telemetry and diagnostics |
| `GET` | `/health` | Health check probe (STT, TTS, LLM status) |
| `POST` | `/incoming-call` | Telnyx TeXML Webhook dispatching `<Connect><Stream>` |
| `WS` | `/media-stream` | Full-duplex Telnyx PCMU 8kHz audio WebSocket stream |
| `GET` | `/leads` | JSON API returning all captured caller leads |
