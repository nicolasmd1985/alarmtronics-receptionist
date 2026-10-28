# RESUMEN DEL PROYECTO Y ESTADO ACTUAL: RECEPCIONISTA VIRTUAL AI (ALARMTRONICS)

**Fecha de Actualización:** 28 de Octubre, 2026  
**Línea Telefónica Activa:** `+1 (407) 305-0475` (Telnyx TeXML - Florida Central)  
**Dominio Público / Webhook:** `https://voz.nicolasmahecha.com`  
**WebSocket Media Stream:** `wss://voz.nicolasmahecha.com/media-stream`  
**Empresa:** Alarmtronics (Sistemas de Alarma Contra Incendios y Seguridad/Intrusión)  
**Repositorio GitHub:** `https://github.com/nicolasmd1985/alarmtronics-receptionist.git`  
**Docker Hub Image:** `nicolasmd/alarmtronics-receptionist:latest`  

---

## 1. Arquitectura Actual en Producción (Opción B: Gemini Live API)

El sistema opera con **Google Gemini Live API (`gemini-3.1-flash-live-preview`)**, procesando voz a voz bidireccional en tiempo real con una latencia promedio de **~1.2 segundos** y voz neural de alta fidelidad (`Aoede`).

### Diagrama del Flujo en Tiempo Real

```
[ Cliente Llama: +1-407-305-0475 ]
               │
               ▼
[ Carrier: Telnyx Programmable Voice (TeXML) ]
               │ Webhook HTTP POST (/incoming-call)
               ▼
[ Cloudflare Tunnel: voz.nicolasmahecha.com ]
               │ Redirección segura a 127.0.0.1:8000
               ▼
[ Contenedor Docker: alarmtronics-receptionist ]
               │
               ├──> 1. Saludo Instantáneo (data/greeting.ulaw - 0ms latencia)
               ├──> 2. Decodificación ITU-T G.711 µ-law y Resampling a 16kHz
               ├──> 3. Supresión de Eco Acústico del Altavoz (RMS > 900 para Barge-In)
               ├──> 4. Google Gemini Live API (gemini-3.1-flash-live-preview)
               │       - Transcripción de entrada (caller transcription)
               │       - Generación directa de audio PCM 24kHz
               │       - Bucle multi-turno continuo (receive_from_gemini)
               ├──> 5. Decimación exacta 3:1 (24kHz -> 8000Hz) & Codificación µ-law
               └──> 6. Transmisión RTP a Telnyx en paquetes de 20ms (160 bytes)
               │
[ Al colgar la llamada ]
               │
               └──> Gemini Flash Lite analiza la transcripción completa
                    y guarda el ticket estructurado en SQLite (data/leads.db)
                    y auditoría JSON (data/leads.json)
```

---

## 2. Hitos y Problemas Resueltos Hoy

### A. Migración Exitosa a Gemini Live Multimodal
- Se reemplazó la cadena tradicional (Whisper STT + Gemini Flash + Piper TTS) por la API nativa de voz **Gemini Live**, eliminando desfasajes fonéticos y permitiendo interacción fluida de voz natural con la voz neural `Aoede`.

### B. Saludo Pre-renderizado sin Colisión de WebSockets
- Se generó el archivo de audio telefónico nativo `data/greeting.ulaw` (73,004 bytes = 9.13s de audio limpio PCMU a 8kHz).
- Esto evita enviar comandos de texto iniciales al socket en vivo mientras el micrófono telefónico transmite ruido ambiental, eliminando el error `1011 keepalive ping timeout`.

### C. Resolución del Bug Multi-Turno (Silencio tras el Turno 1)
- **Causa Raíz 1:** En el SDK `google-genai`, el generador `live_ws.receive()` ejecuta un `break` automático al finalizar cada turno (`turn_complete=True`). Al no tener un bucle exterior, la tarea receptora moría al terminar la primera respuesta. Se implementó un bucle persistente `while not s.is_closing: async for response in live_ws.receive(): ...` que atiende infinitos turnos sin desconectarse.
- **Causa Raíz 2:** Se eliminó el `await asyncio.sleep(0.09)` del emisor de audio (`gemini_audio_pusher`), evitando acumulación de colas y retrasos acumulativos.
- **Causa Raíz 3:** Se corrigió la inicialización de tareas asociándolas a la instancia `session` recién creada tras el evento `event: "start"` de Telnyx, eliminando el fallo `AttributeError: 'NoneType' object has no attribute 'is_closing'`.

