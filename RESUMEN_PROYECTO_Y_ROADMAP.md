# RESUMEN DEL PROYECTO Y ESTADO ACTUAL: RECEPCIONISTA VIRTUAL AI (ALARMTRONICS)

**Última Actualización:** 7 de Noviembre, 2026  
**Línea Telefónica Activa (Telnyx):** `+1 (407) 305-0475` (Florida Central)  
**Número Destino de Desvío / Transferencia (Nicolas):** `+1 (904) 385-0726`  
**Dominio Público / Panel Web / Webhook:** `https://voz.nicolasmahecha.com`  
**WebSocket Media Stream:** `wss://voz.nicolasmahecha.com/media-stream`  
**Servidor de Producción (GCP):** `35.255.35.187` (usuario: `nicolasmelectronic`)  
**Empresa:** Alarmtronics (Sistemas de Alarma Contra Incendios y Seguridad/Intrusión)  
**Repositorio GitHub:** `https://github.com/nicolasmd1985/alarmtronics-receptionist.git`  
**Docker Hub Image:** `nicolasmd/alarmtronics-receptionist:latest`  

---

## 1. Arquitectura Actual en Producción (Gemini Live API + Control de Desvío)

El sistema opera con **Google Gemini Live API (`gemini-3.1-flash-live-preview` sobre API `v1beta`)**, procesando voz a voz bidireccional en tiempo real con voz neural (`Aoede`) y gestionando 3 modos operativos intercambiables en caliente desde el panel web `https://voz.nicolasmahecha.com/`.

### Modos Operativos Disponibles

1. **Modo 3 — Solo IA Autónoma 100% (`ai_only`) [ACTIVO Y VERIFICADO EN VIVO]:**
   - La recepcionista virtual IA atiende el 100% de la llamada entrante.
   - Recopila paso a paso: Nombre completo, Problema de la alarma, Dirección de la propiedad y Teléfono de contacto.
   - Despide cordialmente al cliente, cuelga automáticamente al concluir (`<Hangup />` / cierre de WebSocket) y guarda el ticket estructurado en SQLite (`data/leads.db`) y JSON (`data/leads.json`).
   - **Sin transferencias:** Aunque el cliente pida hablar con un humano, la IA le explica cortésmente que registrará todos sus datos prioritarios para el supervisor sin transferir la llamada.

2. **Modo 2 — IA Híbrida con Transferencia a Humano (`ai_hybrid`):**
   - La IA contesta automáticamente la llamada.
   - Si el cliente solicita hablar con Nicolas, soporte o un humano, la IA anuncia una frase de cortesía, invoca la herramienta `transfer_to_human`, cierra el stream y Telnyx ejecuta el callback `action` de `<Connect>` hacia `/incoming-call-after-stream` para enlazar la llamada mediante `<Dial callerId="+14073050475">` hacia `+19043850725`.

3. **Modo 1 — Desvío Directo Manual (`direct`):**
   - Toda llamada entrante al `+14073050475` puentea por completo la IA y responde inmediatamente con TeXML `<Dial callerId="+14073050475" timeout="25"><Number>+19043850725</Number></Dial>` para contestar manualmente en el teléfono `+19043850725`.

---

## 2. Hitos, Diagnóstico y Problemas Resueltos (Actualización 7 de Noviembre, 2026)

### A. Implementación de Estado Persistente y Panel de Control Web (`data/config.json`)
- Se implementó persistencia atómica en `data/config.json` con los campos `call_forwarding_active`, `allow_human_transfer`, `forward_to_number` (`+19043850725`) y `updated_at`.
- Se añadieron endpoints REST en `server.py`:
  - `GET /forwarding`: Consulta del estado y modo operativo actual.
  - `POST /forwarding/mode`: Selección directa de modo (`direct`, `ai_hybrid`, `ai_only`).
  - `POST /forwarding/toggle`: Alternancia rápida de desvío directo.
  - `POST /forwarding/toggle-transfer`: Alternancia del permiso de transferencia a humano por la IA.
  - `POST /dial-status`: Webhook de diagnóstico para registrar el resultado (`DialCallStatus` y `DialSipResponseCode`) de cualquier `<Dial>` en Telnyx.
  - `POST /incoming-call-after-stream`: Webhook post-stream para ejecutar la transferencia en caliente en modo híbrido.
- Se actualizó el Dashboard en `https://voz.nicolasmahecha.com/` con botones de modo rápido e interruptores en tiempo real.

### B. Causa Raíz y Solución del Fallo `HTTP 404` en Gemini Live WebSocket
- **Síntoma:** Al realizar llamadas tras los primeros despliegues del día, Telnyx colgaba inmediatamente al intentar conectar con la IA.
- **Diagnóstico en el servidor GCP (`35.255.35.187`):** Al inspeccionar `docker logs alarmtronics-receptionist`, se detectó que al modificarse `requirements.txt` se invalidó la caché de Docker y se instaló `google-genai 3.0.0` (en lugar de `2.33.0`). En `google-genai 3.0.0`, el SDK cambió el `api_version` por defecto de `v1beta` a `v1`. Como el endpoint WebSocket `BidiGenerateContent` de Gemini Live solo existe en `v1beta`, Google rechazaba la conexión con `HTTP 404` en los primeros 30ms.
- **Solución Aplicada:**
  1. Se configuró explícitamente `http_options={"api_version": "v1beta"}` al inicializar `genai.Client` en `server.py`.
  2. Se fijó `google-genai==2.33.0` en `requirements.txt`.
  3. Se actualizó la extracción de `call_sid` en el evento `start` del WebSocket para leer `custom_parameters["call_sid"]`, garantizando trazabilidad completa del ID de llamada de Telnyx.

