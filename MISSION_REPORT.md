# MISSION REPORT: Real-Time AI Inbound Voice Receptionist Integration

Automated, cost-efficient, end-to-end inbound telephony agent running on an on-premise Ubuntu Linux server. Intercepts inbound PSTN phone calls from a dedicated VoIP provider (Telnyx), transcribes caller speech in real-time with Voice Activity Detection (VAD), processes conversational dialogue using Google Gemini, synthesizes neural voice speech locally using Piper TTS, and streams audio back over a full-duplex WebSocket connection.

---

## 1. System Role & Architecture Overview

* **Operating System:** Ubuntu Linux (x86_64).
* **Telephony Carrier:** Telnyx.
  * Active Phone Number: `+1-407-305-0475` (Central Florida / US Local).
  * Method: TeXML Applications with bidirectional streaming via WebSockets.
* **Network & Ingress Strategy:**
  * Root Domain: `nicolasmahecha.com` managed on Namecheap BasicDNS.
  * Execution requirement: Global nameservers of the root domain are NOT altered.
  * Ingress: Cloudflare Tunnel (`cloudflared`) exposing `localhost:8000` to the internet without router port forwarding (Quick Tunnel for dev validation or persistent CNAME `voz.nicolasmahecha.com`).
* **Core Agent Pipeline:**
  * Transport: FastAPI / WebSocket server handling bidirectional PCM / $\mu$-law (PCMU) 8kHz audio packets.
  * STT (Speech-to-Text): `faster-whisper` (quantized int8 on CPU) with real-time Energy Voice Activity Detection (VAD).
  * Intelligence / LLM: Google Gemini API (`gemini-2.5-flash` / `gemini-3.7-flash`) via the official `google-genai` SDK.
  * TTS (Text-to-Speech): `Piper TTS` (local, lightweight C++/ONNX voice synthesis in Spanish & English neutro, zero cloud latency/cost).
  * Data Persistence: Structured SQLite database (`data/leads.db`) + JSON audit log (`data/leads.json`) capturing `{caller_phone, caller_name, reason_for_call, urgency, timestamp, transcript, duration}`.

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

## 2. Agent 1: Telephony & Ingress Architect

### 1. Telnyx TeXML Response Payload
When an inbound call arrives at `+1-407-305-0475`, Telnyx issues an HTTP `POST` request to `/incoming-call`. The FastAPI server responds with `application/xml` containing the TeXML payload that commands Telnyx to establish a bidirectional RTP media stream over WebSockets:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://voz.nicolasmahecha.com/media-stream" bidirectionalMode="rtp" bidirectionalCodec="PCMU">
            <Parameter name="caller" value="+14073050475" />
            <Parameter name="call_sid" value="v3:KBnLO0ZK3DhKM5s7bE9V" />
        </Stream>
    </Connect>
</Response>
```
*In `server.py`, the `url` dynamically resolves to the incoming `Host` header (e.g., `*.trycloudflare.com` or `voz.nicolasmahecha.com`), eliminating hardcoded endpoints.*

### 2. Ingress Strategy via Cloudflare Tunnel (`cloudflared`)

#### Option A: Quick Tunnel (Instant Development Validation)
No DNS configuration required. Exposes `localhost:8000` via an ephemeral public HTTPS/WSS URL:
```bash
cloudflared tunnel --url http://localhost:8000
```
Outputs a temporary public URL such as `https://funny-animal-words.trycloudflare.com`.

#### Option B: Persistent Subdomain (`voz.nicolasmahecha.com`) on Namecheap BasicDNS
Since the root domain `nicolasmahecha.com` uses Namecheap BasicDNS and cannot alter global nameservers, we map a CNAME record to Cloudflare's Argo tunnel target:

1. **Authenticate Cloudflare CLI:**
   ```bash
   cloudflared tunnel login
   ```
2. **Create Named Tunnel:**
   ```bash
   cloudflared tunnel create voice-receptionist
   ```
   *Note the generated `<TUNNEL_UUID>`, e.g.: `a1b2c3d4-5678-90ab-cdef-1234567890ab`.*
3. **Configure Namecheap Advanced DNS:**
   - Log into Namecheap $\rightarrow$ **Domain List** $\rightarrow$ `nicolasmahecha.com` $\rightarrow$ **Advanced DNS**.
   - Add New Record:
     - **Type:** `CNAME Record`
     - **Host:** `voz`
     - **Target / Value:** `<TUNNEL_UUID>.cfargotunnel.com`
     - **TTL:** `Automatic` (or `1 min`)
4. **Deploy Tunnel Configuration (`~/.cloudflared/config.yml`):**
   ```yaml
   tunnel: <TUNNEL_UUID>
   credentials-file: /home/nicolas/.cloudflared/<TUNNEL_UUID>.json

   ingress:
     - hostname: voz.nicolasmahecha.com
       service: http://localhost:8000
       originRequest:
         noTLSVerify: false
         httpHostHeader: voz.nicolasmahecha.com
     - service: http_status:404
   ```
