# RESUMEN DEL PROYECTO Y ROADMAP: RECEPCIONISTA VIRTUAL AI (ALARMTRONICS)

**Fecha:** 27 de Octubre, 2026  
**Línea Telefónica Activa:** `+1-407-305-0475` (Telnyx - Florida Central)  
**Dominio / Webhook Ingress:** `https://voz.nicolasmahecha.com`  
**Empresa:** Alarmtronics (Sistemas de Alarma Contra Incendios y Seguridad/Intrusión)  

---

## 1. Resumen de lo Construido Hoy

Se diseñó, programó y puso en producción un sistema telefónico con Inteligencia Artificial autónoma que atiende llamadas de la red telefónica pública (PSTN) en tiempo real, interactúa de forma conversacional con el cliente en inglés, extrae los datos del incidente de alarma y guarda un ticket estructurado para el técnico de servicio.

### Diagrama del Flujo en Tiempo Real

```
[ Cliente Llama: +1-407-305-0475 ]
               │
               ▼
[ Carrier: Telnyx Programmable Voice (TeXML) ]
               │ Webhook HTTP POST (/incoming-call)
               ▼
[ Cloudflare Tunnel: voz.nicolasmahecha.com ]
               │ Redirección segura a localhost:8000
               ▼
[ Servidor FastAPI / WebSocket: /media-stream ]
               │
               ├──> 1. Inbound Audio PCMU 8kHz
               ├──> 2. Decodificación G.711 µ-law & Resampling a 16kHz
               ├──> 3. VAD (Detección de voz/silencio por RMS Energy)
               ├──> 4. faster-whisper (Transcripción STT en ~300ms en CPU)
               ├──> 5. Google Gemini (gemini-flash-lite-latest en ~0.6s)
               ├──> 6. Piper TTS (Síntesis de voz neural en ~100ms)
               └──> 7. Outbound Audio PCMU 8kHz streaming full-duplex con Barge-In
               │
[ Al colgar la llamada ]
               │
               └──> Gemini analiza la transcripción completa y guarda el ticket
                    en SQLite (data/leads.db) y JSON (data/leads.json)
```

---

## 2. Problemas Técnicos Superados Hoy

1. **Python 3.14 (PEP 594 - Eliminación de `audioop`):**
   - En Python 3.13+, la librería nativa `audioop` ya no existe.
   - *Solución:* Se programaron tablas de búsqueda NumPy $O(1)$ precalculadas para codificación y decodificación ITU-T G.711 $\mu$-law, logrando rendimiento C sin dependencias externas.

2. **Telefonía Telnyx ("Wireless mobile is not available"):**
   - El número estaba asignado inicialmente a un SIP Trunk.
   - *Solución:* Se creó una aplicación TeXML en el portal de Telnyx vinculada al número telefónico y apuntando a `https://voz.nicolasmahecha.com/incoming-call`.

3. **Dominio e Ingress Seguro sin Tocar la Web Actual:**
   - El dominio `nicolasmahecha.com` tenía su sitio web principal activo.
   - *Solución:* Se configuró Cloudflare Tunnel (`cloudflared`) mapeando exclusivamente el subdominio `voz.nicolasmahecha.com` hacia `localhost:8000`, preservando intactos todos los registros A, MX y de correo de la página web existente.

4. **Latencia en CPU Intel Core i5-4210U (2 cores / 4 threads):**
   - El modelo Whisper `base` demoraba 25 segundos por turno en CPU.
   - *Solución:* Se integró `faster-whisper` modelo `tiny` con cuantización `int8`, reduciendo la transcripción a solo **~300ms**. Se utilizó `Piper TTS` en local (ONNX runtime), logrando sintetizar audio en **~100ms** con cero costo de nube.

5. **Resolución Definitiva del Bucle / Loop y Error 503:**
   - La API de Gemini arrojaba `503 Service Unavailable (high demand)` en modelos pesados, activando un mensaje por defecto genérico que hacía parecer que el bot olvidaba la conversación.
   - *Solución:*
     - Se migró a **`gemini-flash-lite-latest`**, logrando respuestas en **0.66 segundos** de forma 100% estable.
     - Se actualizó el saludo inicial para pedir Nombre y Problema de entrada:
       > *"Thank you for calling Alarmtronics. I am your virtual receptionist. Could you please provide your name and tell me what issue you are experiencing with your alarm system today?"*
     - Se implementó un **Fallback Determinístico Anti-Bucle**: si Gemini o la red fallaran, el bot analiza qué información ya proporcionó el cliente (Nombre/Problema $\rightarrow$ Dirección $\rightarrow$ Teléfono $\rightarrow$ Confirmación) y nunca repite una pregunta ya contestada.
     - Se añadió `turn_lock` asíncrono para evitar procesamiento concurrente desordenado ante pausas breves al hablar.
     - Se eliminó el `initial_prompt` de Whisper y se agregó un filtro de limpieza de alucinaciones repetitivas.

