#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detección de duplicados e historial."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage import huella_empresa_cargo, huella_job


def buscar_duplicado(job: Dict[str, Any], store, owner_id: Any,
                     collection: str = 'jobs') -> Optional[Dict[str, Any]]:
    huella = job.get('fingerprint') or huella_job(job)
    existente = store.find_by_fingerprint(collection, owner_id, huella)
    if existente:
        return existente

    huella_ec = job.get('fingerprint_empresa') or huella_empresa_cargo(job)
    if huella_ec:
        for registro in store.list(collection, owner_id):
            if registro.get('fingerprint_empresa') == huella_ec and registro.get('status') in (
                'enviada_sin_confirmacion', 'postulacion_confirmada', 'en_proceso'
            ):
                return registro
    return None


def ya_postulado(job: Dict[str, Any], store, owner_id: Any) -> bool:
    duplicado = buscar_duplicado(job, store, owner_id)
    if not duplicado:
        return False
    return duplicado.get('status') in ('enviada_sin_confirmacion', 'postulacion_confirmada')


def marcar_historial(job: Dict[str, Any], store, owner_id: Any,
                     status: str, origen: str = 'descubrimiento') -> Dict[str, Any]:
    registro = dict(job)
    registro['status'] = status
    registro['origen'] = origen
    guardado, creado = store.save('jobs', owner_id, registro, unique_fingerprint=True)
    return guardado
