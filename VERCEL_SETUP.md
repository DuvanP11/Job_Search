# 🚀 Despliegue en Vercel

Guía para publicar el portal en Vercel. **Los pasos 1 y 2 no son opcionales**:
sin ellos la aplicación arranca pero nadie puede registrarse ni iniciar sesión.

## Por qué hace falta configurar algo

Vercel ejecuta la aplicación como funciones *serverless*. Eso cambia dos reglas
respecto a un servidor normal:

1. **El disco es de solo lectura.** Guardar usuarios en `data/users.json` no
   funciona. Hace falta una base de datos.
2. **Cada petición puede atenderla un proceso distinto.** Lo que se guarde en
   una variable de Python desaparece antes de la siguiente petición. Por eso
   el CV, el caché de búsquedas y los códigos de recuperación viven en
   PostgreSQL (ver `utils/kv_store.py`).

---

## 1. Crear la base de datos

En el panel de Vercel: **Storage → Create Database → Postgres**.

Al vincularla al proyecto, Vercel define `DATABASE_URL` automáticamente. Si usas
otro proveedor (Neon, Supabase, Railway), copia su cadena de conexión y créala a
mano en el paso siguiente.

Las tablas se crean solas la primera vez que arranca la aplicación.

## 2. Definir las variables de entorno

En **Settings → Environment Variables**:

| Variable | Valor | Obligatoria |
|---|---|---|
| `DATABASE_URL` | La cadena de conexión de PostgreSQL | **Sí** |
| `SECRET_KEY` | Una cadena larga y aleatoria | **Sí** |
| `OLLAMA_URL` | URL de un Ollama accesible por internet | No |
| `OLLAMA_MODEL` | `llama3.1` | No |

