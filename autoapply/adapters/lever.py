#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lever: API pública de ofertas (api.lever.co/v0/postings)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .ats_api import AtsApiAdapter, a_iso, a_mensual, modalidad_de


class LeverAdapter(AtsApiAdapter):
    nombre = 'Lever'
    clave = 'lever'
    config_clave = 'lever_companies'

    def url_lista(self, slug: str) -> Tuple[str, Dict[str, Any]]:
        return f'https://api.lever.co/v0/postings/{slug}', {'mode': 'json'}

    def a_ofertas(self, slug: str, datos: Any) -> List[Dict[str, Any]]:
        if not isinstance(datos, list):
            return []
        salida = []
        for j in datos:
            cat = j.get('categories') or {}
            listas = ' '.join(f"{x.get('text', '')} {x.get('content', '')}" for x in j.get('lists') or [])
            rango = j.get('salaryRange') or {}
            minimo = a_mensual(rango.get('min'), rango.get('interval', ''))
            maximo = a_mensual(rango.get('max'), rango.get('interval', ''))
            salida.append({
                'external_id': j.get('id'),
                'titulo': j.get('text'),
                'empresa': slug.replace('-', ' ').title(),
                'ubicacion': cat.get('location') or ', '.join(cat.get('allLocations') or []),
                'pais': j.get('country') or '',
                'modalidad': modalidad_de(j.get('workplaceType')),
                'tipo_contrato': '',
                'descripcion': ' '.join(filter(None, [j.get('descriptionPlain'), listas, j.get('additionalPlain')])),
                'salario_minimo': minimo, 'salario_maximo': maximo,
                'moneda': (rango.get('currency') or '') if minimo or maximo else '',
                'url': j.get('hostedUrl'),
                'application_url': j.get('applyUrl') or j.get('hostedUrl'),
                'fecha_publicacion': a_iso(j.get('createdAt')),
            })
        return salida
