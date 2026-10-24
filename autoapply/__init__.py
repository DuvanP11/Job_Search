#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Módulo de búsqueda y postulación laboral asistida.

Se registra como blueprint en app.py. La lógica de negocio vive en este
paquete para no seguir engordando el archivo principal de Flask.
"""

from .routes import autoapply_bp

__all__ = ['autoapply_bp']