### C. Corrección de Flujo TeXML para Solo IA, IA Híbrida y Desvío
- **Modo Solo IA (`ai_only`):** Devuelve `<Connect><Stream .../></Connect><Hangup />` sin redirecciones intermedias y con `tools=None`.
- **Modo IA Híbrida (`ai_hybrid`):** Utiliza el atributo nativo `<Connect action=".../incoming-call-after-stream" method="POST">` en lugar de un `<Redirect>` posterior a `<Connect>` (ya que en TeXML `<Stream>` es asíncrono y un `<Redirect>` hermano se ejecutaba prematuramente).
- **Modo Desvío (`direct`):** Incluye explícitamente `callerId="+14073050475"` y `<Number>+19043850725</Number>` dentro de `<Dial>`.

---

## 3. Verificación de Llamadas Reales en Producción

### Prueba en Vivo — 7 de Noviembre, 2026 (18:03 UTC)
- **Origen:** `+1 (689) 249-0957` (Nicolas) $\rightarrow$ `+1 (407) 305-0475`
- **Modo Activo:** `Solo IA` (`ai_only`)
- **Desarrollo de la Llamada:**
  1. Recepción de saludo pre-renderizado instantáneo e interrupción natural (*Barge-In*) detectada correctamente.
  2. Captura de nombre (`Nicolas`), problema (`alarm is dead`), dirección (`223 Orlando Avenue`) y teléfono de retorno.
  3. Despedida automática de la IA y desconexión limpia tras 61.0 segundos y 9 turnos (`[AUTO HANGUP]`).
  4. Extracción estructurada con `gemini-flash-lite-latest` (`HTTP 200 OK`) y almacenamiento en `/app/data/leads.db` y `/app/data/leads.json`.

---

## 4. Guía para Continuar y Probar el Desvío de Llamadas (`+19043850725`)

Cuando retomes las pruebas para validar el **Modo Desvío Directo (`direct`)** y la **Transferencia en Modo Híbrido (`ai_hybrid`)**, sigue esta lista de verificación:

### Paso 1: Verificar el "Outbound Voice Profile" en el Portal de Telnyx (Requisito de Carrier)
Cuando Telnyx responde con `<Connect><Stream>`, solo recibe audio entrante y no requiere perfil saliente. Sin embargo, cuando Telnyx ejecuta `<Dial><Number>+19043850725</Number></Dial>`, Telnyx origina una **llamada saliente PSTN** nueva hacia `+19043850725`.
1. Ingresa a **Telnyx Mission Control Portal** $\rightarrow$ **Voice** $\rightarrow$ **TeXML Applications**.
2. Edita la aplicación asignada al número `+1-407-305-0475` (`Nicolas Receptionist Agent`).
3. En la sección **Outbound** $\rightarrow$ **Outbound Voice Profile**, verifica que tenga seleccionado un **Outbound Voice Profile** activo (no `None`).
4. En **Voice** $\rightarrow$ **Outbound Voice Profiles**, confirma que ese perfil tenga permitidas las llamadas salientes a **United States / North America (+1)**.

### Paso 2: Probar el Modo Desvío Directo (`direct`)
1. Abre `https://voz.nicolasmahecha.com/` y haz clic en el botón **1. Desvío Directo (Manual)** (o ejecuta `curl -X POST https://voz.nicolasmahecha.com/forwarding/mode -H "Content-Type: application/json" -d '{"mode":"direct"}'`).
2. Llama al `+1 (407) 305-0475`.
3. Revisa en tiempo real el resultado del `<Dial>` en el servidor GCP:
   ```bash
   ssh -i ~/.ssh/id_ed25519 nicolasmelectronic@35.255.35.187 docker logs -f --tail 30 alarmtronics-receptionist
   ```
   - Si el teléfono `+19043850725` timbra y contestas, verás `[DIAL STATUS CALLBACK] Status: completed`.
   - Si Telnyx rechaza la llamada saliente por configuración de cuenta/perfil, el nuevo webhook `/dial-status` mostrará exactamente el código SIP (`SIP Code: 403 / D49 / etc.`) en `[DIAL STATUS CALLBACK]`.

### Paso 3: Probar el Modo IA Híbrida (`ai_hybrid`)
1. En `https://voz.nicolasmahecha.com/`, selecciona **2. IA + Transferir a Humano**.
2. Llama al `+1 (407) 305-0475` y cuando la IA conteste, dile: *"Please transfer me to Nicolas"* o *"Can I speak to a human?"*.
3. La IA anunciará la transferencia, cerrará el stream de voz y Telnyx ejecutará `/incoming-call-after-stream` marcando al `+19043850725`.

---

## 5. Comandos Rápidos de Operación y Mantenimiento

### Ver logs en vivo en el servidor GCP
```bash
ssh -i ~/.ssh/id_ed25519 nicolasmelectronic@35.255.35.187 docker logs -f --tail 50 alarmtronics-receptionist
```

### Verificar estado de salud y modo activo
```bash
curl -s https://voz.nicolasmahecha.com/health
curl -s https://voz.nicolasmahecha.com/forwarding
```

### Ejecutar la suite de pruebas automatizadas localmente
```bash
.venv/bin/python3 test_forwarding_and_endpoints.py
```

### Desplegar cambios pendientes a GitHub / Docker Hub
```bash
git push origin main
```
