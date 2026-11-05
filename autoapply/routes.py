#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blueprint y rutas del módulo 'Aplicar automáticamente'."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any

from flask import (
    Blueprint, Response, flash, jsonify, redirect, render_template, request, session, url_for
)

from .cv import guardar_cv, guardar_perfil_profesional, obtener_perfil_profesional
from .documents import (
    carta_a_docx, carta_a_pdf, construir_datos_cv, cv_a_docx, cv_a_pdf, generar_carta, responder_pregunta,
)
from .engine import AutoApplyEngine
from .profile import CVError, construir_perfil, estado_campos, extraer_texto
from .models import DEFAULT_PROFILE_CONFIG, PORTALES_SOPORTADOS, PORTALES_NO_DISPONIBLES, MODOS
from .runner import AutoApplyRunner
from .security import validar_config_perfil
from .storage import get_store

logger = logging.getLogger(__name__)

autoapply_bp = Blueprint('autoapply', __name__, url_prefix='/autoaplicar',
                        template_folder='../templates')


def _user_id():
    # Nunca caer a un id fijo: eso hacía que, sin sesión válida, se leyera y
    # escribiera sobre la cuenta del usuario 1 (datos de otra persona).
    return session.get('user_id') or session.get('usuario_id')


def _requiere_login(f):
    @wraps(f)
    def envuelto(*args, **kwargs):
        if not session.get('user_id') and not session.get('usuario_id'):
            flash('Debes iniciar sesión para usar "Aplicar automáticamente".', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return envuelto


def _get_perfil(store, user_id: Any):
    perfil = store.get('profiles', user_id, 'default')
    if perfil:
        return perfil
    perfiles = store.list('profiles', user_id)
    return perfiles[0] if perfiles else {}


def _guardar_perfil(store, user_id: Any, perfil: dict):
    perfil = dict(perfil)
    perfil.setdefault('id', 'default')
    guardado, _ = store.save('profiles', user_id, perfil, record_id='default')
    return guardado


@autoapply_bp.route('/')
@_requiere_login
def index():
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    perfil = _get_perfil(store, user_id)
    candidato = obtener_perfil_profesional(user_id)
    stats = engine.estadisticas(user_id)
    ofertas = engine.listar(user_id, limit=30)
    config = perfil.get('config') or DEFAULT_PROFILE_CONFIG
    return render_template('autoapply.html',
                           perfil=perfil,
                           config=config,
                           candidato=candidato,
                           stats=stats,
                           ofertas=ofertas,
                           portales_soportados=PORTALES_SOPORTADOS,
                           portales_no_disponibles=PORTALES_NO_DISPONIBLES,
                           modos=MODOS)


@autoapply_bp.route('/perfil', methods=['GET', 'POST'])
@_requiere_login
def perfil():
    store = get_store()
    user_id = _user_id()
    perfil = _get_perfil(store, user_id)
    config = perfil.get('config') or dict(DEFAULT_PROFILE_CONFIG)

    if request.method == 'POST':
        config['nombre'] = request.form.get('nombre_perfil', 'Perfil principal')
        config['cargos'] = [c.strip() for c in request.form.get('cargos', '').split('\n') if c.strip()]
        config['sinonimos'] = [c.strip() for c in request.form.get('sinonimos', '').split('\n') if c.strip()]
        config['keywords_obligatorias'] = [c.strip() for c in request.form.get('keywords_obligatorias', '').split('\n') if c.strip()]
        config['keywords_excluyentes'] = [c.strip() for c in request.form.get('keywords_excluyentes', '').split('\n') if c.strip()]
        config['ciudad'] = request.form.get('ciudad', '')
        config['departamento'] = request.form.get('departamento', '')
        config['pais'] = request.form.get('pais', 'Colombia')
        config['modalidades'] = request.form.getlist('modalidades')
        config['salario_minimo'] = int(request.form.get('salario_minimo') or 0)
        config['puntuacion_minima'] = int(request.form.get('puntuacion_minima') or 60)
        config['max_postulaciones_diarias'] = int(request.form.get('max_postulaciones_diarias') or 5)
        config['fecha_publicacion_dias'] = int(request.form.get('fecha_publicacion_dias') or 30)
        config['resultados_por_cargo'] = int(request.form.get('resultados_por_cargo') or 20)
        config['portales'] = request.form.getlist('portales')
        config['greenhouse_boards'] = [b.strip() for b in request.form.get('greenhouse_boards', '').split('\n') if b.strip()]
        config['lever_companies'] = [c.strip() for c in request.form.get('lever_companies', '').split('\n') if c.strip()]
        config['ashby_boards'] = [c.strip() for c in request.form.get('ashby_boards', '').split('\n') if c.strip()]
        config['smartrecruiters_companies'] = [c.strip() for c in request.form.get('smartrecruiters_companies', '').split('\n') if c.strip()]
        config['empresas_excluidas'] = [e.strip() for e in request.form.get('empresas_excluidas', '').split('\n') if e.strip()]
        config['horario'] = {
            'desde': request.form.get('desde', '08:00'),
            'hasta': request.form.get('hasta', '18:00'),
            'dias': [int(d) for d in request.form.getlist('dias')],
        }

        errores = validar_config_perfil(config)
        if errores:
            for e in errores:
                flash(e, 'danger')
        else:
            perfil['config'] = config
            perfil['nombre'] = config.get('nombre', 'Perfil principal')
            _guardar_perfil(store, user_id, perfil)
            flash('Perfil guardado correctamente.', 'success')
            return redirect(url_for('autoapply.index'))

    candidato = obtener_perfil_profesional(user_id)
    return render_template('autoapply_perfil.html',
                           perfil=perfil,
                           config=config,
                           candidato=candidato,
                           portales_soportados=PORTALES_SOPORTADOS)


CAMPOS_CONFIRMABLES = ('nombre_completo', 'email', 'telefono', 'ciudad', 'linkedin', 'titular',
                       'resumen', 'anios_experiencia', 'habilidades', 'educacion', 'experiencia', 'idiomas')


def _filas(form, prefijo, campos):
    """Reconstruye una lista de dicts desde inputs paralelos `prefijo_campo`."""
    columnas = {c: form.getlist(f'{prefijo}_{c}') for c in campos}
    n = max((len(v) for v in columnas.values()), default=0)
    filas = []
    for i in range(n):
        fila = {c: (columnas[c][i].strip() if i < len(columnas[c]) else '') for c in campos}
        if any(fila.values()):
            filas.append(fila)
    return filas


@autoapply_bp.route('/candidato', methods=['GET', 'POST'])
@_requiere_login
def candidato():
    user_id = _user_id()
    cand = obtener_perfil_profesional(user_id)

    if request.method == 'POST':
        f = request.form
        for campo in ('nombre_completo', 'email', 'telefono', 'ciudad', 'titular', 'resumen', 'linkedin'):
            cand[campo] = f.get(campo, '').strip()
        try:
            cand['anios_experiencia'] = float(f.get('anios_experiencia') or 0)
            cand['aspiracion_salarial'] = int(f.get('aspiracion_salarial') or 0)
        except ValueError:
            flash('Años de experiencia y aspiración salarial deben ser números.', 'danger')
            return redirect(url_for('autoapply.candidato'))
        cand['habilidades'] = [h.strip() for h in f.get('habilidades', '').split(',') if h.strip()]
        cand['experiencia'] = []
        for fila in _filas(f, 'exp', ('empresa', 'cargo', 'desde', 'hasta', 'responsabilidades')):
            fila['responsabilidades'] = [r.strip() for r in fila['responsabilidades'].split('\n') if r.strip()]
            cand['experiencia'].append(fila)
        cand['educacion'] = _filas(f, 'edu', ('titulo', 'institucion', 'nivel'))
        cand['idiomas'] = _filas(f, 'idi', ('idioma', 'nivel'))
        # Solo lo que el usuario marca como correcto pasa a 'verificado'.
        marcados = set(f.getlist('confirmar'))
        cand['campos_confirmados'] = [c for c in CAMPOS_CONFIRMABLES if c in marcados]
        guardar_perfil_profesional(user_id, cand)
        flash('Perfil profesional guardado.', 'success')
        return redirect(url_for('autoapply.candidato'))

    return render_template('autoapply_candidato.html', candidato=cand, estados=estado_campos(cand))


@autoapply_bp.route('/cv', methods=['GET', 'POST'])
@_requiere_login
def cv():
    store = get_store()
    user_id = _user_id()
    cv_actual = store.get('cv', user_id, 'principal') or {}

    if request.method == 'POST':
        texto = request.form.get('cv_texto', '')
        cv_actual['texto'] = texto
        cv_actual['nombre_archivo'] = request.form.get('nombre_archivo', '')
        guardar_cv(user_id, cv_actual)
        flash('CV guardado correctamente.', 'success')
        return redirect(url_for('autoapply.index'))

    return render_template('autoapply_cv.html', cv=cv_actual)


@autoapply_bp.route('/cv/importar', methods=['POST'])
@_requiere_login
def cv_importar():
    """Sube un PDF/DOCX/TXT (o pega texto), conserva el original y arma el perfil."""
    user_id = _user_id()
    archivo = request.files.get('archivo')
    try:
        if archivo and archivo.filename:
            texto = extraer_texto(archivo.read(), archivo.filename)
            nombre = archivo.filename[:120]
        else:
            texto = request.form.get('cv_texto', '').strip()
            nombre = 'texto pegado'
            if len(texto) < 80:
                raise CVError('Sube un archivo o pega el texto completo de tu CV.')
    except CVError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('autoapply.cv'))

    # El original se conserva tal cual; el perfil estructurado es aparte y editable.
    guardar_cv(user_id, {'texto': texto, 'nombre_archivo': nombre})
    existente = obtener_perfil_profesional(user_id)
    r = construir_perfil(texto, existente=existente, usar_ia=request.form.get('usar_ia', '1') == '1')
    guardar_perfil_profesional(user_id, r['perfil'])

    if r['metodo']['tipo'] == 'ia':
        flash(f"Perfil extraído con IA ({r['metodo']['proveedor']}). Revísalo y confirma lo correcto.", 'success')
    else:
        flash('Perfil extraído con lectura básica. Revísalo y complétalo.', 'warning')
    for aviso in r['avisos']:
        flash(aviso, 'warning')
    if r['descartes']:
        flash(f"Se descartaron {len(r['descartes'])} dato(s) de la IA que no aparecen en tu CV.", 'info')
    return redirect(url_for('autoapply.candidato'))


