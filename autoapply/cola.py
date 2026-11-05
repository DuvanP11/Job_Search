#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cola de trabajo persistente: reintentos con espera, arrendamiento y recuperación.

- Sin duplicados: no hay dos tareas activas para la misma oferta y acción.
- Una tarea reclamada tiene un "arrendamiento"; si el worker muere, vence y la
  tarea vuelve a estar disponible (recuperación tras interrupciones).
- Los fallos reintentables se reintentan con espera exponencial hasta un máximo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

COLECCION = 'queue'
ACCIONES = ('preparar', 'enviar')
ACTIVOS = ('pendiente', 'en_curso')
LEASE_SEGUNDOS = 900
ESPERA_BASE = 60


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _a_dt(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace('Z', '+00:00'))


class ColaTrabajo:
    def __init__(self, store, max_intentos: int = 3):
        self.store = store
        self.max_intentos = max_intentos

    def encolar(self, owner_id: Any, job_id: str, accion: str, **datos) -> Tuple[Dict[str, Any], bool]:
        if accion not in ACCIONES:
            raise ValueError(f'Acción desconocida: {accion}')
        for t in self.store.list(COLECCION, owner_id, where=lambda r: r['job_id'] == job_id and r['accion'] == accion):
            if t['estado'] in ACTIVOS:
                return t, False
        tarea = {'id': uuid.uuid4().hex[:16], 'job_id': job_id, 'accion': accion, 'estado': 'pendiente',
                 'intentos': 0, 'max_intentos': self.max_intentos, 'no_antes_de': _iso(_ahora()),
                 'lease_hasta': '', 'worker': '', 'ultimo_error': '', 'resultado': {}, 'datos': datos}
        guardada, _ = self.store.save(COLECCION, owner_id, tarea)
        return guardada, True

    def _candidata(self, t: Dict[str, Any], ahora: datetime) -> bool:
        if t['estado'] == 'pendiente':
            return _a_dt(t['no_antes_de']) <= ahora
        if t['estado'] == 'en_curso':               # worker caído: el arrendamiento venció
            return bool(t['lease_hasta']) and _a_dt(t['lease_hasta']) <= ahora
        return False

    def reclamar(self, worker: str, ahora: Optional[datetime] = None,
                 lease_seg: int = LEASE_SEGUNDOS) -> Optional[Tuple[Any, Dict[str, Any]]]:
        ahora = ahora or _ahora()
        for owner in self.store.owners(COLECCION):
            for t in sorted(self.store.list(COLECCION, owner, where=lambda r: r['estado'] in ACTIVOS),
                            key=lambda r: r['no_antes_de']):
                if not self._candidata(t, ahora):
                    continue
                reclamo = {}

                def fn(actual, reclamo=reclamo):
                    if not self._candidata(actual, ahora):      # otro worker se adelantó
                        return actual
                    recuperada = actual['estado'] == 'en_curso'
                    actual.update(estado='en_curso', worker=worker, intentos=actual['intentos'] + 1,
                                  lease_hasta=_iso(ahora + timedelta(seconds=lease_seg)))
                    if recuperada:
                        actual['ultimo_error'] = 'Recuperada tras una interrupción del worker.'
                    reclamo['ok'] = True
                    return actual
                nueva = self.store.mutate(COLECCION, owner, t['id'], fn)
                if nueva and reclamo.get('ok') and nueva['worker'] == worker:
                    if nueva['intentos'] > nueva['max_intentos']:       # agotó intentos por caídas repetidas
                        self.fallar(owner, nueva['id'], 'Se agotaron los intentos (interrupciones repetidas).',
                                    reintentable=False)
                        continue
                    return owner, nueva
        return None

    def renovar(self, owner_id: Any, tarea_id: str, lease_seg: int = LEASE_SEGUNDOS) -> None:
        self.store.mutate(COLECCION, owner_id, tarea_id,
                          lambda a: {**a, 'lease_hasta': _iso(_ahora() + timedelta(seconds=lease_seg))})

    def completar(self, owner_id: Any, tarea_id: str, resultado: Optional[Dict[str, Any]] = None,
                  estado: str = 'completada') -> Optional[Dict[str, Any]]:
        return self.store.mutate(COLECCION, owner_id, tarea_id,
                                 lambda a: {**a, 'estado': estado, 'resultado': resultado or {}, 'lease_hasta': ''})

    def requiere_usuario(self, owner_id: Any, tarea_id: str, motivo: str, resultado=None):
        return self.completar(owner_id, tarea_id, {**(resultado or {}), 'motivo': motivo}, estado='requiere_usuario')

    def fallar(self, owner_id: Any, tarea_id: str, error: str, reintentable: bool = True,
               ahora: Optional[datetime] = None):
        ahora = ahora or _ahora()

        def fn(a):
            a['ultimo_error'] = str(error)[:500]
            a['lease_hasta'] = ''
            if reintentable and a['intentos'] < a['max_intentos']:
                a['estado'] = 'pendiente'
                a['no_antes_de'] = _iso(ahora + timedelta(seconds=ESPERA_BASE * 2 ** (a['intentos'] - 1)))
            else:
                a['estado'] = 'fallida'
            return a
        return self.store.mutate(COLECCION, owner_id, tarea_id, fn)

    def cancelar(self, owner_id: Any, tarea_id: str):
        return self.store.mutate(COLECCION, owner_id, tarea_id,
                                 lambda a: {**a, 'estado': 'cancelada', 'lease_hasta': ''}
                                 if a['estado'] in ACTIVOS else a)

    def listar(self, owner_id: Any, estado: str = ''):
        return self.store.list(COLECCION, owner_id, where=lambda r: not estado or r['estado'] == estado)
