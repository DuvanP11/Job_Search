#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blueprint y rutas del módulo 'Aplicar automáticamente'."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
)

from .cv import guardar_cv, guardar_perfil_profesional, obtener_perfil_profesional
from .engine import AutoApplyEngine
from .models import DEFAULT_PROFILE_CONFIG, PORTALES_SOPORTADOS, PORTALES_NO_DISPONIBLES, MODOS
from .runner import AutoApplyRunner
from .security import validar_config_perfil
from .storage import get_store

logger = logging.getLogger(__name__)

autoapply_bp = Blueprint('autoapply', __name__, url_prefix='/autoaplicar',
                        template_folder='../templates')


def _user_id():
    return session.get('user_id') or session.get('usuario_id') or 1


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


@autoapply_bp.route('/candidato', methods=['GET', 'POST'])
@_requiere_login
def candidato():
    store = get_store()
    user_id = _user_id()
    cand = obtener_perfil_profesional(user_id)

    if request.method == 'POST':
        cand['nombre_completo'] = request.form.get('nombre_completo', '')
        cand['email'] = request.form.get('email', '')
        cand['telefono'] = request.form.get('telefono', '')
        cand['ciudad'] = request.form.get('ciudad', '')
        cand['titular'] = request.form.get('titular', '')
        cand['resumen'] = request.form.get('resumen', '')
        cand['anios_experiencia'] = int(request.form.get('anios_experiencia') or 0)
        cand['aspiracion_salarial'] = int(request.form.get('aspiracion_salarial') or 0)
        cand['linkedin'] = request.form.get('linkedin', '')
        cand['habilidades'] = [h.strip() for h in request.form.get('habilidades', '').split(',') if h.strip()]
        guardar_perfil_profesional(user_id, cand)
        flash('Perfil profesional guardado.', 'success')
        return redirect(url_for('autoapply.index'))

    return render_template('autoapply_candidato.html', candidato=cand)


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
    return render_template('autoapply_oferta.html', job=job)


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