---

## 3. Estructura de Archivos del Proyecto

```
/home/nicolas/Development/phones_alarmtronics/
├── .env                              # Credenciales (Gemini API Key, modelo, puertos, teléfono)
├── server.py                         # Servidor principal FastAPI, WebSockets, STT, LLM, TTS, DB
├── download_models.py                # Script de descarga de voces Piper (EN / ES)
├── test_call_simulation.py           # Simulador local de llamadas telefónicas por WebSockets
├── requirements.txt                  # Dependencias de Python
├── data/
│   ├── leads.db                      # Base de datos SQLite con tickets de servicio
│   └── leads.json                    # Registro histórico en formato JSON
├── models/
│   ├── en_US-lessac-medium.onnx      # Modelo de voz neural en inglés
│   ├── en_US-lessac-medium.onnx.json # Configuración de voz en inglés
│   ├── es_ES-davefx-medium.onnx      # Modelo de voz neural en español
│   └── es_ES-davefx-medium.onnx.json # Configuración de voz en español
└── deploy/
    ├── cloudflared-config.yml        # Configuración del túnel de Cloudflare
    ├── cloudflared-receptionist.service # Servicio systemd para el túnel
    └── voice-receptionist.service    # Servicio systemd para el servidor FastAPI
```

---

## 4. Guía Rápida de Comandos para Mañana

### Verificar que todo esté funcionando
```bash
# 1. Probar el endpoint de salud público
curl -s https://voz.nicolasmahecha.com/health

# 2. Ver las llamadas y leads guardados en SQLite
sqlite3 data/leads.db "SELECT id, caller_name, caller_phone, issue_description, service_address, created_at FROM leads ORDER BY id DESC LIMIT 5;"
```

### Iniciar o reiniciar el servidor manualmente
```bash
cd /home/nicolas/Development/phones_alarmtronics
source .venv/bin/activate
python3 server.py
```

### Probar una llamada simulada sin usar minutos de teléfono
```bash
source .venv/bin/activate
python3 test_call_simulation.py
```

### Dejar los servicios corriendo en segundo plano automáticamente (Systemd)
Si deseas que el recepcionista y el túnel arranquen solos al encender la PC:
```bash
sudo cp deploy/cloudflared-receptionist.service /etc/systemd/system/
sudo cp deploy/voice-receptionist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-receptionist.service
sudo systemctl enable --now voice-receptionist.service
```

---

## 5. Roadmap: Mejoras Propuestas para Mañana

| # | Mejora Propuesta | Beneficio |
|---|-------------------|-----------|
| **1** | **Notificaciones SMS / Email Instantáneas** | En cuanto el cliente cuelga y se guarda el lead, enviar un SMS o Email al técnico de turno con el resumen del problema, dirección y teléfono para devolución de llamada inmediata. |
| **2** | **Dashboard Web de Control de Tickets** | Una interfaz web sencilla y elegante (ej. en `voz.nicolasmahecha.com/dashboard`) donde el personal de Alarmtronics pueda ver en vivo los tickets creados, reproducir el audio o leer la transcripción, marcar como "Atendido", y exportar a Excel. |
| **3** | **Soporte Bilingüe Automático (Inglés / Español)** | Si el cliente responde en español ("Hola, mi alarma está sonando"), el sistema detecta el idioma en tiempo real y cambia a la voz en español de Piper (`es_ES-davefx-medium`), respondiendo de forma nativa en español. |
| **4** | **Integración con Google Sheets / CRM** | Sincronización automática de cada fila de lead con una hoja compartida de Google Sheets o webhook hacia el software de despacho de Alarmtronics. |
| **5** | **Optimización de Fonética para Códigos de Alarma** | Ajustar el prompt para reconocer marcas específicas (Honeywell, DSC, Ademco, Bosch, Silent Knight, Fire-Lite) y modelos de panel comunes. |
