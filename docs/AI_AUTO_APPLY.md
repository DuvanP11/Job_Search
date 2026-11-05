# AI Auto Apply

Agente de empleo personal integrado en el portal (`/autoaplicar`). Busca vacantes, las evalúa contra tu perfil,
prepara tus documentos, completa formularios y —solo si tú lo autorizas— envía la postulación y verifica que el portal la confirmó.

## Flujo

```
DISCOVERY → MATCHING → DOCUMENTOS → AUTORIZACIÓN → ENVÍO (navegador) → CONFIRMACIÓN → SEGUIMIENTO
```

| Etapa | Dónde | Notas |
|---|---|---|
| Descubrimiento | `autoapply/adapters/` | Greenhouse, Lever, Ashby, SmartRecruiters (APIs públicas JSON); ElEmpleo y Computrabajo (páginas públicas, con pausa y respetando `robots.txt`) |
| Matching | `autoapply/matching.py` | Requisito por requisito (cumplido/parcial/no cumplido/desconocido). Los excluyentes son filtros independientes del puntaje |
| Perfil | `autoapply/profile.py` | PDF/DOCX/TXT → perfil editable. Todo dato de la IA se contrasta con el texto del CV. Campos: verificado / inferido / pendiente |
| Documentos | `autoapply/documents.py` | CV a la medida + carta (PDF/DOCX). Solo reorganiza datos del perfil; la IA redacta y su salida se valida |
| Autorización | `autoapply/autorizacion.py` | Manual por oferta (se invalida si cambian los documentos) o reglas del modo autónomo |
| Envío | `autoapply/browser/formulario.py` | Playwright. Dry-run por defecto |
| Cola / worker | `autoapply/cola.py`, `pipeline.py`, `worker.py` | Reintentos con espera, recuperación tras caídas, sin tareas duplicadas |

## Modos

* **Manual**: solo encuentra y evalúa.
* **Asistido** (por defecto): prepara documentos y formulario; tú autorizas cada envío (`Cola → Autorizar envío`).
* **Autónomo**: apagado hasta activarlo en `Auto Apply` (escribir `ACTIVAR` + casilla). Envía solo lo que cumple **todas** tus reglas:
  compatibilidad mínima, máximo diario, fuentes, empresas permitidas/excluidas, horario, vigencia, sin excluyentes, sin duplicados, portal con envío verificable.

## Qué NUNCA hace

* Responder preguntas legales, médicas, demográficas, migratorias o de autorización de trabajo, ni aceptar consentimientos/términos (`security.es_pregunta_sensible`, evaluado **antes** de cualquier mapeo de campos).
* Resolver o evadir CAPTCHA, MFA o inicio de sesión: se detiene y la tarea pasa a "requiere tu intervención".
* Marcar "confirmada" sin una señal positiva del portal (URL de confirmación o texto + formulario ausente). Pulsar Enviar sin confirmación = `enviada_sin_confirmacion`; si la validación del navegador frena el envío = error.
* Inventar datos: contacto solo desde campos que marcaste "es correcto"; un campo obligatorio desconocido detiene el proceso.
* Enviar de verdad sin el interruptor del operador `AUTOAPPLY_ENABLE_SUBMIT=1` (sin él solo rellena, verifica y guarda capturas).

## Puesta en marcha

```bash
pip install -r requirements.txt -r requirements-worker.txt -r requirements-dev.txt
python -m playwright install chromium
python app.py                       # web  → http://localhost:5000/autoaplicar/panel
python -m autoapply.worker          # worker (proceso aparte; --una-vez para cron)
pytest                              # 190+ pruebas (incluye Chromium real contra ATS simulados)
```

