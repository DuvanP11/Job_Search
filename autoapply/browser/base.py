#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrato entre el orquestador y los aplicadores de navegador (uno por ATS)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Estados de resultado. Solo 'confirmado' prueba un envío real (señal positiva del portal).
CONFIRMADO = 'confirmado'                      # el portal mostró confirmación verificable
ENVIADO_SIN_CONFIRMACION = 'enviado_sin_confirmacion'   # se pulsó Enviar pero no hay señal clara
DRY_RUN = 'dry_run'                            # formulario completado y validado; NO se envió
REQUIERE_USUARIO = 'requiere_usuario'          # CAPTCHA, MFA, login, pregunta sensible, campo desconocido…
ERROR = 'error'


@dataclass
class ResultadoAplicacion:
    estado: str
    motivo: str = ''
    campos_pendientes: List[str] = field(default_factory=list)
    evidencia: Dict[str, Any] = field(default_factory=dict)   # capturas, url_final, señal
    reintentable: bool = False


@dataclass
class SolicitudAplicacion:
    job: Dict[str, Any]
    candidato: Dict[str, Any]
    archivos: Dict[str, str]                 # {'cv': ruta.pdf, 'carta': ruta.pdf}
    carta_texto: str = ''
    enviar_real: bool = False                # False = rellenar y verificar, sin enviar
    permitir_respuestas_ia: bool = False
    responder: Optional[Any] = None          # callable(pregunta) -> {'estado','respuesta'}
    carpeta_evidencia: str = ''


class Aplicador:
    clave = 'base'

    def soporta(self, job: Dict[str, Any]) -> bool:
        return False

    def aplicar(self, solicitud: SolicitudAplicacion) -> ResultadoAplicacion:
        raise NotImplementedError


_REGISTRO: Dict[str, Any] = {}


def registrar_aplicador(portal: str, fabrica) -> None:
    _REGISTRO[portal] = fabrica


def obtener_aplicador(portal: str) -> Optional[Aplicador]:
    fabrica = _REGISTRO.get((portal or '').lower())
    return fabrica() if fabrica else None


def portales_con_envio() -> List[str]:
    return sorted(_REGISTRO)
