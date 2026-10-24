#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Worker en segundo plano (ejecución fuera del request web)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

from .runner import AutoApplyRunner
from .storage import get_store

logger = logging.getLogger(__name__)


class AutoApplyWorker:
    def __init__(self):
        self.store = get_store()
        self.runner = AutoApplyRunner(self.store)

    def _cargar_perfil(self, user_id: Any) -> Dict[str, Any]:
        perfil = self.store.get('profiles', user_id, 'default')
        if perfil:
            return perfil
        perfil = self.store.list('profiles', user_id)
        return perfil[0] if perfil else {}

    def _cargar_candidato(self, user_id: Any):
        from .cv import obtener_perfil_profesional
        return obtener_perfil_profesional(user_id)

    def ejecutar_una_vez(self, user_id: Any, modo: str = 'simulacion',
                         confirmar_todo: bool = False) -> Dict[str, Any]:
        perfil = self._cargar_perfil(user_id)
        candidato = self._cargar_candidato(user_id)
        if not perfil:
            return {'ok': False, 'error': 'No hay perfil configurado'}
        return self.runner.ejecutar(user_id, perfil, candidato, modo=modo,
                                    confirmar_todo=confirmar_todo)

    def bucle(self, user_id: Any, modo: str = 'simulacion', intervalo_min: int = 60,
              max_iteraciones: int = None):
        iteracion = 0
        while True:
            try:
                resultado = self.ejecutar_una_vez(user_id, modo=modo)
                logger.info('AutoApply worker: %s', resultado)
            except Exception as exc:  # noqa: BLE001
                logger.error('Error en worker AutoApply: %s', exc)
            iteracion += 1
            if max_iteraciones and iteracion >= max_iteraciones:
                break
            time.sleep(max_iteraciones is None and intervalo_min * 60 or 5)


def main():
    logging.basicConfig(level=logging.INFO)
    user_id = os.getenv('AUTOAPPLY_USER_ID') or '1'
    modo = os.getenv('AUTOAPPLY_MODO') or 'simulacion'
    intervalo = int(os.getenv('AUTOAPPLY_INTERVALO_MIN') or 60)
    worker = AutoApplyWorker()
    worker.bucle(user_id, modo=modo, intervalo_min=intervalo)


if __name__ == '__main__':
    main()
