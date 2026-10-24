#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptador para Lever (empresas públicas)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import AdapterBase, ResultadoBusqueda, ResultadoPreparacion, ResultadoPostulacion
from ..jobs import normalizar_job, limpiar

logger = logging.getLogger(__name__)


class LeverAdapter(AdapterBase):
    nombre = 'Lever'
    clave = 'lever'
    soporta_busqueda = True
    soporta_postulacion = False

    def _buscar_empresa(self, empresa: str, config_perfil: Dict[str, Any]) -> List[Dict[str, Any]]:
        ofertas = []
        try:
            url = f'https://jobs.lever.co/{empresa}'
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                return ofertas
            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.select('a[href*="/"]'):
                href = link.get('href') or ''
                if '/apply' in href or href.count('/') < 2:
                    continue
                titulo = limpiar(link.get_text())
                if not titulo or len(titulo) < 5:
                    continue
                if href.startswith('http'):
                    absolute = href
                else:
                    absolute = urljoin(url, href)
                if 'lever.co' not in absolute:
                    continue
                crudo = {
                    'portal': 'lever',
                    'titulo': titulo,
                    'empresa': empresa.replace('-', ' ').title(),
                    'url': absolute,
                    'application_url': absolute,
                    'fuente': 'lever_publica',
                }
                ofertas.append(normalizar_job(crudo, 'lever'))
        except Exception as exc:  # noqa: BLE001
            logger.error('Error buscando Lever %s: %s', empresa, exc)
        return ofertas

    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        resultado = ResultadoBusqueda()
        empresas = config_perfil.get('lever_companies') or []
        if not empresas:
            resultado.advertencias.append(
                'Lever habilitado pero no hay empresas configuradas. '
                'Añade lever_companies en el perfil.'
            )
            return resultado
        for empresa in empresas:
            if not empresa:
                continue
            try:
                resultado.ofertas.extend(self._buscar_empresa(str(empresa).strip(), config_perfil))
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
                'Abrir el formulario Lever',
                'Completar campos obligatorios desde el perfil',
                'Adjuntar CV si se solicita',
                'Enviar manualmente',
            ],
            mensaje='Lever usa formularios propios; se prepara la información pero la postulación es manual.',
        )

    def postular(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(
            enviado=False,
            confirmado=False,
            requiere_intervencion=True,
            mensaje='Postulación manual requerida en Lever.',
        )
