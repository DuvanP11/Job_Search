#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ElEmpleo (Colombia): lectura de la página pública de resultados.

Cada tarjeta trae un JSON estructurado (`data-ga4-offerdata`) con id, título,
empresa, ciudad y salario, más chips con contrato y modalidad. Se respeta
robots.txt (solo bloquea directorios administrativos) y un ritmo bajo.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import AdapterBase, ResultadoBusqueda, ResultadoPostulacion, ResultadoPreparacion
from ..jobs import normalizar_job

logger = logging.getLogger(__name__)

BASE = 'https://www.elempleo.com'
POR_PAGINA = 20
MAX_PAGINAS = 5
MAX_DETALLES = 25       # el listado no trae descripción: solo se consulta la de ofertas que coinciden con el cargo
PAUSA = 1.0
CABECERAS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'),
    'Accept-Language': 'es-CO,es;q=0.9',
}
_CONTRATOS = (('indefinido', 'indefinido'), ('obra', 'obra_labor'), ('labor', 'obra_labor'),
              ('fijo', 'temporal'), ('temporal', 'temporal'), ('prestacion', 'prestacion_servicios'),
              ('aprendiz', 'aprendizaje'), ('practica', 'practicas'))
_MODALIDADES = (('remot', 'remota'), ('hibrid', 'hibrida'), ('presencial', 'presencial'))


def _slug(texto: str) -> str:
    t = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')


def _sin_acentos(t: str) -> str:
    return unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode().lower()


def _num(txt: str) -> Optional[float]:
    """'3,5' → 3.5 ; '1.500.000' → 1500000."""
    txt = txt.strip()
    if re.fullmatch(r'\d{1,3}(\.\d{3})+', txt):
        return float(txt.replace('.', ''))
    try:
        return float(txt.replace(',', '.'))
    except ValueError:
        return None


def parsear_salario(texto: str) -> Tuple[Optional[float], Optional[float]]:
    """'$3 a $3,5 millones' → (3_000_000, 3_500_000). 'A convenir' → (None, None)."""
    t = _sin_acentos(texto)
    nums = re.findall(r'\d[\d.,]*', t)
    if not nums:
        return None, None
    mult = 1_000_000 if 'millon' in t else 1
    vals = [_num(n) for n in nums[:2]]
    vals = [v * mult for v in vals if v is not None]
    if not vals:
        return None, None
    if mult == 1 and max(vals) < 100_000:   # cifra suelta que no es un salario mensual
        return None, None
    return vals[0], vals[-1]


def _chips(tarjeta) -> Dict[str, str]:
    """Pares etiqueta → valor de los bloques '<div>valor</div><div class=small-text>Etiqueta</div>'."""
    salida = {}
    for etiqueta in tarjeta.select('div.small-text'):
        valor = etiqueta.find_previous_sibling('div')
        if valor:
            salida[_sin_acentos(etiqueta.get_text(' ', strip=True))] = valor.get_text(' ', strip=True)
    return salida


def parsear_pagina(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    ofertas = []
    for tarjeta in soup.select('div.result-item'):
        marca = tarjeta.select_one('[data-ga4-offerdata]')
        if not marca:
            continue
        try:
            d = json.loads(marca['data-ga4-offerdata'])
        except (ValueError, KeyError):
            continue
        ruta = marca.get('data-url') or ''
        if not ruta or not d.get('title'):
            continue
        chips = _chips(tarjeta)
        salario_txt = chips.get('salario') or d.get('salary') or ''
        minimo, maximo = parsear_salario(salario_txt)
        contrato = next((v for k, v in _CONTRATOS if k in _sin_acentos(chips.get('tipo de contrato', ''))), '')
        modalidad = next((v for k, v in _MODALIDADES
                          if k in _sin_acentos(chips.get('modalidad laboral', ''))), '')
        fecha = tarjeta.select_one('.js-offer-date')
        # El texto más largo de la tarjeta (fuera de los chips) es el extracto de la descripción.
        bloques = [t.get_text(' ', strip=True) for t in tarjeta.find_all(['p', 'div', 'span'])
                   if not t.find(['p', 'div']) and 'small' not in (t.get('class') or [])]
        descripcion = max((b for b in bloques if len(b) > 80), key=len, default='')
        ofertas.append({
            'external_id': str(d.get('id') or ''),
            'titulo': d['title'].strip(),
            'empresa': (d.get('company') or '').strip() or 'Empresa confidencial',
            'ubicacion': (d.get('location') or '').strip(),
            'ciudad': (d.get('location') or '').strip(),
            'pais': 'Colombia', 'moneda': 'COP',
            'modalidad': modalidad, 'tipo_contrato': contrato,
            'salario_minimo': minimo, 'salario_maximo': maximo,
            'descripcion': descripcion,
            'url': urljoin(BASE, ruta), 'application_url': urljoin(BASE, ruta),
            'fecha_publicacion': fecha.get_text(' ', strip=True) if fecha else None,
            'fuente': 'elempleo_resultados_publicos',
        })
    return ofertas


def parsear_detalle(html: str) -> Dict[str, Any]:
    """Descripción, fechas y vigencia desde el JSON-LD `JobPosting` de la oferta."""
    soup = BeautifulSoup(html, 'html.parser')
    for sc in soup.find_all('script', type='application/ld+json'):
        try:
            datos = json.loads(sc.string or '')
        except ValueError:
            continue
        for it in (datos if isinstance(datos, list) else [datos]):
            if isinstance(it, dict) and it.get('@type') == 'JobPosting':
                desc = it.get('description') or ''
                if '<' in desc:
                    desc = BeautifulSoup(desc, 'html.parser').get_text(' ')
                salida = {'descripcion': re.sub(r'\s+', ' ', desc).strip(),
                          'vigente_hasta': _fecha_iso(it.get('validThrough'))}
                if it.get('datePosted'):
                    salida['fecha_publicacion'] = _fecha_iso(it['datePosted'])
                if it.get('jobLocationType') == 'TELECOMMUTE':
                    salida['modalidad'] = 'remota'
                return salida
    return {}


def _fecha_iso(valor: Any) -> Optional[str]:
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(valor or ''))
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else None


