#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validaciones de seguridad para el módulo de postulación."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


class AutoApplySecurityError(Exception):
    pass


DIRECCIONES_SOSPECHOSAS = (
    'localhost', '127.0.0.1', '0.0.0.0', '::1', '169.254', '10.', '192.168.',
)
DOMINIOS_BLOQUEADOS = (
    'linkedin.com', 'indeed.com', 'serviciodeempleo.gov.co',
)


def validar_url_aplicacion(url: str) -> Tuple[bool, str]:
    if not url:
        return False, 'La URL de postulación está vacía.'
    url_limpia = url.strip()
    if not url_limpia.startswith(('http://', 'https://')):
        return False, 'La URL debe empezar por http:// o https://.'
    url_baja = url_limpia.lower()
    if any(d in url_baja for d in DIRECCIONES_SOSPECHOSAS):
        return False, 'No se permite postular a direcciones locales o internas.'
    for dom in DOMINIOS_BLOQUEADOS:
        if dom in url_baja:
            return False, f'La automatización está bloqueada para {dom} por restricciones de seguridad.'
    return True, ''


def validar_config_perfil(config: Dict[str, Any]) -> List[str]:
    errores: List[str] = []
    max_diario = int(config.get('max_postulaciones_diarias') or 0)
    if max_diario <= 0 or max_diario > 50:
        errores.append('max_postulaciones_diarias debe estar entre 1 y 50.')
    puntuacion = int(config.get('puntuacion_minima') or 0)
    if puntuacion < 0 or puntuacion > 100:
        errores.append('puntuacion_minima debe estar entre 0 y 100.')
    cargos = config.get('cargos') or []
    if not isinstance(cargos, list) or not any(str(c).strip() for c in cargos):
        errores.append('Debes configurar al menos un cargo objetivo.')
    portales = config.get('portales') or []
    if not isinstance(portales, list) or not portales:
        errores.append('Debes seleccionar al menos un portal habilitado.')
    return errores


def requiere_confirmacion_humana(job: Dict[str, Any], modo: str) -> bool:
    if modo == 'simulacion':
        return True
    if modo == 'revision':
        return True
    if modo == 'automatico':
        return False
    return True


def sanitizar_texto(texto: Any) -> str:
    if not texto:
        return ''
    texto = str(texto)
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.IGNORECASE | re.DOTALL)
    texto = re.sub(r'javascript:', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'on\w+\s*=', '', texto, flags=re.IGNORECASE)
    return texto[:5000]
