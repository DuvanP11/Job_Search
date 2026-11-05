#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrato común de los proveedores de IA."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

# Tareas que pueden usar un proveedor/modelo distinto.
TAREAS = (
    'extraccion_cv',
    'clasificacion',
    'matching',
    'documentos',
    'formularios',
    'navegacion',
)


class AIError(Exception):
    """Fallo de un proveedor (red, cuota, respuesta inválida)."""


class AIProvider:
    clave = 'base'
    nombre = 'Base'
    gratuito = False

    def __init__(self, modelo: Optional[str] = None):
        self.modelo = modelo or self.modelo_por_defecto()

    def modelo_por_defecto(self) -> str:
        return ''

    def configurado(self) -> bool:
        """True si hay lo mínimo (URL/clave) para intentar usarlo."""
        return False

    def disponible(self) -> bool:
        """True si responde ahora mismo. No debe lanzar excepciones."""
        return self.configurado()

    def generar(self, prompt: str, sistema: str = '', json_mode: bool = False,
                max_tokens: int = 1500, temperatura: float = 0.2) -> str:
        raise NotImplementedError

    def descripcion(self) -> Dict[str, Any]:
        return {'clave': self.clave, 'nombre': self.nombre, 'modelo': self.modelo,
                'gratuito': self.gratuito, 'configurado': self.configurado()}


def extraer_json(texto: str) -> Any:
    """Extrae el primer objeto/arreglo JSON de la respuesta de un modelo.

    Tolera bloques ```json y texto antes o después. Lanza AIError si no hay JSON.
    """
    if not texto:
        raise AIError('Respuesta vacía del modelo')
    limpio = re.sub(r'^```(?:json)?\s*|\s*```$', '', texto.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(limpio)
    except ValueError:
        pass
    for abre, cierra in (('{', '}'), ('[', ']')):
        i, j = limpio.find(abre), limpio.rfind(cierra)
        if i != -1 and j > i:
            try:
                return json.loads(limpio[i:j + 1])
            except ValueError:
                continue
    raise AIError('La respuesta del modelo no contiene JSON válido')
