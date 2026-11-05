#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Páginas del módulo AI AUTO APPLY: panel, cola, autonomía, IA, fuentes, actividad, historial, privacidad."""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List

from flask import Response, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from . import bitacora
from .adapters import REGISTRO, listar_adapters
from .ai import AIRouter, router_para_usuario
from .ai.base import TAREAS
from .ai.providers import REGISTRO as PROVEEDORES
from .autorizacion import autorizar_envio
from .browser import portales_con_envio
from .cola import ColaTrabajo
from .cv import obtener_perfil_profesional
from .engine import AutoApplyEngine
from .models import (DEFAULT_PROFILE_CONFIG, ESTADOS, ESTADOS_CONFIRMADOS, ESTADOS_POSTULADOS, MODOS,
                     PORTALES_NO_DISPONIBLES, PORTALES_SOPORTADOS)
from .pipeline import envio_real_habilitado
from .routes import _get_perfil, _guardar_perfil, _requiere_login, _user_id, autoapply_bp
from .storage import ahora_iso, get_store

COLECCIONES_USUARIO = ('profiles', 'candidate', 'cv', 'jobs', 'documents', 'authorizations', 'agent_log',
                       'queue', 'worker_state', 'settings')


def _config(store, owner) -> Dict[str, Any]:
    cfg = {**DEFAULT_PROFILE_CONFIG, **((_get_perfil(store, owner) or {}).get('config') or {})}
    cfg['autonomo'] = {**DEFAULT_PROFILE_CONFIG['autonomo'], **(cfg.get('autonomo') or {})}
    cfg['programacion'] = {**DEFAULT_PROFILE_CONFIG['programacion'], **(cfg.get('programacion') or {})}
    return cfg


def _latido(store) -> Dict[str, Any]:
    r = store.get('worker_state', '_sistema', 'latido') or {}
    if not r.get('ts'):
        return {'activo': False, 'texto': 'El worker nunca se ha ejecutado.'}
    seg = (datetime.now(timezone.utc) - datetime.fromisoformat(r['ts'])).total_seconds()
    return {'activo': seg < 300, 'hace_seg': int(seg), 'envio_real': r.get('envio_real'),
            'texto': f"Último latido hace {int(seg // 60)} min" + ('' if seg < 300 else ' — el worker parece detenido.')}


def estadisticas_panel(store, owner) -> Dict[str, Any]:
    jobs = store.list('jobs', owner)
    por = lambda *ests: sum(1 for j in jobs if j.get('status') in ests)             # noqa: E731
    vivos = [j for j in jobs if j.get('status') != 'descartada' and j.get('puntuacion') is not None]
    return {
        'descubiertas': len(jobs),
        'compatibles': len([j for j in jobs if j.get('status') not in ('descartada', 'error')
                            and (j.get('matching') or {}).get('apto', True)]),
        'preparadas': por('pendiente_autorizacion', 'lista_para_postular', 'pendiente_revision'),
        'por_autorizar': por('pendiente_autorizacion', 'lista_para_postular'),
        'enviadas': por(*ESTADOS_POSTULADOS),
        'confirmadas': por(*ESTADOS_CONFIRMADOS),
        'entrevistas': por('entrevista'),
        'ofertas': por('oferta_laboral'),
        'requieren_usuario': por('requiere_intervencion'),
        'compat_promedio': round(sum(j['puntuacion'] for j in vivos) / len(vivos)) if vivos else None,
    }


# -------------------------------------------------------------- 1. Panel
@autoapply_bp.route('/panel')
@_requiere_login
def panel():
    store, owner = get_store(), _user_id()
    cfg = _config(store, owner)
    return render_template('autoapply_panel.html', s=estadisticas_panel(store, owner),
                           actividad=bitacora.listar(store, owner, 8), latido=_latido(store), cfg=cfg,
                           modo=MODOS.get(cfg.get('modo'), cfg.get('modo')), envio_real=envio_real_habilitado(),
                           tareas=ColaTrabajo(store).listar(owner))


