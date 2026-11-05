# 🚀 Portal de Empleos Colombia - Sistema Selenium

Portal web con **login REAL** usando Selenium para búsqueda sin bloqueos.

## 🤖 AI Auto Apply

Agente de empleo personal: busca vacantes en fuentes reales, las evalúa contra tu perfil, prepara CV y carta a la medida,
completa formularios y —con tu autorización— envía y verifica la confirmación. Empieza en `/autoaplicar/panel`.
Documentación completa: [`docs/AI_AUTO_APPLY.md`](docs/AI_AUTO_APPLY.md) · auditoría: [`docs/AUDITORIA.md`](docs/AUDITORIA.md).

```bash
pip install -r requirements.txt -r requirements-worker.txt && python -m playwright install chromium
python app.py                  # web
python -m autoapply.worker     # worker (proceso aparte)
```

## ✅ **YA IMPLEMENTADO**

### 🔐 Sistema de Credenciales
- Encriptación Fernet (AES-128)
- UI amigable (`/credenciales`)
- APIs REST completas

### 🤖 Selenium Scraper
- ElEmpleoBot funcional
- Login real sin bloqueos
- Chrome headless

### 📊 Filtros Avanzados
- Escolaridad, Inglés, Contrato
- Ubicación real, Resultados configurables

## 🛠️ **INSTALACIÓN LOCAL**

```bash
git clone https://github.com/DuvanP11/Job_Search.git
cd Job_Search
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abre: `http://localhost:5000`

## 🔐 **CONFIGURAR CREDENCIALES**

1. Ve a `/credenciales`
2. Crea cuenta en ElEmpleo.com
3. Ingresa email y password
4. ¡Listo!

## 🚀 **DEPLOY GRATIS EN RAILWAY**

1. https://railway.app
2. Conecta GitHub repo
3. Railway detecta Python
4. Deploy automático ✅

## 📁 **ESTRUCTURA**

```
utils/
├── scraper.py (Computrabajo)
├── selenium_scraper.py (ElEmpleo con login)
└── credentials.py (Encriptación)
```

## 👨‍💻 **AUTOR**

Duvan Perilla - @DuvanP11
