#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SmartRecruiters: API pública de ofertas (api.smartrecruiters.com/v1)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from .ats_api import AtsApiAdapter, FuenteError, a_iso, html_a_texto

logger = logging.getLogger(__name__)

PAGINA = 100
MAX_PAGINAS = 3          # hasta 300 ofertas por empresa
MAX_DETALLES = 25        # el listado no trae descripción: se consulta solo las que coinciden con el cargo


class SmartRecruitersAdapter(AtsApiAdapter):
    nombre = 'SmartRecruiters'
    clave = 'smartrecruiters'
    config_clave = 'smartrecruiters_companies'

    def url_lista(self, slug: str) -> Tuple[str, Dict[str, Any]]:
        return f'https://api.smartrecruiters.com/v1/companies/{slug}/postings', {'limit': PAGINA}

    def buscar(self, config_perfil, **kwargs):
        self._cargos = [c.lower() for c in (config_perfil.get('cargos') or []) + (config_perfil.get('sinonimos') or [])]
        return super().buscar(config_perfil, **kwargs)

    def get_json(self, url, params=None, reintentos=2):
        datos = super().get_json(url, params, reintentos)
        # Paginación del listado
        if isinstance(datos, dict) and 'content' in datos and url.endswith('/postings'):
            total = int(datos.get('totalFound') or 0)
            for pagina in range(1, MAX_PAGINAS):
                if len(datos['content']) >= total:
                    break
                extra = super().get_json(url, {**(params or {}), 'offset': pagina * PAGINA}, reintentos)
                if not extra.get('content'):
                    break
                datos['content'].extend(extra['content'])
        return datos

    def _coincide(self, titulo: str) -> bool:
        cargos = getattr(self, '_cargos', [])
        if not cargos:
            return True
        t = (titulo or '').lower()
        return any(all(p in t for p in c.split() if len(p) > 2) for c in cargos if c.strip())

    def a_ofertas(self, slug: str, datos: Any) -> List[Dict[str, Any]]:
        salida, detalles = [], 0
        for j in (datos or {}).get('content', []):
            loc = j.get('location') or {}
            ubicacion = loc.get('fullLocation') or ', '.join(filter(None, [loc.get('city'), loc.get('country')]))
            modalidad = 'remota' if loc.get('remote') else 'hibrida' if loc.get('hybrid') else ''
            url = f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}"
            descripcion, apply_url = '', url
            if detalles < MAX_DETALLES and self._coincide(j.get('name')):
                try:
                    d = self.get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j['id']}")
                    secciones = (d.get('jobAd') or {}).get('sections') or {}
                    descripcion = ' '.join(html_a_texto((secciones.get(k) or {}).get('text'))
                                           for k in ('jobDescription', 'qualifications', 'additionalInformation'))
                    url = d.get('postingUrl') or url
                    apply_url = d.get('applyUrl') or url
                    detalles += 1
                except FuenteError as exc:
                    logger.warning('SmartRecruiters %s/%s sin detalle: %s', slug, j.get('id'), exc)
            salida.append({
                'external_id': j.get('id'),
                'titulo': j.get('name'),
                'empresa': (j.get('company') or {}).get('name') or slug,
                'ubicacion': ubicacion, 'pais': (loc.get('country') or '').upper(),
                'modalidad': modalidad, 'moneda': '',
                'descripcion': descripcion,
                'url': url, 'application_url': apply_url,
                'fecha_publicacion': a_iso(j.get('releasedDate')),
            })
        return salida