# -------------------------------------------------------------- 6. Cola
@autoapply_bp.route('/cola')
@_requiere_login
def cola():
    store, owner = get_store(), _user_id()
    jobs = store.list('jobs', owner)
    docs = {}
    for d in store.list('documents', owner):
        docs.setdefault(d['job_id'], []).append(d)
    return render_template(
        'autoapply_cola.html',
        por_autorizar=sorted([j for j in jobs if j['status'] in ('pendiente_autorizacion', 'lista_para_postular')],
                             key=lambda j: -(j.get('puntuacion') or 0)),
        intervencion=[j for j in jobs if j['status'] == 'requiere_intervencion'],
        tareas=ColaTrabajo(store).listar(owner), docs=docs, latido=_latido(store),
        con_envio=portales_con_envio(), envio_real=envio_real_habilitado())


@autoapply_bp.route('/oferta/<job_id>/autorizar', methods=['POST'])
@_requiere_login
def autorizar(job_id):
    """El usuario autoriza el envío de ESTA oferta con los documentos actuales."""
    store, owner = get_store(), _user_id()
    job = store.get('jobs', owner, job_id)
    docs = [d for d in store.list('documents', owner, where=lambda r: r.get('job_id') == job_id)]
    ultimos = {}
    for d in sorted(docs, key=lambda r: r.get('created_at', ''), reverse=True):
        ultimos.setdefault(d['tipo'], d)
    if not job or len(ultimos) < 2:
        flash('Genera primero el CV y la carta de esta vacante.', 'warning')
        return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))
    if job['status'] in ESTADOS_POSTULADOS:
        flash('Ya existe una postulación a esta oferta.', 'warning')
        return redirect(url_for('autoapply.oferta_detalle', job_id=job_id))
    autorizar_envio(store, owner, job_id, list(ultimos.values()))
    ColaTrabajo(store).encolar(owner, job_id, 'enviar')
    bitacora.registrar(store, owner, 'autorizacion', 'El usuario autorizó el envío.', job_id=job_id)
    flash('Envío autorizado y puesto en la cola del agente.' +
          ('' if envio_real_habilitado() else ' El worker está en modo prueba: rellenará y verificará el formulario sin enviarlo '
           '(para enviar de verdad, el operador debe iniciar el worker con AUTOAPPLY_ENABLE_SUBMIT=1).'), 'success')
    return redirect(url_for('autoapply.cola'))


@autoapply_bp.route('/cola/<tarea_id>/cancelar', methods=['POST'])
@_requiere_login
def cancelar_tarea(tarea_id):
    ColaTrabajo(get_store()).cancelar(_user_id(), tarea_id)
    flash('Tarea cancelada.', 'info')
    return redirect(url_for('autoapply.cola'))


