#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestación: DISCOVERY → MATCHING → DOCUMENTOS → AUTORIZACIÓN → ENVÍO → CONFIRMACIÓN → SEGUIMIENTO.

El navegador solo se usa en la acción 'enviar', y solo si hay autorización
(manual vigente o reglas autónomas cumplidas). Un envío se marca confirmado
únicamente con evidencia del portal. Ante CAPTCHA/MFA/preguntas sensibles el
proceso se detiene y pasa al usuario.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import bitacora
from .autorizacion import (autorizacion_vigente, autorizar_envio, consumir_autorizacion, evaluar_autonomo)
from .browser import (CONFIRMADO, DRY_RUN, ENVIADO_SIN_CONFIRMACION, ERROR, REQUIERE_USUARIO,
                      SolicitudAplicacion, obtener_aplicador)
from .cola import ColaTrabajo
from .cv import obtener_perfil_profesional
from .documents import (carta_a_pdf, construir_datos_cv, cv_a_pdf, generar_carta, responder_pregunta)
from .engine import AutoApplyEngine
from .models import DEFAULT_PROFILE_CONFIG, ESTADOS_POSTULADOS
from .storage import get_store

logger = logging.getLogger(__name__)


def envio_real_habilitado() -> bool:
    """Interruptor del operador: sin esta variable el agente solo rellena y verifica (dry-run)."""
    return os.getenv('AUTOAPPLY_ENABLE_SUBMIT', '') == '1'


