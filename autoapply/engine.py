#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de descubrimiento y evaluación."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .adapters import obtener_adapter
from .dedupe import buscar_duplicado, marcar_historial, ya_postulado
from .jobs import aplicar_filtros, normalizar_job
from .models import ESTADOS
from .scoring import puntuar_oferta
from .storage import get_store, huella_job

logger = logging.getLogger(__name__)


class AutoApplyEngine:
    def __init__(self, store=None):
        self.store = store or get_store()

    def descubrir(self, user_id: Any, profile: Dict[str, Any],
                  candidate: Dict[str, Any]) -> Dict[str, Any]:
        config = profile.get('config') or {}
        portales = config.get('portales') or []
        nuevas = []
        errores = []
        advertencias = []

        for portal in portales:
            adapter = obtener_adapter(portal)
            if not adapter:
                errores.append(f'No hay adaptador para {portal}')
                continue
            try:
                resultado = adapter.buscar(config)
                for oferta in resultado.ofertas:
                    oferta = normalizar_job(oferta, portal)
                    if ya_postulado(oferta, self.store, user_id):
                        continue
                    duplicado = buscar_duplicado(oferta, self.store, user_id)
                    if duplicado:
                        continue
                    filtros = aplicar_filtros(oferta, profile, candidate)
                    puntuacion, detalle = puntuar_oferta(oferta, profile, candidate)
                    oferta['filtros'] = filtros
                    oferta['puntuacion'] = puntuacion
                    oferta['scoring'] = detalle
                    oferta['status'] = 'en_evaluacion' if filtros['pasa'] else 'descartada'
                    guardado = marcar_historial(oferta, self.store, user_id, oferta['status'])
                    nuevas.append(guardado)
                errores.extend(resultado.errores)
                advertencias.extend(resultado.advertencias)
            except Exception as exc:  # noqa: BLE001
                logger.error('Error descubriendo en %s: %s', portal, exc)
                errores.append(str(exc))

        return {
            'nuevas': len(nuevas),
            'ofertas': nuevas,
            'errores': errores,
            'advertencias': advertencias,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    def listar(self, user_id: Any, status: str = None, portal: str = None,
               limit: int = 100) -> List[Dict[str, Any]]:
        def filtrar(r):
            if status and r.get('status') != status:
                return False
            if portal and r.get('portal') != portal:
                return False
            return True
        return self.store.list('jobs', user_id, where=filtrar, limit=limit)

    def obtener(self, user_id: Any, job_id: str) -> Dict[str, Any]:
        return self.store.get('jobs', user_id, job_id)

    def actualizar_estado(self, user_id: Any, job_id: str, status: str,
                          motivo: str = '') -> Dict[str, Any]:
        def fn(actual):
            actual['status'] = status
            if motivo:
                actual['motivo_cambio'] = motivo
            actual['historial_cambios'] = actual.get('historial_cambios') or []
            actual['historial_cambios'].append({
                'fecha': datetime.now(timezone.utc).isoformat(),
                'estado': status,
                'motivo': motivo,
            })
            return actual
        return self.store.mutate('jobs', user_id, job_id, fn)

    def preparar_postulacion(self, user_id: Any, job_id: str, candidato: Dict[str, Any],
                             credenciales: Dict[str, Any] = None) -> Dict[str, Any]:
        job = self.store.get('jobs', user_id, job_id)
        if not job:
            return {'error': 'Oferta no encontrada'}
        adapter = obtener_adapter(job.get('portal'))
        if not adapter:
            return {'error': 'Sin adaptador para este portal'}
        prep = adapter.preparar(job, candidato, credenciales)
        self.actualizar_estado(user_id, job_id, 'pendiente_revision',
                               'Preparado para revisión')
        return {
            'job': job,
            'preparacion': {
                'listo': prep.listo_para_postular,
                'requiere_captcha': prep.requiere_captcha,
                'requiere_mfa': prep.requiere_mfa,
                'requiere_login': prep.requiere_login,
                'requiere_intervencion': prep.requiere_intervencion,
                'campos_faltantes': prep.campos_faltantes,
                'acciones_humano': prep.acciones_humano,
                'mensaje': prep.mensaje,
            },
            'estados': ESTADOS,
        }

    def marcar_como_postulado(self, user_id: Any, job_id: str, confirmado: bool = False,
                              evidencia: str = '') -> Dict[str, Any]:
        status = 'postulacion_confirmada' if confirmado else 'enviada_sin_confirmacion'
        motivo = 'Marcado manualmente como postulado' if not evidencia else f'Marcado con evidencia: {evidencia[:200]}'
        return self.actualizar_estado(user_id, job_id, status, motivo)

    def estadisticas(self, user_id: Any) -> Dict[str, Any]:
        ofertas = self.store.list('jobs', user_id)
        total = len(ofertas)
        por_estado = {}
        por_portal = {}
        for oferta in ofertas:
            e = oferta.get('status', 'desconocido')
            por_estado[e] = por_estado.get(e, 0) + 1
            p = oferta.get('portal', 'otro')
            por_portal[p] = por_portal.get(p, 0) + 1
        estados_postulado = ['enviada_sin_confirmacion', 'postulacion_confirmada']
        postuladas = sum(por_estado.get(e, 0) for e in estados_postulado)

        # Postulaciones de hoy (UTC), leídas del historial de cada oferta.
        hoy = datetime.now(timezone.utc).date()
        postuladas_hoy = 0
        for oferta in ofertas:
            if oferta.get('status') not in estados_postulado:
                continue
            historial = oferta.get('historial_cambios') or []
            marcas = [h.get('fecha') for h in historial
                      if h.get('estado') in estados_postulado and h.get('fecha')]
            marca = marcas[-1] if marcas else oferta.get('updated_at')
            try:
                if marca and datetime.fromisoformat(str(marca).replace('Z', '+00:00')).date() == hoy:
                    postuladas_hoy += 1
            except (TypeError, ValueError):
                continue

        return {
            'total': total,
            'postuladas': postuladas,
            'postuladas_hoy': postuladas_hoy,
            'pendientes': por_estado.get('pendiente_revision', 0) + por_estado.get('lista_para_postular', 0),
            'descartadas': por_estado.get('descartada', 0),
            'por_estado': por_estado,
            'por_portal': por_portal,
        }
