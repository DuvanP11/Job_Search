#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base para adaptadores de portales."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ResultadoBusqueda:
    ofertas: List[Dict[str, Any]] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    paginas: int = 0


@dataclass
class ResultadoPreparacion:
    listo_para_postular: bool = False
    requiere_captcha: bool = False
    requiere_mfa: bool = False
    requiere_login: bool = False
    requiere_intervencion: bool = False
    campos_faltantes: List[str] = field(default_factory=list)
    acciones_humano: List[str] = field(default_factory=list)
    datos_rellenables: Dict[str, Any] = field(default_factory=dict)
    mensaje: str = ''


@dataclass
class ResultadoPostulacion:
    enviado: bool = False
    confirmado: bool = False
    mensaje: str = ''
    captura_evidencia: str = ''
    url_resultado: str = ''
    requiere_intervencion: bool = False


class AdapterBase:
    nombre = 'base'
    clave = 'base'
    soporta_busqueda = True
    soporta_postulacion = False
    usa_selenium = False

    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        return ResultadoBusqueda(errores=['Adaptador base sin implementar'])

    def preparar(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None) -> ResultadoPreparacion:
        return ResultadoPreparacion(
            requiere_intervencion=True,
            mensaje='Este portal requiere intervención humana para postularse.',
        )

    def postular(self, job: Dict[str, Any], candidato: Dict[str, Any],
                 credenciales: Dict[str, Any] = None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(
            enviado=False,
            confirmado=False,
            requiere_intervencion=True,
            mensaje='La postulación automática no está habilitada para este portal.',
        )

    def validar(self) -> List[str]:
        return []