@autoapply_bp.route('/descubrir', methods=['POST'])
@_requiere_login
def descubrir():
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    perfil = _get_perfil(store, user_id)
    candidato = obtener_perfil_profesional(user_id)
    if not perfil.get('config'):
        flash('Configura tu perfil primero.', 'warning')
        return redirect(url_for('autoapply.perfil'))
    res = engine.descubrir(user_id, perfil, candidato)
    flash(f'Se encontraron {res["nuevas"]} ofertas nuevas.', 'info')
    return redirect(url_for('autoapply.index'))


@autoapply_bp.route('/ejecutar', methods=['POST'])
@_requiere_login
def ejecutar():
    store = get_store()
    user_id = _user_id()
    runner = AutoApplyRunner(store)
    perfil = _get_perfil(store, user_id)
    candidato = obtener_perfil_profesional(user_id)
    modo = request.form.get('modo', 'simulacion')
    confirmar_todo = request.form.get('confirmar_todo') == 'on'
    if not perfil.get('config'):
        flash('Configura tu perfil primero.', 'warning')
        return redirect(url_for('autoapply.perfil'))
    res = runner.ejecutar(user_id, perfil, candidato, modo=modo, confirmar_todo=confirmar_todo)
    if not res.get('ok'):
        for e in res.get('errores', []):
            flash(e, 'danger')
    else:
        flash(f'Modo: {modo}. Candidatas: {len(res["candidatas"])}. Postuladas: {res["postuladas"]}.', 'success')
    return redirect(url_for('autoapply.index'))