# -------------------------------------------------------------- 7. Auto Apply (autonomía)
@autoapply_bp.route('/autonomo', methods=['GET', 'POST'])
@_requiere_login
def autonomo():
    store, owner = get_store(), _user_id()
    perfil = _get_perfil(store, owner) or {}
    cfg = _config(store, owner)
    if request.method == 'POST':
        f, accion = request.form, request.form.get('accion')
        if accion == 'desactivar':
            cfg['autonomo']['habilitado'] = False
            flash('Modo autónomo DESACTIVADO.', 'success')
        elif accion == 'activar':
            if f.get('confirmacion', '').strip().upper() != 'ACTIVAR' or not f.get('acepto'):
                flash('Para activarlo escribe ACTIVAR y marca la casilla de aceptación.', 'danger')
                return redirect(url_for('autoapply.autonomo'))
            if not cfg.get('cargos') or not cfg.get('portales'):
                flash('Configura antes tus cargos y portales en Preferencias laborales.', 'warning')
                return redirect(url_for('autoapply.autonomo'))
            cfg['autonomo']['habilitado'], cfg['autonomo']['habilitado_en'] = True, ahora_iso()
            flash('Modo autónomo ACTIVADO. Solo enviará ofertas que cumplan TODAS tus reglas.', 'warning')
        else:
            cfg['modo'] = f.get('modo') if f.get('modo') in MODOS else 'revision'
            cfg['autonomo']['empresas_permitidas'] = [x.strip() for x in f.get('empresas_permitidas', '').split('\n') if x.strip()]
            cfg['autonomo']['permitir_respuestas_ia'] = bool(f.get('permitir_respuestas_ia'))
            cfg['autonomo']['ventana_horaria'] = bool(f.get('ventana_horaria'))
            try:
                cfg['max_postulaciones_diarias'] = max(1, min(50, int(f.get('max_postulaciones_diarias') or 5)))
                cfg['puntuacion_minima'] = max(0, min(100, int(f.get('puntuacion_minima') or 60)))
                cfg['programacion'] = {'activa': bool(f.get('prog_activa')),
                                       'cada_horas': max(1, min(168, float(f.get('prog_cada_horas') or 24))),
                                       'max_vacantes': max(1, min(500, int(f.get('prog_max_vacantes') or 50)))}
            except ValueError:
                flash('Los límites deben ser números.', 'danger')
                return redirect(url_for('autoapply.autonomo'))
            flash('Configuración guardada.', 'success')
        perfil['config'] = cfg
        _guardar_perfil(store, owner, perfil)
        bitacora.registrar(store, owner, 'config_autonomia', f"modo={cfg['modo']} autónomo={cfg['autonomo']['habilitado']}")
        return redirect(url_for('autoapply.autonomo'))
    return render_template('autoapply_autonomo.html', cfg=cfg, modos=MODOS, con_envio=portales_con_envio(),
                           envio_real=envio_real_habilitado(), latido=_latido(store))


# -------------------------------------------------------------- 10. Configuración de IA
@autoapply_bp.route('/ia', methods=['GET', 'POST'])
@_requiere_login
def ia():
    store, owner = get_store(), _user_id()
    if request.method == 'POST':
        tareas = {}
        for t in TAREAS:
            prov, modelo = request.form.get(f'prov_{t}', ''), request.form.get(f'modelo_{t}', '').strip()[:80]
            if prov in PROVEEDORES:
                tareas[t] = [{'proveedor': prov, 'modelo': modelo}]
        store.save('settings', owner, {'id': 'ia', 'tareas': tareas})
        flash('Configuración de IA guardada. Las claves de API nunca se guardan aquí: van en variables de entorno.', 'success')
        return redirect(url_for('autoapply.ia'))
    guardado = (store.get('settings', owner, 'ia') or {}).get('tareas') or {}
    return render_template('autoapply_ia.html', estado=router_para_usuario(store, owner).estado(), tareas=TAREAS,
                           guardado={t: (v[0] if v else {}) for t, v in guardado.items()}, proveedores=list(PROVEEDORES))


# -------------------------------------------------------------- 11. Fuentes
@autoapply_bp.route('/fuentes')
@_requiere_login
def fuentes():
    store, owner = get_store(), _user_id()
    cfg = _config(store, owner)
    claves_cfg = {'greenhouse': 'greenhouse_boards', 'lever': 'lever_companies', 'ashby': 'ashby_boards',
                  'smartrecruiters': 'smartrecruiters_companies'}
    ultimo = next((e for e in bitacora.listar(store, owner, 50) if e['evento'] == 'descubrir'), None)
    filas = []
    for a in listar_adapters():
        k = a['clave']
        filas.append({**a, 'habilitada': k in (cfg.get('portales') or []),
                      'envio': k in portales_con_envio(),
                      'configurados': len(cfg.get(claves_cfg[k], [])) if k in claves_cfg else None,
                      'info': PORTALES_SOPORTADOS.get(k, {}).get('nota', '')})
    return render_template('autoapply_fuentes.html', filas=filas, no_disponibles=PORTALES_NO_DISPONIBLES, ultimo=ultimo)


# -------------------------------------------------------------- 12. Actividad
@autoapply_bp.route('/actividad')
@_requiere_login
def actividad():
    store, owner = get_store(), _user_id()
    nivel = request.args.get('nivel') or ''
    return render_template('autoapply_actividad.html', registros=bitacora.listar(store, owner, 200, nivel=nivel),
                           nivel=nivel, latido=_latido(store))


