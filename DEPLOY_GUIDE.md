# 🚀 GUÍA DE DESPLIEGUE EN RENDER

## Paso 1: Preparación en GitHub

✅ **YA COMPLETADO** - Tu código ya está en: https://github.com/DuvanP11/Job_Search

## Paso 2: Crear Web Service en Render

### 2.1 Acceder a Render
1. Ve a https://render.com
2. Inicia sesión o crea una cuenta gratuita
3. Conecta tu cuenta de GitHub si no lo has hecho

### 2.2 Crear Nuevo Web Service
1. Click en **"New +"** en el dashboard
2. Selecciona **"Web Service"**
3. Conecta tu repositorio: `DuvanP11/Job_Search`
4. Click en **"Connect"**

### 2.3 Configurar el Servicio

Ingresa la siguiente configuración:

**General:**
- **Name:** `job-search-portal` (o el nombre que prefieras)
- **Region:** Oregon (USA) o la más cercana
- **Branch:** `main`
- **Root Directory:** (dejar vacío)

**Build & Deploy:**
- **Runtime:** `Python 3`
- **Build Command:** 
  ```
  pip install -r requirements.txt
  ```
- **Start Command:** 
  ```
  gunicorn app:app
  ```

**Plan:**
- **Instance Type:** `Free` (o el que prefieras)

**Environment Variables** (Opcional):
```
FLASK_ENV=production
PYTHON_VERSION=3.11.6
```

### 2.4 Deploy
1. Click en **"Create Web Service"**
2. Espera 2-5 minutos mientras se construye y despliega
3. Verás logs en tiempo real del proceso

### 2.5 Verificar Deploy
1. Una vez completado, verás el estado en verde: **"Live"**
2. Tu URL será algo como: `https://job-search-portal.onrender.com`
3. Haz click en la URL para probar tu aplicación

## Paso 3: Configuración Post-Deploy

### 3.1 Configurar Dominio Personalizado (Opcional)
1. En tu servicio de Render, ve a **"Settings"**
2. Sección **"Custom Domain"**
3. Agrega tu dominio y configura DNS

### 3.2 Monitoreo
- Render te enviará emails si hay errores
- Puedes ver logs en tiempo real en la pestaña **"Logs"**
- Métricas de uso en **"Metrics"**

## Paso 4: Actualizaciones Futuras

Cada vez que hagas push a GitHub, Render automáticamente:
1. Detectará el cambio
2. Reconstruirá la aplicación
3. Desplegará la nueva versión

### Para hacer cambios:

```bash
# Hacer tus cambios en el código
git add .
git commit -m "Descripción del cambio"
git push origin main
```

Render hará el redeploy automáticamente en ~2-3 minutos.

## Paso 5: Monitoreo y Mantenimiento

### Logs
```bash
# Ver logs en vivo desde Render dashboard
# O usar render-cli:
render logs -s job-search-portal
```

### Reiniciar Servicio
Si necesitas reiniciar:
1. Ve a tu servicio en Render
2. Click en **"Manual Deploy"** > **"Clear build cache & deploy"**

### Health Check
Tu app tiene un endpoint de health check en:
```
https://tu-app.onrender.com/health
```

## Solución de Problemas

### Build Fails
- Verifica que `requirements.txt` esté actualizado
- Revisa los logs de build en Render
- Asegúrate de que `runtime.txt` tenga la versión correcta

### App Crashes
- Revisa los logs de aplicación
- Verifica variables de entorno
- Asegúrate de que `Procfile` sea correcto

### Performance
- Plan Free tiene limitaciones
- Puede "dormir" después de 15 min de inactividad
- Considera upgrade a plan Starter si necesitas más recursos

## URLs Importantes

- **GitHub Repo:** https://github.com/DuvanP11/Job_Search
- **Render Dashboard:** https://dashboard.render.com
- **Documentación Render:** https://render.com/docs

## Comandos Git Útiles

```bash
# Ver estado
git status

# Ver commits
git log --oneline

# Crear nueva rama
git checkout -b feature/nueva-funcionalidad

# Merge a main
git checkout main
git merge feature/nueva-funcionalidad

# Push a GitHub
git push origin main
```

## Notas Importantes

⚠️ **SEGURIDAD DEL TOKEN:**
- **NUNCA compartas tokens de GitHub públicamente**
- Si compartiste un token, revócalo inmediatamente
- Ve a: GitHub > Settings > Developer settings > Personal access tokens
- Revoca el token expuesto y crea uno nuevo
- Para configuración local: `git remote set-url origin https://YOUR_TOKEN@github.com/DuvanP11/Job_Search.git`

📝 **PLAN FREE DE RENDER:**
- 750 horas/mes (suficiente para 1 servicio 24/7)
- App "duerme" tras 15 min de inactividad
- Primera request tras "despertar" toma ~30 segundos
- Suficiente para pruebas y proyectos personales

🚀 **MEJORAS FUTURAS:**
- Considera agregar Redis para caché
- Implementar rate limiting
- Agregar base de datos PostgreSQL para guardar búsquedas

---

¡Tu aplicación está lista para el mundo! 🎉
