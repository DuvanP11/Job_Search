#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adaptador para Computrabajo usando el scraper existente."""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import AdapterBase, ResultadoBusqueda, ResultadoPreparacion, ResultadoPostulacion
from ..jobs import normalizar_job

logger = logging.getLogger(__name__)


class ComputrabajoAdapter(AdapterBase):
    nombre = 'Computrabajo'
    clave = 'computrabajo'
    soporta_busqueda = True
    soporta_postulacion = False

    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        resultado = ResultadoBusqueda()
        try:
            from utils.scraper import buscar_empleos_computrabajo

            cargos = config_perfil.get('cargos') or []
            ciudad = config_perfil.get('ciudad') or ''
            resultados_por_cargo = int(config_perfil.get('resultados_por_cargo') or 20)

            for cargo in cargos:
                if not cargo:
                    continue
                try:
                    crudos = buscar_empleos_computrabajo(
                        cargo=cargo,
                        ciudad=ciudad,
                        cantidad=resultados_por_cargo,
                    )
                    for crudo in crudos:
                        if not isinstance(crudo, dict):
                            continue
                        crudo.setdefault('portal', 'computrabajo')
                        normalizado = normalizar_job(crudo, 'computrabajo')
                        resultado.ofertas.append(normalizado)
                except Exception as exc:  # noqa: BLE001
                    resultado.errores.append(f'Error en Computrabajo para "{cargo}": {exc}')

            # Eliminar duplicados dentro de la búsqueda
            vistos = set()
            unicos = []
            for oferta in resultado.ofertas:
                huella = oferta.get('fingerprint')
                if huella in vistos:
                    continue
                vistos.add(huella)
                unicos.append(oferta)
            resultado.ofertas = unicos
        except Exception as exc:  # noqa: BLE001
            resultado.errores.append(str(exc))
        return resultado

    def preparar(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None) -> ResultadoPreparacion:
        return ResultadoPreparacion(
            listo_para_postular=False,
            requiere_intervencion=True,
            acciones_humano=[
                'Abrir la oferta en Computrabajo',
                'Iniciar sesión en la cuenta del candidato',
                'Revisar la oferta con la información generada',
                'Postular manualmente desde el portal',
            ],
            mensaje='Computrabajo: se prepara la información, pero la postulación se realiza manualmente.',
        )

    def postular(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(
            enviado=False,
            confirmado=False,
            requiere_intervencion=True,
            mensaje='Postulación manual requerida en Computrabajo.',
        )
