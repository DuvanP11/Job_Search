#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrutador: elige proveedor por tarea, con respaldo y modo sin IA."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from .base import AIError, AIProvider, TAREAS, extraer_json
from .providers import REGISTRO

logger = logging.getLogger(__name__)

# Gratuitos/locales primero; los de pago solo si el usuario puso su clave.
ORDEN_POR_DEFECTO = ['ollama', 'openrouter', 'openai', 'anthropic']


class AIRouter:
    """config: {tarea: [{'proveedor': 'ollama', 'modelo': 'qwen3:14b'}, ...]}"""

    def __init__(self, config: Optional[Dict[str, List[Dict[str, str]]]] = None,
                 proveedores: Optional[Dict[str, AIProvider]] = None):
        self.config = config or {}
        self._inyectados = proveedores or {}

    def _orden(self, tarea: str) -> List[AIProvider]:
        if tarea not in TAREAS:
            raise ValueError(f'Tarea desconocida: {tarea}')
        entradas = self.config.get(tarea)
        if not entradas:
            env = os.getenv('AI_PROVIDER_ORDER')
            claves = [c.strip() for c in env.split(',')] if env else ORDEN_POR_DEFECTO
            entradas = [{'proveedor': c} for c in claves]
        salida = []
        for e in entradas:
            clave = e.get('proveedor')
            if clave in self._inyectados:
                salida.append(self._inyectados[clave])
            elif clave in REGISTRO:
                salida.append(REGISTRO[clave](modelo=e.get('modelo') or None))
        return salida

    def estado(self) -> List[Dict[str, Any]]:
        """Para la pantalla de configuración: qué hay y qué responde."""
        filas = []
        for clave in ORDEN_POR_DEFECTO:
            p = self._inyectados.get(clave) or REGISTRO[clave]()
            fila = p.descripcion()
            fila['disponible'] = p.disponible() if p.configurado() else False
            filas.append(fila)
        return filas

    def hay_ia(self, tarea: str = 'matching') -> bool:
        return any(p.configurado() and p.disponible() for p in self._orden(tarea))

    def generar(self, tarea: str, prompt: str, sistema: str = '', json_mode: bool = False,
                **kw) -> Dict[str, Any]:
        """Prueba cada proveedor en orden. Devuelve {'texto', 'proveedor', 'modelo'}.

        Lanza AIError si ninguno responde: quien llama debe tener una vía
        determinística de respaldo (nunca se inventa una respuesta).
        """
        errores = []
        for p in self._orden(tarea):
            if not p.configurado():
                continue
            try:
                texto = p.generar(prompt, sistema=sistema, json_mode=json_mode, **kw)
                if texto and texto.strip():
                    return {'texto': texto, 'proveedor': p.clave, 'modelo': p.modelo}
                errores.append(f'{p.clave}: respuesta vacía')
            except AIError as exc:
                logger.warning('IA %s falló en %s: %s', p.clave, tarea, exc)
                errores.append(f'{p.clave}: {exc}')
        raise AIError('Ningún proveedor de IA respondió. ' + ' | '.join(errores)
                      if errores else 'No hay ningún proveedor de IA configurado.')

    def generar_json(self, tarea: str, prompt: str, sistema: str = '', **kw) -> Dict[str, Any]:
        r = self.generar(tarea, prompt, sistema=sistema, json_mode=True, **kw)
        r['datos'] = extraer_json(r['texto'])
        return r


_router: Optional[AIRouter] = None
_lock = threading.Lock()


def get_router() -> AIRouter:
    global _router
    with _lock:
        if _router is None:
            _router = AIRouter()
        return _router


def reset_router_for_tests(router: Optional[AIRouter] = None) -> None:
    global _router
    with _lock:
        _router = router


def router_para_usuario(store, owner_id) -> AIRouter:
    """Router con el proveedor/modelo que el usuario eligió por tarea (las claves siguen en el entorno)."""
    cfg = (store.get('settings', owner_id, 'ia') or {}).get('tareas') or {}
    limpio = {t: [{'proveedor': e['proveedor'], 'modelo': e.get('modelo', '')} for e in lista
                  if e.get('proveedor') in REGISTRO]
              for t, lista in cfg.items() if t in TAREAS and isinstance(lista, list)}
    return AIRouter(config={t: v for t, v in limpio.items() if v})