# -------------------------------------------------------------- 8. Historial y evidencia
@autoapply_bp.route('/historial')
@_requiere_login
def historial():
    store, owner = get_store(), _user_id()
    postuladas = [j for j in store.list('jobs', owner) if j.get('status') in ESTADOS_POSTULADOS | {'cerrada'}]
    for j in postuladas:
        j['_capturas'] = [c for c in (j.get('evidencia_envio') or {}).get('capturas', []) if c]
        marcas = [h.get('fecha') for h in j.get('historial_cambios') or [] if h.get('estado') in ESTADOS_POSTULADOS]
        j['_fecha'] = (marcas[0] if marcas else j.get('updated_at', ''))[:10]
    postuladas.sort(key=lambda j: j['_fecha'], reverse=True)
    return render_template('autoapply_historial.html', jobs=postuladas, estados=ESTADOS, confirmados=ESTADOS_CONFIRMADOS)


@autoapply_bp.route('/evidencia/<job_id>/<int:n>')
@_requiere_login
def evidencia(job_id, n):
    store, owner = get_store(), _user_id()
    job = store.get('jobs', owner, job_id)
    ev = ((job or {}).get('evidencia_envio') or (job or {}).get('evidencia_dry_run') or {})
    capturas = [c for c in ev.get('capturas', []) if c]
    base = os.path.realpath(os.path.join(store.data_dir, 'evidencia', str(owner), job_id))
    if not job or n >= len(capturas):
        abort(404)
    ruta = os.path.realpath(capturas[n])
    if not ruta.startswith(base + os.sep) or not os.path.isfile(ruta):      # nunca fuera de su carpeta
        abort(404)
    return send_file(ruta, mimetype='image/png')


# -------------------------------------------------------------- 9. Documentos
@autoapply_bp.route('/documentos')
@_requiere_login
def documentos():
    store, owner = get_store(), _user_id()
    docs = sorted(store.list('documents', owner), key=lambda d: d.get('created_at', ''), reverse=True)
    return render_template('autoapply_documentos.html', docs=docs[:200])


# -------------------------------------------------------------- Privacidad: exportar y borrar
@autoapply_bp.route('/privacidad', methods=['GET', 'POST'])
@_requiere_login
def privacidad():
    store, owner = get_store(), _user_id()
    if request.method == 'POST':
        if request.form.get('confirmacion', '').strip().upper() != 'ELIMINAR':
            flash('Escribe ELIMINAR para confirmar el borrado.', 'danger')
            return redirect(url_for('autoapply.privacidad'))
        borrados = sum(store.delete_collection(c, owner) for c in COLECCIONES_USUARIO)
        shutil.rmtree(os.path.join(store.data_dir, 'evidencia', str(owner)), ignore_errors=True)
        flash(f'Se eliminaron {borrados} registros y las capturas de evidencia de este módulo.', 'success')
        return redirect(url_for('autoapply.privacidad'))
    return render_template('autoapply_privacidad.html')


@autoapply_bp.route('/privacidad/exportar')
@_requiere_login
def exportar():
    store, owner = get_store(), _user_id()
    volcado = {c: store.list(c, owner) for c in COLECCIONES_USUARIO}
    volcado['_exportado_en'] = ahora_iso()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('datos.json', json.dumps(volcado, ensure_ascii=False, indent=2, default=str))
        base = os.path.join(store.data_dir, 'evidencia', str(owner))
        for raiz, _, archivos in os.walk(base):
            for a in archivos:
                z.write(os.path.join(raiz, a), os.path.join('evidencia', os.path.relpath(os.path.join(raiz, a), base)))
    return Response(buf.getvalue(), mimetype='application/zip', headers={
        'Content-Disposition': 'attachment; filename="auto_apply_datos.zip"', 'X-Content-Type-Options': 'nosniff'})


@autoapply_bp.route('/api/worker')
@_requiere_login
def api_worker():
    return jsonify({**_latido(get_store()), 'envio_real_en_este_proceso': envio_real_habilitado()})