Variables de entorno relevantes:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | Firma de sesiones. **Obligatoria en producción** (si falta, se usa una aleatoria por proceso y se registra un error) |
| `DATABASE_URL` | PostgreSQL compartido por web y worker. Con JSON local el candado de archivo cubre varios procesos en la misma máquina |
| `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TOKEN` | IA local/remota (prioridad gratuita) |
| `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Proveedores opcionales; nunca se guardan en la base |
| `AI_PROVIDER_ORDER` | Orden de proveedores, p. ej. `ollama,openrouter` |
| `AUTOAPPLY_ENABLE_SUBMIT=1` | **Habilita el envío real** (solo en el worker) |
| `AUTOAPPLY_DATA_DIR`, `AUTOAPPLY_INTERVALO_SEG` | Carpeta de datos / pausa del worker |
| `AUTOAPPLY_BUSQUEDA=cola\|directo` | Dónde se hace «Buscar ahora». Por defecto `cola` en Vercel (la petición muere a los 60 s) y `directo` en local |
| `ENABLE_DEBUG_ENDPOINTS=1` | Reactiva `/debug/storage` (apagado por defecto) |

### Dónde corre el worker

Vercel (serverless) **no puede** ejecutar Playwright ni procesos largos: allí solo corre la web. El worker debe correr en tu Mac,
un VPS o Railway (el `Procfile` ya declara el proceso `worker`), apuntando al mismo `DATABASE_URL`. La web solo encola y consulta: «Buscar ahora» crea una tarea `descubrir` en la cola y el worker la ejecuta (resultado en `/autoaplicar/cola`).
Sin `DATABASE_URL`, web y worker deben compartir `AUTOAPPLY_DATA_DIR` en la misma máquina.

## Seguridad y privacidad

CSRF en todas las acciones del módulo; sesiones por usuario y aislamiento de datos; `/admin/reset-all` eliminado;
validación de URL contra SSRF (también dentro del navegador); capturas de evidencia servidas solo desde la carpeta del propio usuario;
`Privacidad` permite **exportar** (ZIP) y **eliminar** todos tus datos del módulo. Las contraseñas de portales, si se usan, se cifran con Fernet (`utils/credentials.py`).

## Estado de las fuentes

| Fuente | Búsqueda | Envío automatizado |
|---|---|---|
| Greenhouse | API pública (verificado en vivo) | Sí (formulario embebido; se detiene ante preguntas sensibles/CAPTCHA) |
| Lever | API pública (verificado en vivo) | Sí, pero Lever suele exigir hCaptcha → normalmente quedará "requiere tu intervención" |
| Ashby, SmartRecruiters | API pública (verificado en vivo) | No (postulación manual) |
| ElEmpleo | Páginas públicas (verificado en vivo) | No (requiere cuenta) |
| Computrabajo | Funciona desde `www.computrabajo.com.co`; sin empresa/descripción | No |
| LinkedIn, Indeed, otros | No disponible: sus condiciones prohíben automatizar | No |

## Limitaciones conocidas

* Los formularios de Greenhouse con selectores personalizados (País, Escuela, Título…) quedan para el usuario salvo que guardes una respuesta en `respuestas_guardadas` del perfil.
* Nunca se envió una postulación real durante el desarrollo: el envío se probó contra formularios locales y se contrastó la detección de campos con un formulario real de Greenhouse en modo solo lectura.
  La primera postulación real conviene hacerla en modo asistido, mirando la captura del dry-run.
* El puntaje es un indicador de afinidad, no una probabilidad de contratación.
* CSRF cubre el módulo de autoaplicar; los formularios de login/registro/credenciales del portal original aún no lo tienen.

## Decisiones de arquitectura

* **Extender, no reescribir**: se reutilizaron `Store`, `utils/cv_builder.py` (DOCX), `utils/credentials.py`, el blueprint y los estilos existentes.
* **Referencias** (`docs/INVESTIGACION_REFERENCIAS.md`): confirmación por señal positiva y puerta de aprobación (Instaply, job-application-agent), gates excluyentes (CareerPulse), fallback de proveedores de IA (JobNavigator). Descartado: solvers de CAPTCHA, modo stealth y el repo sin licencia.
* **Reglas antes que IA**: filtros, validaciones y seguridad son determinísticos; la IA solo extrae y redacta, siempre con validación posterior y alternativa sin IA.
* **Cola en el mismo almacén** (JSON con flock o PostgreSQL con `FOR UPDATE`) para no añadir infraestructura (Redis/Celery) a un proyecto de un solo usuario por despliegue.
