#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Greenhouse: API pública de tableros (boards-api.greenhouse.io)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .ats_api import AtsApiAdapter, a_iso, html_a_texto


class GreenhouseAdapter(AtsApiAdapter):
    nombre = 'Greenhouse'
    clave = 'greenhouse'
    config_clave = 'greenhouse_boards'

    def url_lista(self, slug: str) -> Tuple[str, Dict[str, Any]]:
        return f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs', {'content': 'true'}

    def a_ofertas(self, slug: str, datos: Any) -> List[Dict[str, Any]]:
        salida = []
        for j in (datos or {}).get('jobs', []):
            salida.append({
                'external_id': str(j.get('id') or ''),
                'titulo': j.get('title'),
                'empresa': j.get('company_name') or slug,
                'ubicacion': (j.get('location') or {}).get('name') or '',
                'pais': '',
                'moneda': '',
                'descripcion': html_a_texto(j.get('content')),
                'url': j.get('absolute_url'),
                'application_url': j.get('absolute_url'),
                'fecha_publicacion': a_iso(j.get('first_published') or j.get('updated_at')),
            })
        return salida
