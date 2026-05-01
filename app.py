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
from utils.scraper import BuscadorEmpleos

app = Flask(__name__)
app.config['SECRET_KEY'] = 'job-search-portal-2025-duvan'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Variables globales para caché de resultados
ultima_busqueda = None
resultados_cache = []


@app.route('/')
def index():
    """Página principal con formulario de búsqueda"""
    from utils.auth import get_current_user
    
    # Verificar si hay sesión activa
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    return render_template('index.html', user=user)


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
            'salario_minimo': int(data.get('salario_minimo', 0)),
            'tipo_contrato': data.get('tipo_contrato', 'todos'),
            'modalidades': data.get('modalidades', ['remoto', 'híbrido', 'presencial']),
            'experiencia_minima': int(data.get('experiencia_minima', 0)),
            'experiencia_maxima': int(data.get('experiencia_maxima', 15)),
            'fecha_desde': data.get('fecha_desde', None),
            'fecha_hasta': data.get('fecha_hasta', None),
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
    
    return render_template('register.html', avatares=AVATARES)


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
    from utils.auth import get_current_user
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', user=user)


@app.route('/user/credenciales')
def user_credenciales():
    """Página de credenciales privadas del usuario"""
    from utils.auth import get_current_user
    from utils.database import db
    
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    # Obtener credenciales del usuario
    credenciales = db.list_user_credentials(user['id'])
    
    return render_template('user_credentials.html', user=user, credenciales=credenciales)


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
