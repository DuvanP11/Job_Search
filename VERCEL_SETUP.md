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

Ten en cuenta el límite de tiempo: `vercel.json` fija `maxDuration` en 60
segundos, y generar un CV con un modelo grande puede tardar más.

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

## Otros proveedores

El repositorio conserva `Procfile`, `nixpacks.toml` y `runtime.txt`, así que
sigue desplegando en Railway sin cambios. Allí el disco es persistente y
`utils/selenium_scraper.py` sí puede usarse.
