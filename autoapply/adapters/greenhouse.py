#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptador para Greenhouse (tableros públicos)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import AdapterBase, ResultadoBusqueda, ResultadoPreparacion, ResultadoPostulacion
from ..jobs import normalizar_job, limpiar

logger = logging.getLogger(__name__)


class GreenhouseAdapter(AdapterBase):
    nombre = 'Greenhouse'
    clave = 'greenhouse'
    soporta_busqueda = True
    soporta_postulacion = False

    def _buscar_tablero(self, board: str, config_perfil: Dict[str, Any]) -> List[Dict[str, Any]]:
        ofertas = []
        try:
            url = f'https://boards.greenhouse.io/{board}'
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                return ofertas
            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.select('a[href*="/jobs/"]'):
                href = link.get('href') or ''
                titulo = limpiar(link.get_text())
                if not titulo or '/jobs/' not in href:
                    continue
                absolute = urljoin(url, href)
                crudo = {
                    'portal': 'greenhouse',
                    'titulo': titulo,
                    'empresa': board.replace('-', ' ').title(),
                    'url': absolute,
                    'application_url': absolute,
                    'fuente': 'greenhouse_api_publica',
                }
                ofertas.append(normalizar_job(crudo, 'greenhouse'))
        except Exception as exc:  # noqa: BLE001
            logger.error('Error buscando Greenhouse board %s: %s', board, exc)
        return ofertas

    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        resultado = ResultadoBusqueda()
        boards = config_perfil.get('greenhouse_boards') or []
        if not boards:
            resultado.advertencias.append(
                'Greenhouse habilitado pero no hay tableros configurados. '
                'Añade greenhouse_boards en el perfil.'
            )
            return resultado
        for board in boards:
            if not board:
                continue
            try:
                resultado.ofertas.extend(self._buscar_tablero(str(board).strip(), config_perfil))
            except Exception as exc:  # noqa: BLE001
                resultado.errores.append(str(exc))
        vistos = set()
        unicos = []
        for oferta in resultado.ofertas:
            huella = oferta.get('fingerprint')
            if huella in vistos:
                continue
            vistos.add(huella)
            unicos.append(oferta)
        resultado.ofertas = unicos
        return resultado

    def preparar(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None) -> ResultadoPreparacion:
        return ResultadoPreparacion(
            listo_para_postular=False,
            requiere_intervencion=True,
            acciones_humano=[
                'Abrir el formulario Greenhouse',
                'Completar campos obligatorios desde el perfil',
                'Adjuntar CV si se solicita',
                'Enviar manualmente',
            ],
            mensaje='Greenhouse usa formularios propios; se prepara la información pero la postulación es manual.',
        )

    def postular(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(
            enviado=False,
            confirmado=False,
            requiere_intervencion=True,
            mensaje='Postulación manual requerida en Greenhouse.',
        )