def _titulo_coincide(titulo: str, cargos: List[str]) -> bool:
    t = _sin_acentos(titulo)
    return any(all(p in t for p in _sin_acentos(c).split() if len(p) > 2) for c in cargos if c.strip())


class ElEmpleoAdapter(AdapterBase):
    nombre = 'ElEmpleo'
    clave = 'elempleo'
    soporta_busqueda = True
    soporta_postulacion = False

    def _url(self, cargo: str, ciudad: str, pagina: int) -> str:
        # Verificado en vivo: '/<ciudad>/trabajo-<cargo>' filtra por ambos; '/<ciudad>/<cargo>' ignora el cargo.
        ruta = (f'/co/ofertas-empleo/{_slug(ciudad)}/trabajo-{_slug(cargo)}' if ciudad
                else f'/co/ofertas-empleo/trabajo-{_slug(cargo)}')
        return f'{BASE}{ruta}' + (f'?page={pagina}' if pagina > 1 else '')

    def _descargar(self, url: str) -> str:
        r = requests.get(url, headers=CABECERAS, timeout=20)
        if r.status_code in (403, 429):
            raise RuntimeError(f'el portal bloqueó la consulta ({r.status_code}); no se reintenta')
        if r.status_code >= 400:
            raise RuntimeError(f'respuesta {r.status_code}')
        return r.text

    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        res = ResultadoBusqueda()
        cargos = [c for c in (config_perfil.get('cargos') or []) if str(c).strip()]
        if not cargos:
            res.advertencias.append('ElEmpleo: no hay cargos configurados.')
            return res
        ciudad = str(config_perfil.get('ciudad') or '').strip()
        meta = int(config_perfil.get('resultados_por_cargo') or POR_PAGINA)
        vistos = set()
        detalles = 0
        for cargo in cargos:
            obtenidas = 0
            for pagina in range(1, MAX_PAGINAS + 1):
                if obtenidas >= meta:
                    break
                try:
                    html = self._descargar(self._url(cargo, ciudad, pagina))
                    res.paginas += 1
                except (requests.exceptions.RequestException, RuntimeError) as exc:
                    res.errores.append(f'ElEmpleo "{cargo}": {exc}.')
                    break
                crudas = parsear_pagina(html)
                if not crudas:
                    if pagina == 1:
                        res.advertencias.append(
                            f'ElEmpleo "{cargo}"{" en " + ciudad if ciudad else ""}: 0 resultados '
                            '(sin ofertas, o el portal cambió su formato).')
                    break
                for cruda in crudas:
                    if (detalles < MAX_DETALLES and _titulo_coincide(cruda['titulo'], cargos)):
                        try:
                            extra = parsear_detalle(self._descargar(cruda['url']))
                            cruda.update({k: v for k, v in extra.items() if v})
                            detalles += 1
                            time.sleep(PAUSA)
                        except (requests.exceptions.RequestException, RuntimeError) as exc:
                            res.advertencias.append(f'ElEmpleo: sin detalle de "{cruda["titulo"][:40]}" ({exc}).')
                    oferta = normalizar_job(cruda, 'elempleo')
                    oferta['vigente_hasta'] = cruda.get('vigente_hasta')
                    if oferta['fingerprint'] in vistos:
                        continue
                    vistos.add(oferta['fingerprint'])
                    res.ofertas.append(oferta)
                    obtenidas += 1
                time.sleep(PAUSA)
        return res

    def preparar(self, job, candidato, credenciales=None) -> ResultadoPreparacion:
        return ResultadoPreparacion(
            listo_para_postular=False, requiere_intervencion=True,
            acciones_humano=['Abrir la oferta en ElEmpleo', 'Iniciar sesión con tu cuenta',
                             'Revisar y postular desde el portal'],
            mensaje='ElEmpleo: la postulación se hace manualmente desde el portal.')

    def postular(self, job, candidato, credenciales=None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(enviado=False, confirmado=False, requiere_intervencion=True,
                                    mensaje='Postulación manual requerida en ElEmpleo.')
