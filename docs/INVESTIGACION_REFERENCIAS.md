# Investigación de repos de referencia (Fase 2)

Lectura dirigida del código (clones superficiales, sin ejecutar nada), 2026-11-05. Los conectores no se probaron contra sitios en vivo.

| Repo | Licencia | Qué aporta de verdad | Promesa del README no cumplida |
|---|---|---|---|
| A vesaias/JobNavigator | MIT | Dedup (`scraper/_shared/dedup.py`), cliente LLM multi-proveedor con fallback (`analyzer/llm_client.py`), `bot_wall.py`, 13 conectores ATS | Auto-fill solo en extensión; **nunca envía** |
| B tcpsyn/CareerPulse | MIT | Rúbrica ponderada con tope duro (`app/matcher.py`), cola prepare→review→approve (`routers/queue.py`) | "Auto-fills any ATS": son 5 adaptadores; detección de envío por texto, débil; claves de IA en claro |
| C ShipItAndPray/job-apply-ai | MIT declarado, **sin archivo LICENSE** | Solo Greenhouse operativo (`greenhouse-pull.cjs`) | Marca `submitted` al hacer clic sin verificar; `src/` sin conectar. **Descartado** |
| D Aditya-00a/Instaply | MIT (producto SaaS) | Mejor detección de confirmación (`instaply/actions.py:258`), puerta de aprobación (`application_review_gate.py`), verificación por correo, cliente Ollama | Autofill monolítico de 9.500 líneas; usa `playwright-stealth` (no se adopta) |
| E vaibhavarora14/job-application-agent | MIT | Regla "filled ≠ applied", ledger idempotente, bloqueos absolutos (CAPTCHA/MFA/legal/demográficos), scoring determinista con gates | Parte de la seguridad es instrucción al LLM, no código; solver de CAPTCHA (apagado) |

## Decisiones

| Idea | Origen | Decisión |
|---|---|---|
| Confirmación por señal positiva (URL/texto); sin señal = no enviado | D, E | Adaptar (Fase 10) |
| Estados pending→approved→submitted | D, B | Adaptar (ya existe `pendiente_revision`) |
| Gates excluyentes independientes del puntaje | E, B | **Hecho**: `autoapply/matching.py` |
| Fallback entre proveedores de IA | A | **Hecho**: `autoapply/ai/` |
| Greenhouse/Lever/Ashby por API JSON pública | D, C | Reutilizar la idea (Fase 6) |
| Bloqueo absoluto de preguntas sensibles | E | Adaptar (Fase 10) |
| CAPTCHA/MFA: detener y pedir humano; **sin solvers ni stealth** | E | Adoptar la política, descartar el código |
| Secretos en almacén del SO | E | Python: Fernet ya existe en `utils/credentials.py` |
| Multi-tenant, billing, telemetría | A, D, E | Descartar |