@autoapply_bp.route('/ofertas')
@_requiere_login
def ofertas():
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    status = request.args.get('status')
    portal = request.args.get('portal')
    ofertas = engine.listar(user_id, status=status, portal=portal, limit=200)
    return render_template('autoapply_ofertas.html', ofertas=ofertas,
                           status_filtro=status, portal_filtro=portal)


@autoapply_bp.route('/oferta/<job_id>')
@_requiere_login
def oferta_detalle(job_id):
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    job = engine.obtener(user_id, job_id)
    if not job:
        flash('Oferta no encontrada.', 'danger')
        return redirect(url_for('autoapply.ofertas'))
    docs = store.list('documents', user_id, where=lambda r: r.get('job_id') == job_id, limit=50)
    ultimos = {}
    for d in sorted(docs, key=lambda r: r.get('created_at', ''), reverse=True):
        ultimos.setdefault(d.get('tipo'), d)
    return render_template('autoapply_oferta.html', job=job, documentos=ultimos)


@autoapply_bp.route('/oferta/<job_id>/documentos', methods=['POST'])
@_requiere_login
def generar_documentos(job_id):
    """CV a la medida + carta para esta vacante. El CV original no se modifica."""
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    job = engine.obtener(user_id, job_id)
    if not job:
        flash('Oferta no encontrada.', 'danger')
        return redirect(url_for('autoapply.ofertas'))
    cand = obtener_perfil_profesional(user_id)
    if not cand or not (cand.get('nombre_completo') and (cand.get('experiencia') or cand.get('habilidades'))):
        flash('Completa tu perfil profesional (nombre y experiencia o habilidades) antes de generar documentos.', 'warning')
        return redirect(url_for('autoapply.candidato'))
    usar_ia = request.form.get('usar_ia', '1') == '1'
    cv_res = construir_datos_cv(cand, job, usar_ia=usar_ia)
    carta = generar_carta(cand, job, cv_res['habilidades_coincidentes'], usar_ia=usar_ia)
    base = {'job_id': job_id, 'empresa': job.get('empresa', ''), 'cargo': job.get('titulo', '')}
    store.save('documents', user_id, {**base, 'tipo': 'cv', 'contenido': cv_res['datos'],
                                      'generado_con': cv_res['generado_con'],
                                      'advertencias': cv_res['advertencias'],
                                      'coincidentes': cv_res['habilidades_coincidentes']})
    store.save('documents', user_id, {**base, 'tipo': 'carta', 'contenido': carta['texto'],
                                      'generado_con': carta['generado_con'], 'idioma': carta['idioma'],
                                      'advertencias': carta['advertencias']})
    if job.get('status') == 'en_evaluacion':
        engine.actualizar_estado(user_id, job_id, 'pendiente_revision', 'Documentos generados; falta revisión')
    flash('Documentos generados. Revisa la carta y el CV antes de usarlos.', 'success')
    return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))


