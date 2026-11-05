#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ashby: API pública de tableros (api.ashbyhq.com/posting-api/job-board)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .ats_api import AtsApiAdapter, a_iso, a_mensual, modalidad_de


def _salario(comp: Dict[str, Any]):
    for c in (comp or {}).get('summaryComponents') or []:
        if c.get('compensationType') == 'Salary' and c.get('minValue') is not None:
            return (a_mensual(c.get('minValue'), c.get('interval', '')),
                    a_mensual(c.get('maxValue'), c.get('interval', '')), c.get('currencyCode') or '')
    return None, None, ''


class AshbyAdapter(AtsApiAdapter):
    nombre = 'Ashby'
    clave = 'ashby'
    config_clave = 'ashby_boards'

    def url_lista(self, slug: str) -> Tuple[str, Dict[str, Any]]:
        return f'https://api.ashbyhq.com/posting-api/job-board/{slug}', {'includeCompensation': 'true'}

    def a_ofertas(self, slug: str, datos: Any) -> List[Dict[str, Any]]:
        salida = []
        for j in (datos or {}).get('jobs', []):
            if j.get('isListed') is False:
                continue
            minimo, maximo, moneda = _salario(j.get('compensation'))
            direccion = ((j.get('address') or {}).get('postalAddress') or {})
            modalidad = modalidad_de(j.get('workplaceType')) or ('remota' if j.get('isRemote') else '')
            salida.append({
                'external_id': j.get('id'),
                'titulo': j.get('title'),
                'empresa': slug.replace('-', ' ').title(),
                'ubicacion': j.get('location') or '',
                'pais': direccion.get('addressCountry') or '',
                'modalidad': modalidad,
                'descripcion': j.get('descriptionPlain') or '',
                'salario_minimo': minimo, 'salario_maximo': maximo, 'moneda': moneda,
                'url': j.get('jobUrl'),
                'application_url': j.get('applyUrl') or j.get('jobUrl'),
                'fecha_publicacion': a_iso(j.get('publishedAt')),
            })
        return salida