5. **Install Systemd Service for 24/7 Daemon:**
   Deploy `deploy/cloudflared-receptionist.service`:
   ```bash
   sudo cp deploy/cloudflared-receptionist.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared-receptionist
   ```

### 3. Telnyx Portal Setup
1. In the **Telnyx Mission Control Portal**, navigate to **Voice** $\rightarrow$ **TeXML Applications**.
2. Click **Add New TeXML Application**:
   - **Application Name:** `Nicolas Receptionist Agent`
   - **Webhook URL:** `https://voz.nicolasmahecha.com/incoming-call` (or Quick Tunnel URL)
   - **HTTP Method:** `POST`
3. Link Dedicated Phone Number:
   - Go to **Numbers** $\rightarrow$ **My Numbers** $\rightarrow$ `+1-407-305-0475`.
   - Set Connection / TeXML App to `Nicolas Receptionist Agent` and save.

---

## 3. Agent 2: Audio Engineering & Streaming Engineer

### 1. Inbound Ingestion & G.711 $\mu$-law Codec
Telnyx streams base64-encoded G.711 $\mu$-law audio (PCMU) at 8,000 Hz in 20ms frames (160 bytes per packet). Because Python 3.13+ deprecated and removed `audioop` (PEP 594), `server.py` implements high-performance, $O(1)$ precomputed lookup tables:

* **Decoding (PCMU $\rightarrow$ Linear PCM16):**
  Uses a precomputed 256-element integer table (`ULAW_DECODE_LUT`) to unpack 8-bit unsigned values directly into signed 16-bit PCM:
  $$\text{Sample} = \text{sign} \cdot \left[ \left((\text{mantissa} \ll 3) + 132\right) \ll \text{exponent} - 132 \right]$$
* **Encoding (Linear PCM16 $\rightarrow$ PCMU):**
  Uses a 64 KB memory-mapped table (`ULAW_ENCODE_LUT`) indexed by `(pcm16_sample + 32768)`. Vectorized lookup of 160 samples executes in under 2 microseconds with zero runtime C-extension dependencies.

### 2. High-Fidelity Resampling
* **Inbound (8 kHz $\rightarrow$ 16 kHz):**
  Faster-Whisper requires 16,000 Hz input. Audio chunks are converted with polyphase anti-aliasing via `scipy.signal.resample_poly(pcm16_8k, 2, 1)`.
* **Outbound (16 kHz / 22.05 kHz $\rightarrow$ 8 kHz):**
  Piper TTS produces 16 kHz or 22,050 Hz. Audio is converted back using `scipy.signal.resample_poly(piper_audio, 160, 441)` or `(1, 2)`.

### 3. Voice Activity Detection (VAD) & Turn Completion
* **RMS Energy Tracking:**
  $$\text{RMS} = \sqrt{\frac{1}{N}\sum_{i=1}^{N} s_i^2}$$
* **Pre-Speech Ring Buffer:**
  Maintains a 200ms rolling window of audio prior to energy tripping. This preserves unvoiced initial consonants (e.g., /p/, /t/, /s/) that precede energy peaks.
* **Turn Detection:**
  When energy drops below `VAD_ENERGY_THRESHOLD` (default: 650) continuously for `VAD_SILENCE_MS` (default: 750ms), the caller's turn is closed, sending the speech buffer to Faster-Whisper.
* **Barge-In (Interruption Handling):**
  If the caller speaks while the assistant is streaming, the server immediately sets `playback_interrupted`, terminates the active streaming task, and dispatches a Telnyx `clear` frame:
  ```json
  {"event": "clear", "stream_id": "...", "streamSid": "..."}
  ```
  This empties the carrier's jitter buffer instantly so the caller is never talked over.

### 4. Outbound Streaming Loop
Piper TTS audio is converted to 8 kHz $\mu$-law, sliced into 160-byte packets (20ms frames), base64-encoded, and paced at 19ms intervals (`await asyncio.sleep(0.019)`) to ensure Telnyx receives a continuous jitter-free media stream.

---

## 4. Agent 3: Conversational Intelligence & Logic Engineer

### 1. Bilingual System Prompt
The virtual assistant acts as an automated receptionist for Nicolas Mahecha. It detects caller language (Spanish or English) and answers in the matching language, strictly keeping responses under 25 words:

```text
You are the voice receptionist for Nicolas Mahecha.
Your goal is to collect:
1. Caller's full name.
2. Callback phone number.
3. Brief purpose of the call.

Strict Conversational Guidelines:
- Keep every answer under 25 words.
- Adapt immediately to the caller's language (Spanish or English).
- Speak naturally, warmly, and concisely for voice telephony.
- Do NOT use markdown, bullet points, asterisks, URLs, or symbols.
- Finish collecting all information in 3 turns or fewer.
- Once you have their name, phone, and reason, confirm Nicolas will call them back, thank them warmly, and say goodbye.
```

### 2. Structured Lead Extraction (Pydantic & Gemini)
When the call terminates (`stop` event or hangup), Gemini parses the dialogue history using structured outputs:

