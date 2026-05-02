#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PORTAL DE BÚSQUEDA DE EMPLEOS
Autor: Duvan Perilla
Fecha: 2025

Aplicación web Flask para búsqueda automatizada de ofertas laborales
"""

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from datetime import datetime, timedelta
import pandas as pd
import io
import os
import random
import string
import json
from utils.scraper import BuscadorEmpleos

app = Flask(__name__)
app.config['SECRET_KEY'] = 'job-search-portal-2025-duvan-secure-key-12345'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Configuración de sesiones persistentes (cookies del lado del cliente)
app.config['SESSION_TYPE'] = None  # Usar cookies firmadas del cliente (default Flask)
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True si usas HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_DOMAIN'] = None  # Permite subdominios
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 días
app.config['SESSION_COOKIE_NAME'] = 'job_search_session'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Renovar sesión en cada request

# LOGGING DE VOLUME AL INICIO
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verificar volume al inicio
data_path = os.path.abspath('data')
logger.info(f"🔍 DATA PATH: {data_path}")
logger.info(f"🔍 CWD: {os.getcwd()}")
logger.info(f"🔍 DATA EXISTS: {os.path.exists('data')}")
if os.path.exists('data'):
    logger.info(f"🔍 DATA FILES: {os.listdir('data')}")
    users_file = 'data/users.json'
    if os.path.exists(users_file):
        size = os.path.getsize(users_file)
        logger.info(f"🔍 USERS FILE SIZE: {size} bytes")
        with open(users_file, 'r') as f:
            content = f.read()
            logger.info(f"🔍 USERS CONTENT: {content[:200]}")

# Variables globales para caché de resultados
ultima_busqueda = None
resultados_cache = []

# LOGGING DE TIPO DE BASE DE DATOS
logger.info("=" * 60)
logger.info("🔍 VERIFICANDO CONFIGURACIÓN DE BASE DE DATOS")
logger.info("=" * 60)
database_url = os.getenv('DATABASE_URL')
logger.info(f"🔍 DATABASE_URL presente: {bool(database_url)}")
if database_url:
    # Mostrar solo primeros caracteres por seguridad
    logger.info(f"🔍 DATABASE_URL (primeros 30 chars): {database_url[:30]}...")
else:
    logger.info("⚠️ DATABASE_URL NO ENCONTRADA - Usará JSON")
logger.info("=" * 60)

# Códigos de recuperación temporal (en memoria)
# En producción usar Redis o base de datos
recovery_codes = {}


@app.route('/')
def index():
    """Página principal con formulario de búsqueda"""
    from utils.auth import get_current_user, get_avatar_emoji
    
    # Verificar si hay sesión activa
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    avatar_emoji = get_avatar_emoji(user.get('avatar', 'cat'))
    
    return render_template('index.html', user=user, avatar_emoji=avatar_emoji)


@app.route('/buscar', methods=['POST'])
def buscar():
    """Endpoint para ejecutar búsqueda de empleos"""
    global ultima_busqueda, resultados_cache
    
    try:
        # Obtener parámetros del formulario
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('titulos') or not data.get('ubicaciones'):
            return jsonify({
                'success': False,
                'error': 'Debes especificar al menos un cargo y una ubicación'
            }), 400
        
        # Construir configuración de búsqueda
        config_busqueda = {
            'titulos': data.get('titulos', []),
            'ubicaciones': data.get('ubicaciones', []),
            'pais': data.get('pais', 'Colombia'),
            'modalidad': data.get('modalidad', 'presencial'),
            'salario_minimo': int(data.get('salario_minimo', 0)),
            'tipo_contrato': data.get('tipo_contrato', 'todos'),
            'escolaridad': data.get('escolaridad', 'todos'),
            'nivel_ingles': data.get('nivel_ingles', 'todos'),
            'experiencia_minima': int(data.get('experiencia_minima', 0)),
            'experiencia_maxima': int(data.get('experiencia_maxima', 15)),
            'fecha_desde': data.get('fecha_desde', None),
            'fecha_hasta': data.get('fecha_hasta', None),
            'resultados_por_portal': int(data.get('resultados_por_portal', 10)),
        }
        
        # Keywords
        keywords = {
            'incluir': data.get('keywords_incluir', []),
            'excluir': data.get('keywords_excluir', []),
            'bonus': data.get('keywords_bonus', [])
        }
        
        # Portales activos
        portales = {
            'computrabajo': data.get('portal_computrabajo', True),
            'elempleo': data.get('portal_elempleo', True),
            'magneto': data.get('portal_magneto', True),
            'indeed': data.get('portal_indeed', True),
            'trabajando': data.get('portal_trabajando', True),
            'linkedin': data.get('portal_linkedin', False),
            'serviciodeempleo': data.get('portal_serviciodeempleo', False),
            'talentbox': data.get('portal_talentbox', False),
            'colsubsidio': data.get('portal_colsubsidio', False),
            'unmejorempleo': data.get('portal_unmejorempleo', False),
        }
        
        # Ejecutar búsqueda
        print(f"🚀 Iniciando búsqueda con configuración: {config_busqueda}")
        print(f"📊 Portales activos: {portales}")
        
        try:
            buscador = BuscadorEmpleos(config_busqueda, keywords, portales)
            buscador.ejecutar_busqueda()
            buscador.eliminar_duplicados()
            
            # Aplicar filtro de fechas si se especificó
            if config_busqueda['fecha_desde'] or config_busqueda['fecha_hasta']:
                buscador.filtrar_por_fechas(
                    fecha_desde=config_busqueda['fecha_desde'],
                    fecha_hasta=config_busqueda['fecha_hasta']
                )
            
            buscador.ordenar_por_score()
            
            # Guardar en caché
            resultados_cache = buscador.ofertas_encontradas
            ultima_busqueda = datetime.now()
            
        except Exception as e:
            print(f"❌ Error en búsqueda: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Retornar error pero con JSON válido
            return jsonify({
                'success': False,
                'error': f'Error al ejecutar búsqueda: {str(e)}',
                'ofertas': [],
                'resumen': {
                    'total_ofertas': 0,
                    'score_promedio': 0,
                    'portales_consultados': 0,
                    'fecha_busqueda': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }), 200  # Retornar 200 con error en JSON, no 500
        
        # Preparar respuesta
        resumen = {
            'total_ofertas': len(resultados_cache),
            'score_promedio': round(sum(o['score'] for o in resultados_cache) / len(resultados_cache), 1) if resultados_cache else 0,
            'portales_consultados': len([p for p, activo in portales.items() if activo]),
            'fecha_busqueda': ultima_busqueda.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"✅ Búsqueda completada: {resumen['total_ofertas']} ofertas encontradas")
        
        return jsonify({
            'success': True,
            'ofertas': resultados_cache[:100],  # Limitar a top 100
            'resumen': resumen
        }), 200
    
    except Exception as e:
        print(f"❌ Error general en endpoint /buscar: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # SIEMPRE retornar JSON válido, nunca crashear
        return jsonify({
            'success': False,
            'error': f'Error del servidor: {str(e)}',
            'ofertas': [],
            'resumen': {
                'total_ofertas': 0,
                'score_promedio': 0,
                'portales_consultados': 0,
                'fecha_busqueda': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200  # Retornar 200 con error en JSON


@app.route('/exportar', methods=['GET'])
def exportar_excel():
    """Exportar resultados a Excel"""
    global resultados_cache
    
    try:
        if not resultados_cache:
            return jsonify({
                'success': False,
                'error': 'No hay resultados para exportar. Realiza una búsqueda primero.'
            }), 400
        
        # Crear DataFrame
        df = pd.DataFrame(resultados_cache)
        
        # Reordenar columnas
        columnas_orden = ['score', 'titulo', 'empresa', 'ubicacion', 'portal', 
                         'link', 'fecha_publicacion', 'fecha_busqueda']
        columnas_disponibles = [col for col in columnas_orden if col in df.columns]
        df = df[columnas_disponibles]
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Ofertas', index=False)
            
            # Formatear
            worksheet = writer.sheets['Ofertas']
            worksheet.column_dimensions['A'].width = 10  # Score
            worksheet.column_dimensions['B'].width = 50  # Título
            worksheet.column_dimensions['C'].width = 30  # Empresa
            worksheet.column_dimensions['D'].width = 20  # Ubicación
            worksheet.column_dimensions['E'].width = 15  # Portal
            worksheet.column_dimensions['F'].width = 60  # Link
            worksheet.column_dimensions['G'].width = 15  # Fecha Publicación
            worksheet.column_dimensions['H'].width = 15  # Fecha Búsqueda
        
        output.seek(0)
        
        # Nombre del archivo con timestamp
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f'ofertas_empleo_{fecha}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=nombre_archivo
        )
        
    except Exception as e:
        print(f"❌ Error al exportar: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error al exportar: {str(e)}'
        }), 500


@app.route('/estadisticas', methods=['GET'])
def obtener_estadisticas():
    """Obtener estadísticas de la última búsqueda"""
    global resultados_cache, ultima_busqueda
    
    if not resultados_cache:
        return jsonify({
            'success': False,
            'error': 'No hay resultados disponibles'
        }), 400
    
    # Calcular estadísticas
    df = pd.DataFrame(resultados_cache)
    
    stats = {
        'total_ofertas': len(resultados_cache),
        'score_promedio': df['score'].mean() if 'score' in df else 0,
        'score_max': df['score'].max() if 'score' in df else 0,
        'score_min': df['score'].min() if 'score' in df else 0,
        'por_portal': df['portal'].value_counts().to_dict() if 'portal' in df else {},
        'por_ubicacion': df['ubicacion'].value_counts().head(10).to_dict() if 'ubicacion' in df else {},
        'ultima_busqueda': ultima_busqueda.strftime('%Y-%m-%d %H:%M:%S') if ultima_busqueda else None
    }
    
    return jsonify({
        'success': True,
        'estadisticas': stats
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check para Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/test-busqueda', methods=['GET'])
def test_busqueda():
    """Endpoint de prueba - retorna datos dummy sin scraping"""
    try:
        ofertas_dummy = [
            {
                'titulo': 'Analista de Datos (PRUEBA)',
                'empresa': 'Empresa Test',
                'ubicacion': 'Bogotá',
                'link': 'https://example.com/test',
                'portal': 'TEST',
                'fecha_publicacion': datetime.now().strftime('%Y-%m-%d'),
                'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                'descripcion': 'Oferta de prueba',
                'score': 75
            }
        ]
        
        return jsonify({
            'success': True,
            'ofertas': ofertas_dummy,
            'resumen': {
                'total_ofertas': 1,
                'score_promedio': 75.0,
                'portales_consultados': 1,
                'fecha_busqueda': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== RUTAS DE CREDENCIALES ====================

@app.route('/credenciales')
def credenciales():
    """Página de configuración de credenciales"""
    from utils.credentials import credential_manager
    
    # Obtener portales configurados
    portales = credential_manager.list_portals()
    
    return render_template('credenciales.html', portales=portales)


@app.route('/api/credenciales/guardar', methods=['POST'])
def guardar_credenciales():
    """Guardar credenciales de un portal"""
    try:
        from utils.credentials import credential_manager
        
        data = request.get_json()
        portal = data.get('portal')
        email = data.get('email')
        password = data.get('password')
        
        # Validar
        if not all([portal, email, password]):
            return jsonify({
                'success': False,
                'error': 'Faltan datos requeridos'
            }), 400
        
        # Guardar
        success = credential_manager.save_credentials(portal, email, password)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Credenciales guardadas para {portal}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error guardando credenciales'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/credenciales/listar', methods=['GET'])
def listar_credenciales():
    """Listar portales configurados"""
    try:
        from utils.credentials import credential_manager
        
        portales = credential_manager.list_portals()
        
        return jsonify({
            'success': True,
            'portales': portales
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/credenciales/eliminar', methods=['POST'])
def eliminar_credenciales():
    """Eliminar credenciales de un portal"""
    try:
        from utils.credentials import credential_manager
        
        data = request.get_json()
        portal = data.get('portal')
        
        if not portal:
            return jsonify({
                'success': False,
                'error': 'Portal no especificado'
            }), 400
        
        success = credential_manager.delete_credentials(portal)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Credenciales eliminadas para {portal}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error eliminando credenciales'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/credenciales/toggle', methods=['POST'])
def toggle_credenciales():
    """Habilitar/deshabilitar portal"""
    try:
        from utils.credentials import credential_manager
        
        data = request.get_json()
        portal = data.get('portal')
        enabled = data.get('enabled', False)
        
        if not portal:
            return jsonify({
                'success': False,
                'error': 'Portal no especificado'
            }), 400
        
        success = credential_manager.toggle_portal(portal, enabled)
        
        if success:
            status = "habilitado" if enabled else "deshabilitado"
            return jsonify({
                'success': True,
                'message': f'Portal {portal} {status}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error actualizando estado'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== APIs DE DATOS (ROLES Y UBICACIONES) ====================

@app.route('/api/roles')
def get_roles():
    """Obtener lista de roles profesionales"""
    try:
        from utils.roles_data import get_roles_list
        
        roles = get_roles_list()
        return jsonify({
            'success': True,
            'roles': roles,
            'count': len(roles)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ubicaciones/paises')
def get_paises():
    """Obtener lista de países por región"""
    try:
        from utils.locations_data import get_paises_por_region
        
        paises_por_region = get_paises_por_region()
        return jsonify({
            'success': True,
            'paises': paises_por_region
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ubicaciones/ciudades/<pais>')
def get_ciudades(pais):
    """Obtener ciudades de un país"""
    try:
        from utils.locations_data import get_ciudades_por_pais
        
        ciudades = get_ciudades_por_pais(pais)
        return jsonify({
            'success': True,
            'pais': pais,
            'ciudades': ciudades
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== RUTAS DE AUTENTICACIÓN ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login de usuario"""
    from utils.database import db
    from utils.auth import login_user
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.authenticate_user(email, password)
        
        if user:
            login_user(user)
            flash(f'✅ Bienvenido {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Email o contraseña incorrectos', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevo usuario"""
    from utils.database import db
    from utils.auth import login_user, AVATARES
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        avatar = request.form.get('avatar', 'cat')
        
        user_id = db.create_user(username, email, password, avatar)
        
        if user_id:
            user = db.get_user_by_id(user_id)
            login_user(user)
            flash(f'✅ Cuenta creada! Bienvenido {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('❌ El email o usuario ya están registrados', 'error')
    
    return render_template('register.html', avatars=AVATARES)


@app.route('/logout')
def logout():
    """Cerrar sesión"""
    from utils.auth import logout_user
    
    logout_user()
    flash('✅ Sesión cerrada correctamente', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    """Dashboard de usuario"""
    from utils.auth import get_current_user, get_avatar_emoji
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    try:
        # Obtener datos para dashboard
        credentials = db.list_user_credentials(user['id'])
        credentials_count = len(credentials)
        
        # Fecha de creación
        created_at_str = user.get('created_at', '')
        if created_at_str:
            created_at = datetime.fromisoformat(created_at_str)
            member_since = created_at.strftime('%b %Y')
        else:
            member_since = 'Hoy'
        
        # Avatar emoji
        avatar_key = user.get('avatar', 'cat')
        avatar_emoji = get_avatar_emoji(avatar_key)
        
        return render_template(
            'dashboard.html',
            user=user,
            avatar_emoji=avatar_emoji,
            credentials_count=credentials_count,
            searches_count=0,
            member_since=member_since
        )
    except Exception as e:
        # Log error y mostrar página de error
        print(f"Error en dashboard: {str(e)}")
        flash(f'Error cargando dashboard: {str(e)}', 'error')
        return redirect(url_for('login'))


@app.route('/user/credenciales')
def user_credenciales():
    """Página de credenciales privadas del usuario"""
    from utils.auth import get_current_user, get_avatar_emoji
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    # Obtener credenciales del usuario
    credenciales = db.list_user_credentials(user['id'])
    
    # Avatar emoji
    avatar_emoji = get_avatar_emoji(user.get('avatar', 'cat'))
    
    return render_template('user_credentials.html', user=user, credenciales=credenciales, avatar_emoji=avatar_emoji)


# ==================== APIS DE CREDENCIALES DE USUARIO ====================

@app.route('/api/user/credenciales/guardar', methods=['POST'])
def api_user_guardar_credencial():
    """Guardar credencial de portal para usuario actual"""
    from utils.auth import get_current_user
    from utils.database import db
    from utils.credentials import credential_manager
    
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        portal = data.get('portal')
        email = data.get('email')
        password = data.get('password')
        
        if not all([portal, email, password]):
            return jsonify({
                'success': False,
                'error': 'Faltan datos requeridos'
            }), 400
        
        # Encriptar contraseña
        password_encrypted = credential_manager.cipher.encrypt(password.encode()).decode()
        
        # Guardar en base de datos del usuario
        success = db.save_user_credentials(user['id'], portal, email, password_encrypted)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Credenciales de {portal} guardadas'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error guardando credenciales'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/user/credenciales/listar')
def api_user_listar_credenciales():
    """Listar credenciales del usuario actual"""
    from utils.auth import get_current_user
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        credenciales = db.list_user_credentials(user['id'])
        
        return jsonify({
            'success': True,
            'credenciales': credenciales
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/user/credenciales/eliminar', methods=['POST'])
def api_user_eliminar_credencial():
    """Eliminar credencial de portal para usuario actual"""
    from utils.auth import get_current_user
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    
    try:
        data = request.get_json()
        portal = data.get('portal')
        
        if not portal:
            return jsonify({
                'success': False,
                'error': 'Portal no especificado'
            }), 400
        
        success = db.delete_user_credentials(user['id'], portal)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Credenciales de {portal} eliminadas'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Credencial no encontrada'
            }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Recuperar contraseña - Enviar código"""
    if request.method == 'POST':
        from utils.database import db
        
        email = request.form.get('email')
        user = db.get_user_by_email(email)
        
        if not user:
            flash('No existe una cuenta con ese email', 'error')
            return redirect(url_for('forgot_password'))
        
        # Generar código de 6 dígitos
        code = ''.join(random.choices(string.digits, k=6))
        
        # Guardar código con expiración de 15 minutos
        recovery_codes[email] = {
            'code': code,
            'expires_at': datetime.now() + timedelta(minutes=15)
        }
        
        # En producción, enviar por email
        # Por ahora, mostrar el código en la pantalla
        flash(f'Tu código de recuperación es: {code} (válido por 15 minutos)', 'info')
        return redirect(url_for('reset_password', email=email))
    
    return render_template('forgot_password.html')


@app.route('/reset-password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    """Restablecer contraseña con código"""
    if request.method == 'POST':
        from utils.database import db
        
        code = request.form.get('code')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validar que las contraseñas coincidan
        if new_password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return redirect(url_for('reset_password', email=email))
        
        # Validar código
        if email not in recovery_codes:
            flash('Código expirado o inválido', 'error')
            return redirect(url_for('forgot_password'))
        
        recovery_data = recovery_codes[email]
        
        # Verificar expiración
        if datetime.now() > recovery_data['expires_at']:
            del recovery_codes[email]
            flash('El código ha expirado. Solicita uno nuevo', 'error')
            return redirect(url_for('forgot_password'))
        
        # Verificar código
        if code != recovery_data['code']:
            flash('Código incorrecto', 'error')
            return redirect(url_for('reset_password', email=email))
        
        # Actualizar contraseña
        user = db.get_user_by_email(email)
        if not user:
            flash('Usuario no encontrado', 'error')
            return redirect(url_for('login'))
        
        # Actualizar contraseña
        user['password_hash'] = db.hash_password(new_password)
        db.update_user(user['id'], user)
        
        # Eliminar código usado
        del recovery_codes[email]
        
        flash('Contraseña actualizada exitosamente', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', email=email)


@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    """Editar perfil de usuario"""
    from utils.auth import get_current_user, get_avatar_emoji, AVATARES
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Obtener datos del formulario
        avatar = request.form.get('avatar', user.get('avatar', 'cat'))
        nombre = request.form.get('nombre', '')
        apellido = request.form.get('apellido', '')
        edad = request.form.get('edad', '')
        nacionalidad = request.form.get('nacionalidad', '')
        
        # Actualizar usuario
        user['avatar'] = avatar
        user['nombre'] = nombre
        user['apellido'] = apellido
        user['edad'] = int(edad) if edad else None
        user['nacionalidad'] = nacionalidad
        
        # Guardar cambios
        db.update_user(user['id'], user)
        
        # Actualizar sesión
        session['avatar'] = avatar
        
        flash('Perfil actualizado exitosamente', 'success')
        return redirect(url_for('dashboard'))
    
    # GET - mostrar formulario
    avatar_emoji = get_avatar_emoji(user.get('avatar', 'cat'))
    
    return render_template(
        'edit_profile.html',
        user=user,
        avatar_emoji=avatar_emoji,
        avatars=list(AVATARES.items())
    )


@app.route('/debug/storage')
def debug_storage():
    """Verificar estado del almacenamiento - SOLO PARA DEBUGGING"""
    from utils.auth import get_current_user
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    import os
    from datetime import datetime
    
    data_dir = 'data'
    users_file = os.path.join(data_dir, 'users.json')
    credentials_file = os.path.join(data_dir, 'user_credentials.json')
    
    info = {
        'timestamp': datetime.now().isoformat(),
        'cwd': os.getcwd(),
        'data_dir': {
            'exists': os.path.exists(data_dir),
            'path': os.path.abspath(data_dir),
            'files': os.listdir(data_dir) if os.path.exists(data_dir) else []
        },
        'users_file': {
            'exists': os.path.exists(users_file),
            'path': os.path.abspath(users_file),
            'size': os.path.getsize(users_file) if os.path.exists(users_file) else 0
        },
        'credentials_file': {
            'exists': os.path.exists(credentials_file),
            'path': os.path.abspath(credentials_file),
            'size': os.path.getsize(credentials_file) if os.path.exists(credentials_file) else 0
        },
        'volume_check': {
            'expected_mount': '/app/data',
            'current_path': os.path.abspath(data_dir),
            'is_volume_mounted': os.path.abspath(data_dir) == '/app/data'
        }
    }
    
    return jsonify(info)


@app.route('/admin/reset-all', methods=['GET', 'POST'])
def admin_reset_all():
    """TEMPORAL: Resetear toda la base de datos - SOLO DESARROLLO"""
    import os
    from datetime import datetime
    
    if request.method == 'POST':
        password = request.form.get('admin_password')
        
        # Password temporal de seguridad
        if password != 'reset2025':
            return jsonify({'error': 'Password incorrecto'}), 403
        
        try:
            # Backup antes de borrar
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = 'data/backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Copiar archivos actuales
            if os.path.exists('data/users.json'):
                import shutil
                shutil.copy('data/users.json', f'{backup_dir}/users_{timestamp}.json')
            
            if os.path.exists('data/user_credentials.json'):
                import shutil
                shutil.copy('data/user_credentials.json', f'{backup_dir}/credentials_{timestamp}.json')
            
            # Resetear archivos
            with open('data/users.json', 'w') as f:
                json.dump({}, f)
            
            with open('data/user_credentials.json', 'w') as f:
                json.dump({}, f)
            
            return jsonify({
                'success': True,
                'message': 'Base de datos reseteada',
                'backup': f'Backup guardado en {backup_dir}',
                'timestamp': timestamp
            })
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET - mostrar formulario
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Base de Datos</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-danger">
        <div class="container mt-5">
            <div class="card">
                <div class="card-header bg-warning">
                    <h3>⚠️ RESETEAR BASE DE DATOS</h3>
                </div>
                <div class="card-body">
                    <div class="alert alert-danger">
                        <strong>ADVERTENCIA:</strong> Esto borrará TODOS los usuarios y credenciales.
                        Se creará un backup antes de borrar.
                    </div>
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">Password de Admin:</label>
                            <input type="password" class="form-control" name="admin_password" required>
                            <small class="text-muted">Hint: reset2025</small>
                        </div>
                        <button type="submit" class="btn btn-danger">
                            🗑️ Resetear TODO
                        </button>
                        <a href="/" class="btn btn-secondary">Cancelar</a>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''


# ==================== ENDPOINTS DEL BOT DE CV ====================

@app.route('/api/cv-bot/chat', methods=['POST'])
def cv_bot_chat():
    """Endpoint para chat con el bot de CV"""
    from utils.cv_bot import get_cv_bot
    
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Mensaje vacío'}), 400
        
        # Obtener instancia del bot
        bot = get_cv_bot()
        
        # Verificar si Ollama está corriendo
        if not bot.check_ollama_status():
            return jsonify({
                'response': '⚠️ Ollama no está corriendo. Por favor inicia Ollama en tu máquina local.<br><br>Comando: <code>ollama serve</code>'
            })
        
        # Generar respuesta
        response = bot.chat(message)
        
        return jsonify({'response': response})
    
    except Exception as e:
        logger.error(f"Error en cv-bot chat: {str(e)}")
        return jsonify({
            'response': f'Lo siento, ocurrió un error: {str(e)}'
        })


@app.route('/api/cv-bot/upload', methods=['POST'])
def cv_bot_upload():
    """Endpoint para subir y analizar CV"""
    from utils.cv_bot import get_cv_bot
    
    try:
        if 'cv' not in request.files:
            return jsonify({'error': 'No se encontró archivo'}), 400
        
        file = request.files['cv']
        
        if file.filename == '':
            return jsonify({'error': 'Nombre de archivo vacío'}), 400
        
        # Leer archivo
        file_bytes = file.read()
        filename = file.filename
        
        # Obtener instancia del bot
        bot = get_cv_bot()
        
        # Verificar si Ollama está corriendo
        if not bot.check_ollama_status():
            return jsonify({
                'message': '⚠️ Ollama no está corriendo. El CV fue cargado pero no puedo analizarlo sin Ollama.<br><br>Inicia Ollama con: <code>ollama serve</code>',
                'analysis': None
            })
        
        # Parsear CV
        cv_text = bot.parse_cv(file_bytes, filename)
        bot.cv_text = cv_text
        
        # Analizar CV
        analysis = bot.analyze_cv_ats()
        
        message = f'✅ CV cargado correctamente: <strong>{filename}</strong><br><br>'
        message += f'📄 Longitud del texto: {len(cv_text)} caracteres<br><br>'
        message += 'Analizando con IA...'
        
        return jsonify({
            'message': message,
            'analysis': analysis
        })
    
    except Exception as e:
        logger.error(f"Error en cv-bot upload: {str(e)}")
        return jsonify({
            'message': f'❌ Error al procesar CV: {str(e)}',
            'analysis': None
        })


@app.errorhandler(404)
def not_found(error):
    """Manejo de error 404"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Manejo de error 500"""
    return render_template('500.html'), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
