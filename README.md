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

## Call Forwarding & Operational Presets (+19043850725)

The system supports hot-swapping between 3 operational modes in real time:

1. **Modo 1: Desvío Directo Manual (`mode: direct`):**
   - Incoming calls to `+1 (407) 305-0475` ring directly on Nicolas's phone (`+19043850725`).
   - You answer manually. AI is completely bypassed and WebSockets are not connected.
2. **Modo 2: IA Híbrida con Transferencia (`mode: ai_hybrid`):**
   - The AI virtual receptionist answers automatically.
   - **Solo si el cliente pide hablar con un humano o con Nicolas**, la IA anuncia una frase de cortesía y transfiere la llamada activa en vivo al `+19043850725`.
   - Si no pide transferencia, la IA recopila los datos del cliente, guarda el ticket y concluye la llamada normalmente.
3. **Modo 3: Solo IA Autónoma 100% (`mode: ai_only`):**
   - La IA atiende el 100% de la llamada y registra toda la información en SQLite y JSON.
   - **Transferencia estrictamente deshabilitada:** Aunque el cliente pida hablar con un humano, la IA le informa cortésmente que registrará todos sus datos para que el equipo lo contacte, sin transferir la llamada.

### Control Options:
1. **Web Dashboard:** Visita `https://voz.nicolasmahecha.com/` (o `http://localhost:8000/`) y usa los botones de modo rápido o los interruptores individuales.
2. **Interactive Console Keyboard:**
   - Presiona `f` + Enter $\rightarrow$ Alterna Desvío Directo Inmediato.
   - Presiona `t` + Enter $\rightarrow$ Alterna Permisos de Transferencia IA (Permitida <-> Solo IA).
   - Presiona `s` + Enter $\rightarrow$ Muestra el estado actual.
3. **CLI Commands:**
   ```bash
   python3 server.py --status           # Ver estado actual
   python3 server.py --mode direct      # Modo 1: Desvío Manual Directo
   python3 server.py --mode ai_hybrid   # Modo 2: IA + Transferencia a Humano
   python3 server.py --mode ai_only     # Modo 3: Solo IA (100% Autónoma)
   python3 server.py --transfer-on      # Permitir transferencias por IA
   python3 server.py --transfer-off     # Desactivar transferencias por IA (Solo IA)
   ```

---

## Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Operational dashboard with live telemetry and visual forwarding toggle |
| `GET` | `/health` | Health check probe (Gemini Live & Call Forwarding status) |
| `GET` | `/forwarding` | Returns current forwarding config and status badge |
| `POST` | `/forwarding/toggle` | Toggles call forwarding on/off in real time |
| `POST` | `/incoming-call` | Telnyx Inbound Webhook (TeXML `<Dial>` if active, `<Connect><Stream>` if AI) |
| `POST` | `/incoming-call-after-stream` | TeXML post-stream redirect (handles mid-call transfer or hangup) |
| `WS` | `/media-stream` | Full-duplex Telnyx PCMU 8kHz audio WebSocket stream |
| `GET` | `/leads` | JSON API returning all captured caller leads |
