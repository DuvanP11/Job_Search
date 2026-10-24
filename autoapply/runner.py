#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ejecución con modos y límites."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .engine import AutoApplyEngine
from .security import validar_config_perfil, requiere_confirmacion_humana

logger = logging.getLogger(__name__)


class AutoApplyRunner:
    def __init__(self, store=None):
        self.engine = AutoApplyEngine(store=store)

    def ejecutar(self, user_id: Any, profile: Dict[str, Any],
                 candidate: Dict[str, Any], modo: str = 'simulacion',
                 confirmar_todo: bool = False) -> Dict[str, Any]:
        config = profile.get('config') or {}
        errores_validacion = validar_config_perfil(config)
        if errores_validacion:
            return {'ok': False, 'errores': errores_validacion}

        desc = self.engine.descubrir(user_id, profile, candidate)
        pendientes = self.engine.listar(user_id, status='en_evaluacion')

        resultado = {
            'ok': True,
            'modo': modo,
            'descubiertas': desc['nuevas'],
            'candidatas': [],
            'saltadas': [],
            'postuladas': 0,
            'errores': desc['errores'] + desc['advertencias'],
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        max_diario = int(config.get('max_postulaciones_diarias') or 5)
        hora = datetime.now().hour
        horario = config.get('horario') or {}
        desde = horario.get('desde', '08:00')
        hasta = horario.get('hasta', '18:00')
        try:
            h_desde = int(str(desde).split(':')[0])
            h_hasta = int(str(hasta).split(':')[0])
            if not (h_desde <= hora <= h_hasta):
                resultado['errores'].append(
                    f'Fuera de horario configurado ({desde} - {hasta}).'
                )
        except Exception:
            pass

        hoy = datetime.now(timezone.utc).date()
        estadisticas = self.engine.estadisticas(user_id)
        ya_hoy = estadisticas.get('postuladas', 0)

        for oferta in pendientes:
            if ya_hoy >= max_diario:
                resultado['saltadas'].append({
                    'id': oferta.get('id'),
                    'motivo': f'Límite diario alcanzado ({max_diario})',
                })
                continue

            puntuacion = int(oferta.get('puntuacion') or 0)
            min_puntuacion = int(config.get('puntuacion_minima') or 60)
            if puntuacion < min_puntuacion:
                resultado['saltadas'].append({
                    'id': oferta.get('id'),
                    'titulo': oferta.get('titulo'),
                    'motivo': f'Puntuación {puntuacion} < {min_puntuacion}',
                })
                self.engine.actualizar_estado(user_id, oferta['id'], 'descartada',
                                              f'Puntuación inferior al mínimo ({puntuacion})')
                continue

            if oferta.get('filtros', {}).get('pasa') is False:
                resultado['saltadas'].append({
                    'id': oferta.get('id'),
                    'titulo': oferta.get('titulo'),
                    'motivo': 'No pasa filtros',
                })
                continue

            if requiere_confirmacion_humana(oferta, modo) and not confirmar_todo:
                resultado['candidatas'].append({
                    'id': oferta.get('id'),
                    'titulo': oferta.get('titulo'),
                    'empresa': oferta.get('empresa'),
                    'portal': oferta.get('portal'),
                    'puntuacion': puntuacion,
                    'url': oferta.get('url'),
                    'estado_propuesto': 'pendiente_revision',
                })
                self.engine.actualizar_estado(user_id, oferta['id'], 'pendiente_revision',
                                              'Pendiente de aprobación humana')
                continue

            if modo == 'simulacion':
                resultado['candidatas'].append({
                    'id': oferta.get('id'),
                    'titulo': oferta.get('titulo'),
                    'empresa': oferta.get('empresa'),
                    'portal': oferta.get('portal'),
                    'puntuacion': puntuacion,
                    'url': oferta.get('url'),
                    'estado_propuesto': 'simulado',
                })
                continue

            prep = self.engine.preparar_postulacion(user_id, oferta['id'], candidate)
            if prep.get('error'):
                resultado['errores'].append(prep['error'])
                continue
            if prep['preparacion'].get('requiere_intervencion'):
                resultado['saltadas'].append({
                    'id': oferta.get('id'),
                    'titulo': oferta.get('titulo'),
                    'motivo': 'Requiere intervención humana en el portal',
                })
                self.engine.actualizar_estado(user_id, oferta['id'], 'requiere_intervencion',
                                              prep['preparacion'].get('mensaje', ''))
                continue

            resultado['postuladas'] += 1
            ya_hoy += 1
            self.engine.actualizar_estado(user_id, oferta['id'], 'enviada_sin_confirmacion',
                                          'Procesado en modo automático (sin confirmación verificable)')

        return resultado