class Orquestador:
    def __init__(self, store=None, router=None, ahora=None):
        self.store = store or get_store()
        self.engine = AutoApplyEngine(self.store)
        self.cola = ColaTrabajo(self.store)
        self.router = router
        self._ahora = ahora

    # ------------------------------------------------------------- utilidades
    def _perfil(self, owner) -> Dict[str, Any]:
        p = self.store.get('profiles', owner, 'default') or {}
        cfg = {**DEFAULT_PROFILE_CONFIG, **(p.get('config') or {})}
        cfg['autonomo'] = {**DEFAULT_PROFILE_CONFIG['autonomo'], **(cfg.get('autonomo') or {})}
        return {**p, 'config': cfg}

    def _docs(self, owner, job_id: str) -> List[Dict[str, Any]]:
        docs = self.store.list('documents', owner, where=lambda r: r.get('job_id') == job_id)
        ultimos: Dict[str, Dict[str, Any]] = {}
        for d in sorted(docs, key=lambda r: r.get('created_at', ''), reverse=True):
            ultimos.setdefault(d['tipo'], d)
        return list(ultimos.values())

    def _log(self, owner, evento, detalle='', nivel='info', job_id='', tarea_id='', **extra):
        bitacora.registrar(self.store, owner, evento, detalle, nivel, job_id, tarea_id, extra or None)

    # ------------------------------------------------------------- descubrir
    def descubrir(self, owner) -> Dict[str, Any]:
        perfil, cand = self._perfil(owner), obtener_perfil_profesional(owner)
        cfg = perfil['config']
        if not cfg.get('cargos') or not cfg.get('portales'):
            self._log(owner, 'descubrir_omitido', 'Falta configurar cargos o portales.', 'warning')
            return {'nuevas': 0, 'omitido': True}
        r = self.engine.descubrir(owner, perfil, cand)
        tope = int((cfg.get('programacion') or {}).get('max_vacantes') or 50)
        encoladas = 0
        if cfg.get('modo') in ('revision', 'automatico'):
            for o in sorted([x for x in r['ofertas'] if x['status'] == 'en_evaluacion'],
                            key=lambda x: -(x.get('puntuacion') or 0))[:tope]:
                if o['puntuacion'] >= int(cfg.get('puntuacion_minima') or 60):
                    _, nueva = self.cola.encolar(owner, o['id'], 'preparar')
                    encoladas += nueva
        self._log(owner, 'descubrir', f"{r['nuevas']} nuevas, {encoladas} para preparar, {len(r['errores'])} errores.",
                  'warning' if r['errores'] else 'info', extra_errores=r['errores'][:5])
        return {'nuevas': r['nuevas'], 'preparar_encoladas': encoladas, 'errores': r['errores'],
                'advertencias': r['advertencias']}

    # --------------------------------------------------------------- preparar
    def preparar(self, owner, job_id: str, tarea_id: str = '') -> Dict[str, Any]:
        job = self.engine.obtener(owner, job_id)
        if not job:
            return {'ok': False, 'error': 'Oferta no encontrada'}
        if job['status'] in ESTADOS_POSTULADOS:
            return {'ok': True, 'omitida': 'ya postulada'}
        cand, cfg = obtener_perfil_profesional(owner), self._perfil(owner)['config']
        if not (cand.get('nombre_completo') and (cand.get('experiencia') or cand.get('habilidades'))):
            self.engine.actualizar_estado(owner, job_id, 'pendiente_documentos', 'Perfil profesional incompleto')
            self._log(owner, 'preparar_bloqueado', 'Perfil incompleto', 'warning', job_id, tarea_id)
            return {'ok': False, 'requiere_usuario': 'Completa tu perfil profesional.'}
        cv_res = construir_datos_cv(cand, job, router=self.router)
        carta = generar_carta(cand, job, cv_res['habilidades_coincidentes'], router=self.router)
        base = {'job_id': job_id, 'empresa': job.get('empresa', ''), 'cargo': job.get('titulo', '')}
        self.store.save('documents', owner, {**base, 'tipo': 'cv', 'contenido': cv_res['datos'],
                                             'generado_con': cv_res['generado_con'],
                                             'advertencias': cv_res['advertencias'],
                                             'coincidentes': cv_res['habilidades_coincidentes']})
        self.store.save('documents', owner, {**base, 'tipo': 'carta', 'contenido': carta['texto'],
                                             'generado_con': carta['generado_con'], 'idioma': carta['idioma'],
                                             'advertencias': carta['advertencias']})
        self.engine.actualizar_estado(owner, job_id, 'pendiente_autorizacion', 'Documentos listos; falta autorización')
        self._log(owner, 'documentos', f"CV y carta generados ({cv_res['generado_con']}).", job_id=job_id, tarea_id=tarea_id)
        if cfg.get('modo') == 'automatico':
            self.cola.encolar(owner, job_id, 'enviar')
        return {'ok': True}

    # ------------------------------------------------------------------ enviar
    def _archivos(self, docs, destino: str) -> Dict[str, str]:
        rutas = {}
        for d in docs:
            ruta = os.path.join(destino, f"{d['tipo']}.pdf")
            with open(ruta, 'wb') as fh:
                fh.write(cv_a_pdf(d['contenido']) if d['tipo'] == 'cv' else carta_a_pdf(d['contenido']))
            rutas[d['tipo']] = ruta
        return rutas

    def enviar(self, owner, job_id: str, tarea_id: str = '', aplicador=None) -> Dict[str, Any]:
        job = self.engine.obtener(owner, job_id)
        if not job:
            return {'estado': ERROR, 'motivo': 'Oferta no encontrada'}
        if job['status'] in ESTADOS_POSTULADOS:
            return {'estado': 'omitida', 'motivo': 'Ya existe una postulación a esta oferta.'}
        perfil, cand = self._perfil(owner), obtener_perfil_profesional(owner)
        cfg = perfil['config']
        docs = self._docs(owner, job_id)
        aplicador = aplicador or obtener_aplicador(job.get('portal'))

        # 1) ¿hay permiso? manual vigente, o reglas autónomas cumplidas
        manual, motivo_manual = autorizacion_vigente(self.store, owner, job_id, docs) if docs else (False, 'Faltan documentos.')
        autonomo = False
        motivos_auto: List[str] = []
        if not manual and cfg.get('modo') == 'automatico':
            autonomo, motivos_auto = evaluar_autonomo(
                job, perfil, docs_listos=len(docs) >= 2, adapter_envia=bool(aplicador and aplicador.soporta(job)),
                postuladas_hoy=self.engine.estadisticas(owner)['postuladas_hoy'], ahora=self._ahora)
        if not (manual or autonomo):
            motivo = '; '.join(motivos_auto) if motivos_auto else motivo_manual
            self.engine.actualizar_estado(owner, job_id, 'pendiente_autorizacion', motivo)
            self._log(owner, 'envio_no_autorizado', motivo, 'warning', job_id, tarea_id)
            return {'estado': REQUIERE_USUARIO, 'motivo': motivo}
        if not aplicador or not aplicador.soporta(job):
            motivo = 'Este portal no tiene envío automatizado: postula manualmente desde el enlace de la oferta.'
            self.engine.actualizar_estado(owner, job_id, 'requiere_intervencion', motivo)
            self._log(owner, 'sin_aplicador', motivo, 'warning', job_id, tarea_id)
            return {'estado': REQUIERE_USUARIO, 'motivo': motivo}

        # 2) navegador
        enviar_real = envio_real_habilitado()
        self.engine.actualizar_estado(owner, job_id, 'enviando', 'El agente está completando el formulario')
        self._log(owner, 'envio_inicio', f"{'ENVÍO REAL' if enviar_real else 'dry-run (sin enviar)'} vía "
                  f"{'autorización manual' if manual else 'reglas autónomas'}", job_id=job_id, tarea_id=tarea_id)
        carpeta = tempfile.mkdtemp(prefix='autoapply_')
        evidencia_dir = os.path.join(self.store.data_dir, 'evidencia', str(owner), job_id)
        os.makedirs(evidencia_dir, exist_ok=True)
        try:
            carta = next((d['contenido'] for d in docs if d['tipo'] == 'carta'), '')
            solicitud = SolicitudAplicacion(
                job=job, candidato=cand, archivos=self._archivos(docs, carpeta), carta_texto=carta,
                enviar_real=enviar_real, carpeta_evidencia=evidencia_dir,
                permitir_respuestas_ia=bool(cfg['autonomo'].get('permitir_respuestas_ia')) and not manual,
                responder=lambda q: responder_pregunta(q, cand, job, router=self.router))
            res = aplicador.aplicar(solicitud)
        except Exception as exc:  # noqa: BLE001 - el navegador puede fallar de mil formas
            logger.exception('Aplicador falló')
            res = type('R', (), {'estado': ERROR, 'motivo': f'{type(exc).__name__}: {exc}'[:300],
                                 'evidencia': {}, 'campos_pendientes': [], 'reintentable': True})()
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
        return self._aplicar_resultado(owner, job_id, tarea_id, res, manual)

    def _aplicar_resultado(self, owner, job_id, tarea_id, res, manual: bool) -> Dict[str, Any]:
        info = {'estado': res.estado, 'motivo': res.motivo, 'evidencia': res.evidencia,
                'campos_pendientes': res.campos_pendientes}
        if res.estado == CONFIRMADO:
            consumir_autorizacion(self.store, owner, job_id)
            self.engine.actualizar_estado(owner, job_id, 'postulacion_confirmada',
                                          f"Confirmado por el portal: {res.evidencia.get('senal', '')}")
            self.store.mutate('jobs', owner, job_id, lambda a: {**a, 'evidencia_envio': res.evidencia})
            self._log(owner, 'envio_confirmado', res.evidencia.get('senal', ''), job_id=job_id, tarea_id=tarea_id)
        elif res.estado == ENVIADO_SIN_CONFIRMACION:
            consumir_autorizacion(self.store, owner, job_id)
            self.engine.actualizar_estado(owner, job_id, 'enviada_sin_confirmacion', res.motivo)
            self.store.mutate('jobs', owner, job_id, lambda a: {**a, 'evidencia_envio': res.evidencia})
            self._log(owner, 'envio_sin_confirmacion', res.motivo, 'warning', job_id, tarea_id)
        elif res.estado == DRY_RUN:
            self.engine.actualizar_estado(owner, job_id, 'lista_para_postular',
                                          'Formulario completado y verificado (no enviado). Activa AUTOAPPLY_ENABLE_SUBMIT=1 en el worker para enviar.')
            self.store.mutate('jobs', owner, job_id, lambda a: {**a, 'evidencia_dry_run': res.evidencia})
            self._log(owner, 'dry_run', 'Formulario verificado sin enviar.', job_id=job_id, tarea_id=tarea_id)
        elif res.estado == REQUIERE_USUARIO:
            self.engine.actualizar_estado(owner, job_id, 'requiere_intervencion', res.motivo)
            self._log(owner, 'requiere_usuario', res.motivo, 'warning', job_id, tarea_id,
                      campos=res.campos_pendientes)
        else:
            self.engine.actualizar_estado(owner, job_id, 'error' if not res.reintentable else 'pendiente_autorizacion',
                                          res.motivo)
            self._log(owner, 'envio_error', res.motivo, 'error', job_id, tarea_id)
        return info

    # --------------------------------------------------------------- tareas
    def procesar_tarea(self, owner, tarea: Dict[str, Any], aplicador=None) -> Dict[str, Any]:
        tid = tarea['id']
        try:
            if tarea['accion'] == 'preparar':
                r = self.preparar(owner, tarea['job_id'], tid)
                if r.get('requiere_usuario'):
                    self.cola.requiere_usuario(owner, tid, r['requiere_usuario'])
                elif r.get('ok'):
                    self.cola.completar(owner, tid, r)
                else:
                    self.cola.fallar(owner, tid, r.get('error', 'desconocido'), reintentable=False)
                return r
            r = self.enviar(owner, tarea['job_id'], tid, aplicador=aplicador)
            if r['estado'] in (CONFIRMADO, ENVIADO_SIN_CONFIRMACION, DRY_RUN, 'omitida'):
                self.cola.completar(owner, tid, {'estado': r['estado']})
            elif r['estado'] == REQUIERE_USUARIO:
                self.cola.requiere_usuario(owner, tid, r['motivo'])
            else:
                self.cola.fallar(owner, tid, r.get('motivo', 'error'), reintentable=True)
            return r
        except Exception as exc:  # noqa: BLE001
            logger.exception('Tarea %s falló', tid)
            self._log(owner, 'tarea_error', f'{type(exc).__name__}: {exc}', 'error', tarea.get('job_id', ''), tid)
            self.cola.fallar(owner, tid, f'{type(exc).__name__}: {exc}', reintentable=True)
            return {'estado': ERROR, 'motivo': str(exc)}

    # ------------------------------------------------------------ programación
    def _toca_descubrir(self, owner, ahora: datetime) -> bool:
        prog = self._perfil(owner)['config'].get('programacion') or {}
        if not prog.get('activa'):
            return False
        estado = self.store.get('worker_state', owner, 'descubrimiento') or {}
        if not estado.get('ultima'):
            return True
        return datetime.fromisoformat(estado['ultima']) + timedelta(hours=float(prog.get('cada_horas') or 24)) <= ahora

    def tick(self, worker: str = 'worker', max_tareas: int = 20, aplicador=None) -> Dict[str, int]:
        """Una pasada: descubrimientos que toquen + tareas pendientes. Idempotente y reanudable."""
        ahora = self._ahora or datetime.now(timezone.utc)
        hechos = {'descubrimientos': 0, 'tareas': 0}
        for owner in self.store.owners('profiles'):
            if self._toca_descubrir(owner, ahora):
                try:
                    self.descubrir(owner)
                except Exception as exc:  # noqa: BLE001
                    self._log(owner, 'descubrir_error', f'{type(exc).__name__}: {exc}', 'error')
                self.store.save('worker_state', owner, {'id': 'descubrimiento', 'ultima': ahora.isoformat()})
                hechos['descubrimientos'] += 1
        for _ in range(max_tareas):
            reclamo = self.cola.reclamar(worker, ahora=self._ahora or datetime.now(timezone.utc))
            if not reclamo:
                break
            owner, tarea = reclamo
            self.procesar_tarea(owner, tarea, aplicador=aplicador)
            hechos['tareas'] += 1
        return hechos