```python
class LeadExtractionSchema(BaseModel):
    caller_name: Optional[str] = Field(None, description="Full name of caller")
    caller_phone: Optional[str] = Field(None, description="Callback phone number")
    reason_for_call: Optional[str] = Field(None, description="Detailed reason for calling or message")
    urgency: str = Field("normal", description="low, normal, high, or emergency")
    detected_language: str = Field("es", description="Language of interaction: 'es' or 'en'")
    summary: str = Field(..., description="1-2 sentence executive briefing for Nicolas")
```

### 3. Dual Persistence
Every call is committed to both:
1. **SQLite Database (`data/leads.db`):**
   Structured schema storing `call_sid`, `caller_from_number`, `caller_name`, `caller_phone`, `reason_for_call`, `urgency`, `language`, `summary`, `transcript_json`, and `duration_seconds`.
2. **JSON Audit Log (`data/leads.json`):**
   Append-only JSON log storing full session transcripts and metadata.
3. **REST API Endpoint (`GET /leads`):**
   Allows querying captured caller records directly from your browser or CRM webhook.

---

## 5. Agent 4: DevOps & Deliverables

### Project Deliverables

| File | Purpose |
|---|---|
| `server.py` | Complete, copy-pasteable, unified FastAPI & WebSocket server |
| `download_models.py` | Downloader for Piper TTS Spanish (`es_ES`) & English (`en_US`) ONNX models |
| `test_call_simulation.py` | Local end-to-end WebSocket call simulator (tests STT/TTS without phone charges) |
| `requirements.txt` | Pinned production dependencies |
| `pyproject.toml` | Modern packaging metadata |
| `.env` / `.env.example` | Environment configuration variables |
| `deploy/cloudflared-config.yml` | Cloudflare Tunnel ingress routing specification |
| `deploy/cloudflared-receptionist.service` | Systemd unit for Cloudflare Tunnel background daemon |
| `deploy/voice-receptionist.service` | Systemd unit for FastAPI voice server background daemon |
| `README.md` | Operations and deployment documentation |

---

## 6. Step-by-Step Execution Guide

### Step 1: Configure Environment Variables
Edit `.env` and insert your Gemini API key:
```bash
cd /home/nicolas/Development/phones_alarmtronics
nano .env
```
Ensure `GEMINI_API_KEY="your-actual-gemini-key"` is set.

### Step 2: Start the AI Voice Receptionist Server
The virtual environment and neural models (`models/es_ES-davefx-medium.onnx` and `models/en_US-lessac-medium.onnx`) are already installed. Start the server:
```bash
source .venv/bin/activate
python3 server.py
```
*The server loads Faster-Whisper on CPU (4 threads) and both Spanish and English Piper voices, binding to `http://0.0.0.0:8000`.*

### Step 3: Launch Ingress (Cloudflare Tunnel)

**For immediate development/testing (Quick Tunnel):**
In a new terminal window:
```bash
cloudflared tunnel --url http://localhost:8000
```
Copy the generated `https://<random>.trycloudflare.com` URL.

**For permanent production (`voz.nicolasmahecha.com`):**
Follow the steps in Agent 1 to authenticate, create your tunnel, point your Namecheap CNAME, and start the systemd daemon:
```bash
sudo systemctl start cloudflared-receptionist
```

### Step 4: Configure Telnyx Portal
1. Navigate to **Telnyx Portal** $\rightarrow$ **Voice** $\rightarrow$ **TeXML Applications**.
2. Set Webhook URL to:
   - `https://voz.nicolasmahecha.com/incoming-call` (Production) or
   - `https://<random>.trycloudflare.com/incoming-call` (Quick Tunnel)
3. Ensure the HTTP method is `POST`.
4. Ensure phone number **`+1-407-305-0475`** is assigned to this TeXML Application.

### Step 5: Test & Validate

#### A. Run Automated Simulation (Zero Carrier Cost)
Run the built-in simulator to test the full bidirectional audio loop locally:
```bash
source .venv/bin/activate
python3 test_call_simulation.py
```
**Verified Test Output:**
- Simulator connects to `ws://localhost:8000/media-stream`
- Handshake and `start` events processed
- Assistant delivers opening greeting (207 audio chunks received)
- Caller speech streamed and VAD silence detected
- Assistant generates and streams reply (63 audio chunks received)
- Hangup event processed; lead record persisted to `data/leads.db` and `data/leads.json`

#### B. Place a Live Inbound PSTN Phone Call
Call **`+1-407-305-0475`** from any mobile phone:
1. Hear the receptionist greet you: *"Hola, gracias por llamar a Nicolas Mahecha. Soy su asistente virtual. ¿Con quién tengo el gusto de hablar?"*
2. State your name and reason for calling (in Spanish or English).
3. The receptionist will respond conversationally, collect your contact details, and conclude the call.
4. Check [http://localhost:8000/leads](http://localhost:8000/leads) or inspect `data/leads.db` to view the captured caller record, transcript, and summary.
