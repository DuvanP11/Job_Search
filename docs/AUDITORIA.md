# Auditoría de Job_Search (Fase 1)

Fecha: 2026-11-05 · Base: `main` @ 9c543d5 · Todo lo siguiente se verificó leyendo el código, no los README.

## Arquitectura actual

- **Stack**: Flask 3 (monolito de `app.py`, 1.390 líneas) + plantillas Jinja/Bootstrap, Python 3.14 en el venv local.
- **Persistencia**: `utils/database.py` (SQLAlchemy/PostgreSQL si hay `DATABASE_URL`, JSON si no) y `utils/kv_store.py` para sesiones/búsquedas.
- **Despliegue**: Vercel (`vercel.json`, serverless), Railway/Procfile y nixpacks como alternativas. En serverless no hay navegador ni procesos largos.
- **IA**: solo `utils/cv_bot.py` (Ollama, remoto vía `scripts/ollama_proxy.py` con token). No hay capa de proveedores.
- **Búsqueda original**: `utils/scraper.py` (Computrabajo/Magneto/etc., ~970 líneas) y `utils/selenium_scraper.py` (ElEmpleo; no se importa en producción).
- **Credenciales de portales**: `utils/credentials.py`, cifradas con Fernet.

## Módulo `autoapply/` ya existente (~2.500 líneas, PRs #9–#11)

| Pieza | Estado real |
|---|---|
| `routes.py` (blueprint `/autoapply`) | Funciona: perfil, candidato, CV, descubrir, ofertas, preparar, cambio de estado. Requiere login. |
| `storage.py` | JSON por usuario o PostgreSQL; clave única por `owner_id`+huella. Sólido. |
| `adapters/` | Computrabajo, ElEmpleo, Greenhouse, Lever: **solo búsqueda**. Greenhouse/Lever raspan HTML en vez de usar sus APIs JSON públicas. `postular()` devuelve siempre "intervención humana". |
| `scoring.py` | Heurística de palabras clave (0–100). No evalúa requisitos excluyentes por título, ni experiencia, ni educación, y no explica requisito por requisito. |
| `dedupe.py` | Huella por URL y por empresa+cargo. Correcto. |
| `runner.py` / `worker.py` | Modos simulación/revisión/automático, límite diario. El worker es un bucle `time.sleep`, sin cola ni reintentos ni recuperación. |
| Pruebas | **Ninguna** antes de esta rama. |

## Defectos encontrados

1. **CRÍTICO — `/admin/reset-all`**: público (sin sesión), contraseña `reset2025` escrita en el código y mostrada como "Hint" en la propia página; borraba todos los usuarios. **Eliminado en esta rama.**
2. **CRÍTICO (integridad) — envío simulado**: en modo `automatico`, el runner marcaba la oferta `enviada_sin_confirmacion` sin llamar nunca a `adapter.postular()`. Contradice la regla de no simular postulaciones. **Corregido**: solo se marca postulada si el adaptador envió; `postulacion_confirmada` exige confirmación del adaptador.
3. **ALTO — SSRF por subcadena**: `validar_url_aplicacion` comparaba subcadenas (`'10.'` bloqueaba cualquier URL con "10." y no detectaba `[::1]`, `172.16/12`, `.internal`). **Corregido** con `urlparse` + `ipaddress`.
4. MEDIO — `SECRET_KEY` con valor por defecto inseguro si falta la variable (hoy solo avisa). Pendiente: fallar al arrancar en producción.
5. MEDIO — sin protección CSRF en los formularios POST. Pendiente (Flask-WTF o token propio).
6. MEDIO — `/debug/storage` expone rutas del servidor a cualquier usuario logueado. Pendiente: restringir a admin.
7. BAJO — `requirements.txt` sin Playwright, pytest ni dependencias de IA.

## Puntos de extensión que se reutilizarán (no se reescribe)

- Blueprint `autoapply_bp` y su almacén `Store` (colecciones nuevas: `preferences`, `documents`, `applications`, `agent_logs`, `ai_providers`).
- Registro `adapters.REGISTRO` para nuevos conectores y ATS.
- `utils/cv_bot.py` como primer proveedor (Ollama) detrás de la futura capa de proveedores.
- `utils/credentials.py` (Fernet) para secretos de portales y claves de IA.
- Navegación: `templates/index.html:97` y `dashboard.html:108` ya enlazan a `autoapply.index`.

## Restricciones de despliegue que condicionan el diseño

Vercel serverless **no puede** ejecutar Playwright ni workers de larga duración. Por eso el motor de envío con navegador debe correr como proceso aparte (local o Railway/VM) leyendo una cola persistida en el mismo `Store`; la web solo encola y consulta. Es la separación que ya sugiere `worker.py`.