### D. Supresión de Eco Acústico y Soporte para Interrupciones (Barge-In)
- Se programó un filtro de umbral RMS (900): si el asistente está hablando y el usuario no interrumpe con voz fuerte, el retorno del altavoz al micrófono es suprimido para no generar eco ni auto-interrupciones en Gemini. Si el usuario habla con energía, se limpia el buffer y el modelo se interrumpe inmediatamente.

### E. Contenedorización Completa con Docker
- **Dockerfile:** Imagen optimizada en `python:3.12-slim` (~250MB) con dependencias mínimas requeridas.
- **docker-compose.yml:** Servicio `voice-receptionist` mapeando `127.0.0.1:8000:8000`, montando volumen persistente `./data:/app/data` y con healthcheck automático sobre `/health`.
- Se configuró con política de reinicio `unless-stopped` para ejecución **24/7**.

### F. Automatización CI/CD con GitHub Actions
- Archivo de flujo de trabajo `.github/workflows/deploy.yml` idéntico al estándar del servidor de `nicolasmahecha.com`.
- Pasos automatizados:
  1. Compilación de imagen Docker con Docker Buildx y push a Docker Hub (`nicolasmd/alarmtronics-receptionist:latest`).
  2. Conexión segura por SSH al servidor.
  3. Generación automática del archivo `.env.production` a partir de los Secrets de GitHub (`GEMINI_API_KEY`, `TELNYX_PHONE_NUMBER`, etc.).
  4. Despliegue con `docker compose pull` y `docker compose up -d`.

---

## 3. Verificación de la Última Prueba Real en Vivo

En la llamada de prueba realizada por el usuario al `+1 (407) 305-0475`:
- **Cliente:** Julian
- **Problema Reportado:** No puede desarmar el sistema y la sirena sigue sonando activa.
- **Dirección de Servicio:** 8011 Michigan Avenue, Kissimmee, Florida.
- **Teléfono de Retorno:** 407-312-1222.
- **Turnos Totales:** 7 turnos fluidos con confirmación de despacho.
- **Resultado en Base de Datos (SQLite & JSON):** Ticket guardado con ID #26, clasificado como `urgency: emergency` y resumen generado con éxito.

---

## 4. Estructura de Archivos del Repositorio

```
/home/nicolas/Development/phones_alarmtronics/
├── .env                              # Variables locales de entorno
├── .env.example                      # Plantilla de variables para CI/CD
├── .gitignore                        # Reglas de exclusión de Git
├── Dockerfile                        # Imagen Docker en python:3.12-slim
├── docker-compose.yml                # Orquestación de contenedor y volumen de datos
├── requirements.txt                  # Dependencias de Python mínimas
├── server.py                         # Servidor principal FastAPI / WebSockets / Gemini Live
├── RESUMEN_PROYECTO_Y_ROADMAP.md     # Documento de contexto y estado actual
├── .github/
│   └── workflows/
│       └── deploy.yml                # Pipeline CI/CD GitHub Actions
└── data/
    ├── greeting.ulaw                 # Audio pre-renderizado del saludo en PCMU 8kHz
    ├── leads.db                      # Base de datos SQLite persistente con tickets
    └── leads.json                    # Registro cronológico en formato JSON
```

---

## 5. Guía de Comandos Rápidos para Mañana

### Verificar que el contenedor esté corriendo y saludable
```bash
docker compose ps
curl -s http://127.0.0.1:8000/health
```

### Ver los logs en vivo de las llamadas telefónicas
```bash
docker logs -f --tail 50 alarmtronics-receptionist
```

### Consultar los últimos tickets de servicio capturados
```bash
sqlite3 data/leads.db "SELECT id, timestamp, caller_name, caller_phone, service_address, reason_for_call, urgency FROM leads ORDER BY id DESC LIMIT 5;"
```

### Reiniciar o reconstruir el contenedor tras cambios en el código
```bash
docker compose up -d --build
```

---

## 6. Próximos Pasos Sugeridos para Mañana

1. **Notificación SMS / Email al Técnico:**
   - Integrar envío inmediato de notificación (por webhook, Telnyx SMS o email SMTP/SendGrid) cada vez que se guarde un ticket con urgencia `urgent` o `emergency`.
2. **Dashboard Web de Despacho:**
   - Crear una interfaz web visual en `/leads` o `/dashboard` para que el equipo de despacho pueda ver tickets en tiempo real, filtrar por urgencia y marcarlos como "Despachado" o "Atendido".
3. **Soporte Bilingüe Dinámico:**
   - Aprovechar las capacidades nativas de Gemini 3.1 Flash Live para alternar fluidamente entre inglés y español si el cliente inicia la conversación en español.