Para generar la `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> ⚠️ La `SECRET_KEY` firma las cookies de sesión. Si alguien la conoce, puede
> entrar como cualquier usuario. No la subas al repositorio ni la reutilices.

## 3. Desplegar

Con el repositorio importado en Vercel, cada push a `main` despliega solo. El
preset **Flask** y el `vercel.json` del repositorio ya traen la configuración.

## 4. Comprobar que quedó bien

```bash
curl https://TU-PROYECTO.vercel.app/health
```

Y en los *runtime logs* de Vercel debe aparecer:

```
🗄️ KV store usando PostgreSQL
🔍 DATABASE_URL detectada - usando PostgreSQL
```

Si en su lugar ves `❌ FALTA DATABASE_URL`, la variable no llegó: revísala y
vuelve a desplegar.

---

## Qué funciona y qué no

| Función | Estado en Vercel |
|---|---|
| Registro, login, perfil | ✅ Con `DATABASE_URL` |
| Búsqueda de empleos | ✅ Usa HTTP, no navegador |
| Exportar a Excel | ✅ |
| Mejorar CV: formato ATS | ✅ |
| Mejorar CV: reescritura con IA | ⚠️ Solo con `OLLAMA_URL` |
| Credenciales de portales | ✅ Con `DATABASE_URL` |
| `utils/selenium_scraper.py` | ❌ Excluido del despliegue |

### Sobre la IA del CV

Ollama corre en tu equipo, y Vercel no puede alcanzar `localhost`. Sin
`OLLAMA_URL`, el botón **Mejorar mi CV** sigue funcionando en *modo básico*:
reorganiza el CV y aplica todo el formato ATS, pero no reescribe el texto. La
interfaz lo indica.

Para conectarlo, sigue la sección siguiente.

---

## Conectar Ollama con la aplicación desplegada

### Por qué hace falta un proxy

Ollama **no tiene autenticación**. Publicarlo tal cual en internet permite a
cualquiera generar texto con tu equipo, listar tus modelos o borrarlos.

`scripts/ollama_proxy.py` se pone delante: exige un token en la cabecera
`Authorization` y solo deja pasar `/api/tags`, `/api/generate`, `/api/chat` y
`/api/embeddings`. Los endpoints que modifican el equipo (`/api/delete`,
`/api/pull`) quedan bloqueados.

### Instalar cloudflared

El túnel publica el proxy sin abrir puertos en el router:

```bash
curl -sL -o /tmp/cf.tgz https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz
tar xzf /tmp/cf.tgz -C /tmp && mkdir -p ~/.local/bin && mv /tmp/cloudflared ~/.local/bin/
```

En Mac con Intel, cambia `darwin-arm64` por `darwin-amd64`.

### Levantarlo

Con la aplicación Ollama abierta:

```bash
./scripts/exponer_ollama.sh
```

El script arranca el proxy, abre el túnel e imprime las tres variables que hay
que configurar. **Deja esa terminal abierta**: al cerrarla se cae el túnel.

### Configurar el proyecto

En **Settings → Environment Variables**, y volver a desplegar:

| Variable | Valor |
|---|---|
| `OLLAMA_URL` | La URL que imprime el script |
| `OLLAMA_TOKEN` | El token que imprime el script |
| `OLLAMA_MODEL` | `llama3.1` |

### Elegir el modelo por el tiempo, no por la calidad

`vercel.json` fija `maxDuration` en 60 segundos y la petición se corta ahí.
Medido sobre el mismo CV:

| Modelo | Tiempo | ¿Cabe en 60 s? |
|---|---|---|
| `llama3.1` | ~33 s | Sí |
| `qwen3:14b` | ~91 s | **No** |

Con un CV largo, `llama3.1` puede acercarse al límite. Si empiezas a ver
tiempos de espera agotados, instala un modelo más pequeño:

```bash
ollama pull llama3.2
```

### Limitaciones de este montaje

- **La URL es temporal.** `trycloudflare.com` asigna una distinta en cada
  arranque, así que hay que actualizar `OLLAMA_URL` y volver a desplegar. Para
  una URL fija hace falta una cuenta de Cloudflare con un dominio propio y
  crear un túnel con nombre.
- **Depende de tu equipo.** Si se apaga, se suspende o pierde la conexión, la
  aplicación sigue funcionando pero en modo básico.
- **La velocidad la pone tu equipo**, y lo comparten todos los usuarios de la
  web: dos peticiones a la vez tardan más.

Si necesitas que la IA funcione siempre, sin depender de tu equipo, lo
apropiado es una API alojada en lugar de Ollama.

### Sobre el scraper con Selenium

`utils/selenium_scraper.py` necesita Chrome, que no existe en serverless. Está
excluido en `.vercelignore` y **ningún módulo de la aplicación lo importa**, así
que la búsqueda no se ve afectada: `utils/scraper.py` consulta los portales por
HTTP. Para usarlo en local: `pip install selenium==4.16.0`.

---

## Desarrollo local

Nada de esto es necesario para trabajar en local. Sin `DATABASE_URL`, la
aplicación usa los archivos JSON de `data/` y guarda el estado en memoria, igual
que antes:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
FLASK_ENV=development .venv/bin/python app.py
```

Abre http://localhost:5000

## Problemas conocidos del build

### `The Python request from .python-version resolved to Python 3.11.9, which is incompatible with ==3.12.*`

Vercel construye con Python 3.12, pero el repositorio trae un `.python-version`
con `3.11.9` para el entorno local y para Railway. `uv` lo lee y aborta.

Ya está resuelto: `.python-version` figura en `.vercelignore`, así que no llega
al build. Si el error reaparece, comprueba que esa línea sigue ahí.

### Las páginas responden 404

Puede pasar si se añade un `rewrite` de `/(.*)` hacia `/app.py` en
`vercel.json`. El preset **Flask** ya enruta todas las peticiones al módulo, y
el rewrite haría que Flask reciba la ruta `/app.py` en lugar de la original. El
`vercel.json` del repositorio solo define `maxDuration` y `memory` por eso.

## Otros proveedores

El repositorio conserva `Procfile`, `nixpacks.toml` y `runtime.txt`, así que
sigue desplegando en Railway sin cambios. Allí el disco es persistente y
`utils/selenium_scraper.py` sí puede usarse.
