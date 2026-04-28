#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PORTAL DE BÚSQUEDA DE EMPLEOS
Autor: Duvan Perilla
Fecha: 2025

Aplicación web Flask para búsqueda automatizada de ofertas laborales
"""

from flask import Flask, render_template, request, jsonify, send_file
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
    return render_template('index.html')


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
            'fecha_desde': data.get('fecha_desde', None),  # NUEVO: filtro de fecha
            'fecha_hasta': data.get('fecha_hasta', None),  # NUEVO: filtro de fecha
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
        }
        
        # Ejecutar búsqueda
        print(f"🚀 Iniciando búsqueda con configuración: {config_busqueda}")
        
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
        
        # Preparar respuesta
        resumen = {
            'total': len(resultados_cache),
            'por_portal': buscador.obtener_estadisticas_portales(),
            'por_ubicacion': buscador.obtener_estadisticas_ubicacion(),
            'score_promedio': buscador.obtener_score_promedio()
        }
        
        # Limitar resultados a top 100 para enviar al frontend
        ofertas_limitadas = resultados_cache[:100] if len(resultados_cache) > 100 else resultados_cache
        
        return jsonify({
            'success': True,
            'ofertas': ofertas_limitadas,
            'resumen': resumen,
            'timestamp': ultima_busqueda.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"❌ Error en búsqueda: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error durante la búsqueda: {str(e)}'
        }), 500


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
