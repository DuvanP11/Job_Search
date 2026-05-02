# 🔒 CONFIGURACIÓN DE PERSISTENCIA DE DATOS EN RAILWAY

## PROBLEMA
Railway tiene filesystem efímero. Cada deploy borra los archivos en `/data/`.

## SOLUCIÓN: RAILWAY VOLUMES

### PASO A PASO PARA CONFIGURAR VOLUME

#### 1. IR A TU PROYECTO EN RAILWAY
```
https://railway.app/project/[tu-proyecto-id]
```

#### 2. CREAR VOLUME
```
1. Click en tu servicio (job-search-portal)
2. Pestaña "Settings"
3. Scroll down a "Volumes"
4. Click "+ New Volume"

CONFIGURACIÓN DEL VOLUME:
- Mount Path: /app/data
- Name: job-search-data
```

#### 3. REINICIAR SERVICIO
```
1. Pestaña "Deployments"
2. Click "Redeploy" en el deployment más reciente
```

#### 4. VERIFICAR
```
Después de redeploy:
1. Registra un usuario nuevo
2. Cierra sesión
3. Haz un nuevo deploy (push a GitHub)
4. Verifica que el usuario SIGA EXISTIENDO
```

## ESTRUCTURA DE DATOS

```
/app/data/              ← ESTE DIRECTORIO DEBE SER PERSISTENTE
├── users.json          ← Usuarios registrados
└── user_credentials.json  ← Credenciales de portales
```

## CONFIGURACIÓN ALTERNATIVA: BASE DE DATOS

Si Railway Volumes tiene problemas, migrar a PostgreSQL:

### OPCIÓN 1: PostgreSQL en Railway
```
1. Railway Dashboard → "+ New" → Database → PostgreSQL
2. Actualizar código para usar SQLAlchemy
3. Migrar datos de JSON a PostgreSQL
```

### OPCIÓN 2: Supabase (Free)
```
1. Crear cuenta en supabase.com
2. Crear proyecto
3. Usar cliente de Supabase en Python
4. Migrar datos
```

## TESTING POST-CONFIGURACIÓN

```bash
# Test 1: Registrar usuario
POST /register
{
  "username": "testuser",
  "email": "test@test.com",
  "password": "test123"
}

# Test 2: Hacer deploy nuevo
git push origin main

# Test 3: Verificar usuario persiste
POST /login
{
  "email": "test@test.com",
  "password": "test123"
}

✅ Si login funciona → Volume configurado correctamente
❌ Si login falla → Revisar Mount Path
```

## NOTAS IMPORTANTES

1. **Mount Path debe ser exacto**: `/app/data`
   - NO `/data`
   - NO `data/`
   - SÍ `/app/data`

2. **Primer deploy después de crear Volume**:
   - Los datos anteriores se perderán
   - Tendrás que registrar usuarios nuevamente
   - Pero DESPUÉS de eso, persistirán

3. **Backups**:
   - Railway NO hace backups automáticos de Volumes
   - Considera exportar usuarios periódicamente
   - O migrar a base de datos con backups automáticos

## VERIFICACIÓN DE VOLUME

Para verificar que el volume está montado correctamente:

```python
# Agregar a app.py (temporal, para debugging):
import os

@app.route('/debug/storage')
def debug_storage():
    """Ver estado del almacenamiento"""
    if not session.get('user_id'):
        return "Unauthorized", 401
    
    return {
        'data_dir_exists': os.path.exists('data/'),
        'users_file_exists': os.path.exists('data/users.json'),
        'credentials_file_exists': os.path.exists('data/user_credentials.json'),
        'cwd': os.getcwd(),
        'data_files': os.listdir('data/') if os.path.exists('data/') else []
    }
```

## CONTACTO

Si tienes problemas configurando el Volume:
- Railway Docs: https://docs.railway.app/reference/volumes
- Railway Discord: https://discord.gg/railway