def _nombre_archivo(doc, ext):
    import re
    limpio = re.sub(r'[^A-Za-z0-9]+', '_', f"{doc.get('empresa', '')}_{doc.get('cargo', '')}").strip('_')[:60]
    return f"{'CV' if doc.get('tipo') == 'cv' else 'Carta'}_{limpio or 'oferta'}.{ext}"


@autoapply_bp.route('/documento/<doc_id>/descargar/<fmt>')
@_requiere_login
def descargar_documento(doc_id, fmt):
    doc = get_store().get('documents', _user_id(), doc_id)     # el almacén es por usuario
    if not doc or fmt not in ('pdf', 'docx'):
        flash('Documento no encontrado.', 'danger')
        return redirect(url_for('autoapply.ofertas'))
    if doc['tipo'] == 'cv':
        datos = cv_a_pdf(doc['contenido']) if fmt == 'pdf' else cv_a_docx(doc['contenido'])
    else:
        datos = carta_a_pdf(doc['contenido']) if fmt == 'pdf' else carta_a_docx(doc['contenido'])
    mime = 'application/pdf' if fmt == 'pdf' else \
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(datos, mimetype=mime, headers={
        'Content-Disposition': f'attachment; filename="{_nombre_archivo(doc, fmt)}"',
        'X-Content-Type-Options': 'nosniff'})


