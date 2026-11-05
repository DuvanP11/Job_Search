#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capa de proveedores de IA intercambiables (Ollama primero, de pago opcional)."""

from .base import AIError, AIProvider, TAREAS
from .router import AIRouter, get_router, reset_router_for_tests

__all__ = ['AIError', 'AIProvider', 'TAREAS', 'AIRouter', 'get_router', 'reset_router_for_tests']
