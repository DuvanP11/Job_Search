#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validaciones de seguridad para el módulo de postulación."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Tuple


class AutoApplySecurityError(Exception):
    pass


DOMINIOS_BLOQUEADOS = (
    'linkedin.com', 'indeed.com', 'serviciodeempleo.gov.co',
)


def _host_interno(host: str) -> bool:
    """True si el host es local, privado o reservado (protección SSRF)."""
    host = host.strip('[]').lower().rstrip('.')
    if host in ('localhost',) or host.endswith(('.localhost', '.local', '.internal')):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # nombre de dominio normal
    return (ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def validar_url_aplicacion(url: str) -> Tuple[bool, str]:
    if not url or not str(url).strip():
        return False, 'La URL de postulación está vacía.'
    try:
        partes = urlparse(str(url).strip())
        host = (partes.hostname or '').lower()
    except ValueError:
        return False, 'La URL no es válida.'
    if partes.scheme not in ('http', 'https') or not host:
        return False, 'La URL debe empezar por http:// o https://.'
    if _host_interno(host):
        return False, 'No se permite postular a direcciones locales o internas.'
    for dom in DOMINIOS_BLOQUEADOS:
        if host == dom or host.endswith('.' + dom):
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


# Preguntas que NUNCA se responden automáticamente (ni con plantilla ni con IA):
# las contesta el usuario. Cubre antecedentes, salud, datos demográficos,
# autorización laboral/migratoria y declaraciones jurídicas.
_SENSIBLES = (
    r'antecedent', r'penal', r'judicial', r'delit', r'condena', r'arrest', r'criminal', r'convict',
    r'felony', r'background check',
    r'salud', r'medic', r'enfermedad', r'discapacidad', r'disabilit', r'embaraz', r'pregnan',
    r'g[eé]nero', r'gender', r'sexo\b', r'sexual', r'raza', r'\brace\b', r'etnia', r'ethnic',
    r'religi', r'estado civil', r'marital', r'veteran', r'nacionalidad', r'ciudadan[ií]a', r'citizenship',
    r'visa', r'sponsor', r'work authori', r'autorizaci[oó]n (laboral|de trabajo)', r'permiso de trabajo',
    r'right to work', r'legalmente', r'legally',
    r'declaro', r'bajo juramento', r'certifico que', r'i certify', r'under penalty',
    r'afiliaci[oó]n pol[ií]tica', r'sindical', r'fecha de nacimiento', r'date of birth', r'edad\b', r'\bage\b',
    r'dependientes', r'hijos', r'children',
    r'contrase[ñn]a', r'password', r'c[eé]dula', r'pasaporte', r'passport', r'social security', r'tax id',
)


def es_pregunta_sensible(texto: Any) -> bool:
    """True si la pregunta de un formulario debe contestarla el usuario."""
    t = str(texto or '').lower()
    return any(re.search(p, t) for p in _SENSIBLES)
