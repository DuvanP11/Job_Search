#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quién puede enviar qué: autorización manual por oferta y reglas del modo autónomo.

Nada se envía sin una de estas dos cosas:
1. el usuario autorizó ESA oferta con ESOS documentos (si se regeneran, la
   autorización se invalida), o
2. el modo autónomo está habilitado de forma explícita y la oferta cumple
   TODAS las reglas del usuario.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .jobs import sin_acentos
from .models import ESTADOS_POSTULADOS
from .storage import ahora_iso

COLECCION = 'authorizations'


def huella_documentos(docs: List[Dict[str, Any]]) -> str:
    base = [(d.get('id'), d.get('tipo'), json.dumps(d.get('contenido'), sort_keys=True, ensure_ascii=False))
            for d in sorted(docs, key=lambda d: d.get('tipo', ''))]
    return hashlib.sha256(json.dumps(base, ensure_ascii=False).encode()).hexdigest()[:32]


def autorizar_envio(store, owner_id: Any, job_id: str, docs: List[Dict[str, Any]],
                    por: str = 'usuario') -> Dict[str, Any]:
    reg = {'id': f'{job_id}', 'job_id': job_id, 'por': por, 'fecha': ahora_iso(),
           'huella_docs': huella_documentos(docs), 'usada': False}
    store.save(COLECCION, owner_id, reg)     # mismo id = reemplaza la autorización previa

    return reg


def autorizacion_vigente(store, owner_id: Any, job_id: str, docs: List[Dict[str, Any]]) -> Tuple[bool, str]:
    reg = store.get(COLECCION, owner_id, job_id)
    if not reg:
        return False, 'El usuario no ha autorizado el envío de esta oferta.'
    if reg.get('usada'):
        return False, 'La autorización ya se usó; autoriza de nuevo para reintentar.'
    if reg.get('huella_docs') != huella_documentos(docs):
        return False, 'Los documentos cambiaron después de autorizar; revisa y autoriza de nuevo.'
    return True, ''


def consumir_autorizacion(store, owner_id: Any, job_id: str) -> None:
    store.mutate(COLECCION, owner_id, job_id, lambda a: {**a, 'usada': True, 'usada_en': ahora_iso()})


def _en_ventana(config: Dict[str, Any], ahora: Optional[datetime]) -> Tuple[bool, str]:
    h = config.get('horario') or {}
    zona = ZoneInfo(h.get('zona') or 'America/Bogota')
    local = (ahora or datetime.now(zona)).astimezone(zona)
    if h.get('dias') and local.weekday() not in h['dias']:
        return False, 'Hoy está fuera de los días configurados.'
    try:
        desde = int(str(h.get('desde', '00:00')).split(':')[0])
        hasta = int(str(h.get('hasta', '23:59')).split(':')[0])
    except ValueError:
        return True, ''
    if not desde <= local.hour <= hasta:
        return False, f"Fuera del horario configurado ({h.get('desde')} - {h.get('hasta')})."
    return True, ''


def evaluar_autonomo(job: Dict[str, Any], profile: Dict[str, Any], *, docs_listos: bool,
                     adapter_envia: bool, postuladas_hoy: int, ya_postulado: bool = False,
                     ahora: Optional[datetime] = None) -> Tuple[bool, List[str]]:
    """(puede_enviar_solo, motivos_para_no_hacerlo). Cualquier duda → no enviar."""
    config = profile.get('config') or {}
    auto = config.get('autonomo') or {}
    motivos: List[str] = []

    if not auto.get('habilitado') or not auto.get('habilitado_en'):
        return False, ['El modo autónomo no está habilitado.']
    if ya_postulado or job.get('status') in ESTADOS_POSTULADOS:
        motivos.append('Ya existe una postulación a esta oferta.')
    if not adapter_envia:
        motivos.append('Este portal no tiene envío automatizado verificable.')
    if job.get('portal') not in (config.get('portales') or []):
        motivos.append('El portal no está entre las fuentes autorizadas.')
    match = job.get('matching') or {}
    if not match.get('apto'):
        motivos.append('La oferta tiene requisitos excluyentes sin cumplir.')
    if int(job.get('puntuacion') or 0) < int(config.get('puntuacion_minima') or 60):
        motivos.append(f"Compatibilidad {job.get('puntuacion')} por debajo del mínimo {config.get('puntuacion_minima')}.")
    if not docs_listos:
        motivos.append('Faltan los documentos de esta vacante.')
    if postuladas_hoy >= int(config.get('max_postulaciones_diarias') or 5):
        motivos.append('Se alcanzó el máximo de postulaciones de hoy.')

    empresa = sin_acentos(job.get('empresa'))
    for ex in config.get('empresas_excluidas') or []:
        if sin_acentos(ex) and sin_acentos(ex) in empresa:
            motivos.append(f'Empresa excluida: {ex}.')
    permitidas = [sin_acentos(e) for e in auto.get('empresas_permitidas') or [] if e]
    if permitidas and not any(p in empresa for p in permitidas):
        motivos.append('La empresa no está en tu lista de empresas permitidas.')

    vigente = job.get('vigente_hasta')
    if vigente:
        try:
            if date.fromisoformat(str(vigente)[:10]) < date.today():
                motivos.append('La oferta está vencida.')
        except ValueError:
            pass
    if auto.get('ventana_horaria', True):
        ok, motivo = _en_ventana(config, ahora)
        if not ok:
            motivos.append(motivo)
    return (not motivos), motivos
