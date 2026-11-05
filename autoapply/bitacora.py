#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitácora de actividad del agente (auditoría). Nunca guarda secretos ni datos de formularios."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage import ahora_iso

COLECCION = 'agent_log'
MAX_REGISTROS = 1500          # por usuario; se poda lo más antiguo


def registrar(store, owner_id: Any, evento: str, detalle: str = '', nivel: str = 'info',
              job_id: str = '', tarea_id: str = '', extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    reg = {'id': f"{ahora_iso()}-{evento}-{job_id or tarea_id or 'x'}"[:64] + _sufijo(),
           'ts': ahora_iso(), 'evento': evento, 'nivel': nivel, 'detalle': str(detalle)[:600],
           'job_id': job_id, 'tarea_id': tarea_id, 'extra': extra or {}}
    store.save(COLECCION, owner_id, reg)
    _podar(store, owner_id)
    return reg


def _sufijo() -> str:
    import uuid
    return '-' + uuid.uuid4().hex[:6]


def _podar(store, owner_id: Any) -> None:
    registros = store.list(COLECCION, owner_id)
    if len(registros) > MAX_REGISTROS:
        for viejo in sorted(registros, key=lambda r: r.get('ts', ''))[:len(registros) - MAX_REGISTROS]:
            store.delete(COLECCION, owner_id, viejo['id'])


def listar(store, owner_id: Any, limite: int = 100, job_id: str = '', nivel: str = '') -> List[Dict[str, Any]]:
    def ok(r):
        return (not job_id or r.get('job_id') == job_id) and (not nivel or r.get('nivel') == nivel)
    return sorted(store.list(COLECCION, owner_id, where=ok), key=lambda r: r.get('ts', ''), reverse=True)[:limite]
