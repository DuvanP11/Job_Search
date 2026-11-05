#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base para conectores de ATS que ofrecen API pública de ofertas (JSON).

Solo se usan los endpoints públicos documentados por cada ATS; no se raspa HTML
ni se evade ningún control. Cada conector reporta errores y advertencias
explícitos para la pantalla de estado de fuentes.
"""

from __future__ import annotations

import html
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .base import AdapterBase, ResultadoBusqueda, ResultadoPostulacion, ResultadoPreparacion
from ..jobs import normalizar_job

logger = logging.getLogger(__name__)

SLUG_VALIDO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,60}$')
USER_AGENT = 'JobSearchAutoApply/1.0 (cliente personal; consulta de ofertas publicas)'
MAX_OFERTAS_POR_FUENTE = 500


class FuenteError(Exception):
    """Fallo esperable de una fuente (no existe, límite, caída). Mensaje apto para el usuario."""


def html_a_texto(valor: Any) -> str:
    """HTML (a veces escapado dos veces, como en Greenhouse) → texto plano."""
    if not valor:
        return ''
    texto = html.unescape(str(valor))
    if '<' in texto:
        texto = BeautifulSoup(texto, 'html.parser').get_text(' ')
    return re.sub(r'\s+', ' ', texto).strip()


def a_iso(valor: Any) -> Optional[str]:
    """Fecha ISO-8601 o epoch (s/ms) → 'YYYY-MM-DD'. None si no se entiende."""
    if valor in (None, ''):
        return None
    try:
        if isinstance(valor, (int, float)):
            seg = valor / 1000 if valor > 1e11 else valor
            return datetime.fromtimestamp(seg, tz=timezone.utc).date().isoformat()
        return datetime.fromisoformat(str(valor).replace('Z', '+00:00')).date().isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def a_mensual(valor: Any, intervalo: str) -> Optional[float]:
    """Normaliza un monto a mensual. Por hora/desconocido no se convierte (None)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    i = (intervalo or '').lower()
    if 'year' in i or 'annual' in i or 'per-year' in i or i in ('yearly', 'anual'):
        return round(v / 12, 2)
    if 'month' in i or i == 'mensual':
        return v
    return None


class AtsApiAdapter(AdapterBase):
    """Subclases definen `url_lista(slug)` y `a_ofertas(slug, datos)`."""

    config_clave = ''           # clave de la lista de identificadores en la configuración
    intervalo_min = 0.3         # segundos entre peticiones a la misma fuente
    _ultimo = 0.0
    _lock = threading.Lock()
    soporta_busqueda = True
    soporta_postulacion = False

    # ---- a implementar -------------------------------------------------
    def url_lista(self, slug: str) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError

    def a_ofertas(self, slug: str, datos: Any) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # ---- red -----------------------------------------------------------
    def _esperar(self):
        with self._lock:
            falta = self.intervalo_min - (time.monotonic() - AtsApiAdapter._ultimo)
            if falta > 0:
                time.sleep(falta)
            AtsApiAdapter._ultimo = time.monotonic()

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, reintentos: int = 2) -> Any:
        ultimo_error = ''
        for intento in range(reintentos + 1):
            self._esperar()
            try:
                r = requests.get(url, params=params, timeout=20,
                                 headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
            except requests.exceptions.RequestException as exc:
                ultimo_error = f'sin conexión ({type(exc).__name__})'
            else:
                if r.status_code == 404:
                    raise FuenteError('no existe o no tiene ofertas públicas (404)')
                if r.status_code in (401, 403):
                    raise FuenteError(f'acceso no permitido ({r.status_code})')
                if r.status_code == 429 or r.status_code >= 500:
                    ultimo_error = f'el servicio respondió {r.status_code}'
                    espera = r.headers.get('Retry-After', '')
                    if espera.isdigit() and intento < reintentos:
                        time.sleep(min(int(espera), 10))
                elif r.status_code >= 400:
                    raise FuenteError(f'respuesta inesperada ({r.status_code})')
                else:
                    try:
                        return r.json()
                    except ValueError as exc:
                        raise FuenteError('la respuesta no es JSON válido') from exc
            if intento < reintentos:
                time.sleep(1.5 * (intento + 1))
        raise FuenteError(ultimo_error or 'fallo desconocido')

    # ---- interfaz del módulo ------------------------------------------
    def buscar(self, config_perfil: Dict[str, Any], **kwargs) -> ResultadoBusqueda:
        res = ResultadoBusqueda()
        slugs = [str(s).strip() for s in (config_perfil.get(self.config_clave) or []) if str(s).strip()]
        if not slugs:
            res.advertencias.append(
                f'{self.nombre}: no hay empresas configuradas ("{self.config_clave}" en el perfil).')
            return res
        vistos = set()
        for slug in slugs:
            if not SLUG_VALIDO.match(slug):
                res.errores.append(f'{self.nombre}: identificador no válido "{slug[:40]}".')
                continue
            try:
                url, params = self.url_lista(slug)
                datos = self.get_json(url, params)
                crudas = self.a_ofertas(slug, datos)
                if len(crudas) > MAX_OFERTAS_POR_FUENTE:
                    res.advertencias.append(
                        f'{self.nombre} "{slug}": {len(crudas)} ofertas; solo se procesan las primeras '
                        f'{MAX_OFERTAS_POR_FUENTE}. Usa cargos más específicos.')
                    crudas = crudas[:MAX_OFERTAS_POR_FUENTE]
                res.paginas += 1
            except FuenteError as exc:
                res.errores.append(f'{self.nombre} "{slug}": {exc}.')
                continue
            except Exception as exc:  # noqa: BLE001  - un tablero roto no debe tumbar a los demás
                logger.exception('%s "%s" falló', self.nombre, slug)
                res.errores.append(f'{self.nombre} "{slug}": error inesperado ({type(exc).__name__}).')
                continue
            for cruda in crudas:
                cruda.setdefault('portal', self.clave)
                cruda.setdefault('fuente', f'{self.clave}_api_publica')
                oferta = normalizar_job(cruda, self.clave)
                if not oferta['titulo'] or not oferta['url']:
                    continue
                if oferta['fingerprint'] in vistos:
                    continue
                vistos.add(oferta['fingerprint'])
                res.ofertas.append(oferta)
        return res

    def preparar(self, job, candidato, credenciales=None) -> ResultadoPreparacion:
        return ResultadoPreparacion(
            listo_para_postular=False, requiere_intervencion=True,
            acciones_humano=[f'Abrir el formulario de {self.nombre}', 'Completar los campos con tu perfil verificado',
                             'Adjuntar el CV', 'Enviar manualmente'],
            mensaje=f'El envío en {self.nombre} aún no está automatizado; la postulación es manual.')

    def postular(self, job, candidato, credenciales=None, **kwargs) -> ResultadoPostulacion:
        return ResultadoPostulacion(enviado=False, confirmado=False, requiere_intervencion=True,
                                    mensaje=f'Postulación manual requerida en {self.nombre}.')


def modalidad_de(texto: str) -> str:
    t = (texto or '').lower()
    if 'remote' in t or 'remoto' in t:
        return 'remota'
    if 'hybrid' in t or 'hibrid' in t:
        return 'hibrida'
    if 'on-site' in t or 'onsite' in t or 'on site' in t or 'presencial' in t:
        return 'presencial'
    return ''
