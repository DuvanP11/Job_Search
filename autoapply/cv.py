#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integración con CV existente."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

from .storage import get_store

logger = logging.getLogger(__name__)

COLECCION_CV = 'cv'
COLECCION_CANDIDATO = 'candidate'


def obtener_perfil_profesional(user_id: Any) -> Dict[str, Any]:
    store = get_store()
    candidato = store.get(COLECCION_CANDIDATO, user_id, 'principal')
    if candidato:
        return candidato
    try:
        from utils.cv_bot import CVBot
        bot = CVBot(user_id)
        resumen = bot.get_resumen_profesional()
        if resumen:
            candidato = {
                'id': 'principal',
                'source': 'cv_bot',
                'nombre_completo': resumen.get('nombre', ''),
                'email': resumen.get('email', ''),
                'telefono': resumen.get('telefono', ''),
                'ciudad': resumen.get('ciudad', ''),
                'titular': resumen.get('perfil_profesional', ''),
                'resumen': resumen.get('perfil_profesional', ''),
                'anios_experiencia': resumen.get('anios_experiencia', 0),
                'habilidades': resumen.get('habilidades', []),
                'educacion': resumen.get('educacion', []),
                'experiencia': resumen.get('experiencia', []),
                'idiomas': resumen.get('idiomas', []),
                'campos_confirmados': [],
            }
            store.save(COLECCION_CANDIDATO, user_id, candidato, record_id='principal')
            return candidato
    except Exception as exc:  # noqa: BLE001
        logger.error('No se pudo cargar perfil desde cv_bot: %s', exc)
    return {}


def guardar_perfil_profesional(user_id: Any, candidato: Dict[str, Any]) -> Dict[str, Any]:
    store = get_store()
    candidato = copy.deepcopy(candidato)
    candidato['id'] = 'principal'
    guardado, _ = store.save(COLECCION_CANDIDATO, user_id, candidato, record_id='principal')
    return guardado


def cargar_cv(user_id: Any) -> Optional[Dict[str, Any]]:
    store = get_store()
    return store.get(COLECCION_CV, user_id, 'principal')


def guardar_cv(user_id: Any, cv: Dict[str, Any]) -> Dict[str, Any]:
    store = get_store()
    cv = copy.deepcopy(cv)
    cv['id'] = 'principal'
    guardado, _ = store.save(COLECCION_CV, user_id, cv, record_id='principal')
    return guardado


def adaptar_cv_para_oferta(cv_texto: str, job: Dict[str, Any], max_lineas: int = 60) -> str:
    if not cv_texto:
        return ''
    descripcion = (job.get('descripcion') or '')[:1500].lower()
    lineas = cv_texto.split('\n')
    relevantes = []
    irrelevantes = []
    for linea in lineas:
        l = linea.lower()
        if not l.strip():
            continue
        if any(p in l for p in descripcion.split() if len(p) > 4):
            relevantes.append(linea)
        elif len(l) < 80:
            relevantes.append(linea)
        else:
            irrelevantes.append(linea)
    resultado = relevantes + [l for l in irrelevantes if len(relevantes) < max_lineas]
    return '\n'.join(resultado[:max_lineas])
