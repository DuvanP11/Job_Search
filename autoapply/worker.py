#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Worker en segundo plano (proceso aparte de la web).

    python -m autoapply.worker                # bucle continuo
    python -m autoapply.worker --una-vez      # una pasada y salir (cron)

Variables de entorno:
    AUTOAPPLY_ENABLE_SUBMIT=1   permite el ENVÍO REAL. Sin ella solo rellena y verifica (dry-run).
    AUTOAPPLY_INTERVALO_SEG     espera entre pasadas (por defecto 60)
    AUTOAPPLY_DATA_DIR / DATABASE_URL   almacén compartido con la web
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import time

from .pipeline import Orquestador, envio_real_habilitado

logger = logging.getLogger(__name__)


class AutoApplyWorker:
    def __init__(self, store=None, nombre: str = ''):
        self.nombre = nombre or f'{socket.gethostname()}:{os.getpid()}'
        self.orquestador = Orquestador(store)
        self._parar = False

    def parar(self, *_):
        logger.info('Señal de parada recibida; termino la tarea en curso.')
        self._parar = True

    def una_pasada(self) -> dict:
        return self.orquestador.tick(self.nombre)

    def bucle(self, intervalo: int = 60, max_iteraciones=None):
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.parar)
            except ValueError:      # no es el hilo principal
                pass
        logger.info('Worker %s iniciado. Envío real: %s', self.nombre,
                    'HABILITADO' if envio_real_habilitado() else 'deshabilitado (dry-run)')
        i = 0
        while not self._parar:
            try:
                r = self.una_pasada()
                if r['tareas'] or r['descubrimientos']:
                    logger.info('Pasada: %s', r)
            except Exception:  # noqa: BLE001 - el bucle nunca debe morir por una tarea
                logger.exception('Error en la pasada del worker')
            i += 1
            if max_iteraciones and i >= max_iteraciones:
                break
            for _ in range(intervalo):          # dormir en trozos para reaccionar a la señal de parada
                if self._parar:
                    break
                time.sleep(1)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Worker de AI Auto Apply')
    ap.add_argument('--una-vez', action='store_true')
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    w = AutoApplyWorker()
    if args.una_vez:
        print(w.una_pasada())
    else:
        w.bucle(int(os.getenv('AUTOAPPLY_INTERVALO_SEG') or 60))


if __name__ == '__main__':
    main()