@autoapply_bp.route('/documento/<doc_id>/editar', methods=['POST'])
@_requiere_login
def editar_carta(doc_id):
    """El usuario puede corregir el texto de la carta; queda marcado como editado a mano."""
    store = get_store()
    user_id = _user_id()
    doc = store.get('documents', user_id, doc_id)
    if not doc or doc.get('tipo') != 'carta':
        flash('Solo se puede editar el texto de la carta.', 'danger')
        return redirect(url_for('autoapply.ofertas'))
    doc['contenido'] = request.form.get('contenido', '').strip()[:6000]
    doc['generado_con'] = 'editado_por_usuario'
    doc['advertencias'] = []
    store.save('documents', user_id, doc, record_id=doc_id)
    flash('Carta actualizada.', 'success')
    return redirect(url_for('autoapply.oferta_detalle', job_id=doc['job_id']))


@autoapply_bp.route('/oferta/<job_id>/pregunta', methods=['POST'])
@_requiere_login
def responder_pregunta_formulario(job_id):
    """Borrador para una pregunta abierta. Lo sensible devuelve `requiere_usuario`."""
    user_id = _user_id()
    job = AutoApplyEngine(get_store()).obtener(user_id, job_id)
    pregunta = (request.get_json(silent=True) or {}).get('pregunta') or request.form.get('pregunta', '')
    if not job or not pregunta.strip():
        return jsonify({'error': 'Falta la oferta o la pregunta'}), 400
    return jsonify(responder_pregunta(pregunta, obtener_perfil_profesional(user_id), job))


@autoapply_bp.route('/oferta/<job_id>/preparar', methods=['POST'])
@_requiere_login
def preparar(job_id):
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    candidato = obtener_perfil_profesional(user_id)
    res = engine.preparar_postulacion(user_id, job_id, candidato)
    if res.get('error'):
        flash(res['error'], 'danger')
    else:
        flash('Oferta preparada para revisión.', 'info')
    return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))


@autoapply_bp.route('/oferta/<job_id>/estado', methods=['POST'])
@_requiere_login
def cambiar_estado(job_id):
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    status = request.form.get('status', '')
    motivo = request.form.get('motivo', '')
    engine.actualizar_estado(user_id, job_id, status, motivo)
    flash('Estado actualizado.', 'success')
    return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))


@autoapply_bp.route('/oferta/<job_id>/postular', methods=['POST'])
@_requiere_login
def postular_manual(job_id):
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    confirmado = request.form.get('confirmado') == 'on'
    evidencia = request.form.get('evidencia', '')
    engine.marcar_como_postulado(user_id, job_id, confirmado=confirmado, evidencia=evidencia)
    flash('Marcado como postulado.', 'success')
    return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))


@autoapply_bp.route('/api/estado')
@_requiere_login
def api_estado():
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    return jsonify(engine.estadisticas(user_id))


@autoapply_bp.route('/diagnostico')
@_requiere_login
def diagnostico():
    """Muestra dónde se guarda realmente: motor, base, cuenta y marcas de tiempo."""
    store = get_store()
    user_id = _user_id()
    pg = getattr(store, '_pg', None)
    motor = 'PostgreSQL' if pg is not None else 'JSON local (se pierde al reiniciar)'
    destino = '—'
    if pg is not None:
        url = pg.engine.url
        destino = f"{url.host or 'local'}:{url.port or ''}/{url.database or ''}"
    registros = {}
    for coleccion, record_id in (('profiles', 'default'),
                                 ('candidate', 'principal'),
                                 ('cv', 'principal')):
        doc = store.get(coleccion, user_id, record_id) or {}
        registros[coleccion] = {
            'encontrado': bool(doc),
            'updated_at': doc.get('updated_at') or '—',
            'detalle': (f"{len(doc.get('texto') or '')} caracteres de CV"
                        if coleccion == 'cv' else doc.get('nombre_completo') or doc.get('nombre') or ''),
        }
    return render_template('autoapply_diagnostico.html',
                           motor=motor, destino=destino,
                           user_id=user_id, registros=registros,
                           persistente=store.persistente)


@autoapply_bp.route('/api/descubrir', methods=['POST'])
@_requiere_login
def api_descubrir():
    store = get_store()
    user_id = _user_id()
    engine = AutoApplyEngine(store)
    perfil = _get_perfil(store, user_id)
    candidato = obtener_perfil_profesional(user_id)
    res = engine.descubrir(user_id, perfil, candidato)
    return jsonify(res)
