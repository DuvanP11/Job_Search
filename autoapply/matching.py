#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de compatibilidad oferta ↔ perfil.

Determinístico a propósito: los requisitos excluyentes y el puntaje no
dependen de ningún modelo. Cada requisito queda como cumplido, parcial,
no cumplido o desconocido, con su explicación. El puntaje es un indicador
de afinidad, NO una probabilidad de contratación.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .jobs import (
    _EDUCACION_RANGO, _candidato_anios, _coincide_cargo, _idiomas_candidato,
    _nivel_educativo_candidato, aplicar_filtros, sin_acentos,
)

CUMPLIDO, PARCIAL, NO_CUMPLIDO, DESCONOCIDO = 'cumplido', 'parcial', 'no_cumplido', 'desconocido'
_VALOR = {CUMPLIDO: 1.0, PARCIAL: 0.5, NO_CUMPLIDO: 0.0}

PESOS = {
    'cargo': 25, 'habilidades': 25, 'experiencia': 15, 'educacion': 10,
    'ubicacion': 10, 'modalidad': 5, 'salario': 5, 'idiomas': 5,
}

_PREFIJO_TITULO = (r'(?:titulo\s+(?:profesional\s+|universitario\s+|tecnico\s+|tecnologo\s+)?|profesional\s+|'
                   r'licenciad[oa]\s+|ingenier[oa]\s+|tecnolog[oa]\s+|tecnic[oa]\s+)')
_RE_TITULO = re.compile(_PREFIJO_TITULO + r'(?:en|de|como)\s+([a-z ,/]{4,80}?)(?=\s+(?:con|y|que|para|o)\s|[.;:()\n]|$)')
_STOP = {'area', 'areas', 'afines', 'afin', 'carrera', 'carreras', 'ciencias', 'gestion', 'administracion_'}


def _tokens(texto: str) -> set:
    return {t[:5] for t in re.findall(r'[a-z]{4,}', sin_acentos(texto)) if t not in _STOP}


def _titulos_del_candidato(candidate: Dict[str, Any]) -> List[str]:
    salida = []
    for e in candidate.get('educacion') or []:
        if isinstance(e, dict):
            salida.append(f"{e.get('titulo', '')} {e.get('campo', '')} {e.get('area', '')}")
        elif isinstance(e, str):
            salida.append(e)
    return salida


def _req(categoria, requisito, estado, detalle, obligatorio=False) -> Dict[str, Any]:
    return {'categoria': categoria, 'requisito': requisito, 'estado': estado,
            'detalle': detalle, 'obligatorio': obligatorio}


def _titulo_especifico(job, candidate) -> List[Dict[str, Any]]:
    texto = sin_acentos(f"{job.get('descripcion', '')} {' '.join(job.get('requisitos') or [])}")
    salida = []
    for m in _RE_TITULO.finditer(texto):
        area = m.group(1).strip(' ,/')
        pedidos = _tokens(area)
        if not pedidos:
            continue
        contexto = texto[max(0, m.start() - 60): m.end() + 80]
        flexible = bool(re.search(r'afines?|equivalent|o experiencia|preferiblemente|deseable', contexto))
        propios = _titulos_del_candidato(candidate)
        if not propios:
            salida.append(_req('titulo', f'Título en {area}', DESCONOCIDO,
                               'No hay estudios registrados en el perfil para comparar.', False))
            continue
        if any(pedidos & _tokens(p) for p in propios):
            salida.append(_req('titulo', f'Título en {area}', CUMPLIDO,
                               'El perfil tiene un título relacionado.', False))
        else:
            salida.append(_req('titulo', f'Título en {area}',
                               PARCIAL if flexible else NO_CUMPLIDO,
                               'La oferta pide un título en esa área y el perfil no tiene uno relacionado'
                               + (' (admite afines).' if flexible else '.'),
                               obligatorio=not flexible))
        break  # con el primer título exigido basta
    return salida


def evaluar_compatibilidad(job: Dict[str, Any], profile: Dict[str, Any],
                           candidate: Dict[str, Any]) -> Dict[str, Any]:
    config = profile.get('config') or {}
    reqs: List[Dict[str, Any]] = []
    texto = sin_acentos(f"{job.get('titulo', '')} {job.get('descripcion', '')}")

    # Cargo
    if config.get('cargos') or config.get('sinonimos'):
        ok = _coincide_cargo(job, config)
        reqs.append(_req('cargo', 'Cargo objetivo', CUMPLIDO if ok else NO_CUMPLIDO,
                         'El cargo coincide con los cargos o sinónimos configurados.' if ok
                         else 'El cargo no coincide con los configurados.', obligatorio=True))

    # Experiencia
    pedidos = job.get('anios_experiencia')
    propios = _candidato_anios(candidate)
    if pedidos is None:
        reqs.append(_req('experiencia', 'Años de experiencia', DESCONOCIDO, 'La oferta no indica años.'))
    elif propios >= pedidos:
        reqs.append(_req('experiencia', f'{pedidos:g} años de experiencia', CUMPLIDO,
                         f'El perfil confirma {propios:g} años.'))
    elif propios >= 0.75 * pedidos:
        reqs.append(_req('experiencia', f'{pedidos:g} años de experiencia', PARCIAL,
                         f'El perfil confirma {propios:g} años, cerca de lo pedido.'))
    else:
        reqs.append(_req('experiencia', f'{pedidos:g} años de experiencia', NO_CUMPLIDO,
                         f'El perfil confirma {propios:g} años.', obligatorio=True))

    # Nivel educativo
    nivel_job = job.get('nivel_educativo')
    nivel_perfil = _nivel_educativo_candidato(candidate)
    if nivel_job in _EDUCACION_RANGO:
        if not nivel_perfil:
            reqs.append(_req('educacion', f'Nivel {nivel_job}', DESCONOCIDO,
                             'No hay nivel educativo confirmado en el perfil.'))
        elif _EDUCACION_RANGO[nivel_perfil] >= _EDUCACION_RANGO[nivel_job]:
            reqs.append(_req('educacion', f'Nivel {nivel_job}', CUMPLIDO, f'El perfil confirma {nivel_perfil}.'))
        else:
            reqs.append(_req('educacion', f'Nivel {nivel_job}', NO_CUMPLIDO,
                             f'El perfil confirma {nivel_perfil}.', obligatorio=True))
    else:
        reqs.append(_req('educacion', 'Nivel educativo', DESCONOCIDO, 'La oferta no lo especifica.'))

    # Título específico (filtro independiente del puntaje)
    reqs.extend(_titulo_especifico(job, candidate))

    # Habilidades
    habs = []
    for h in candidate.get('habilidades') or []:
        nombre = h.get('nombre') if isinstance(h, dict) else h
        if nombre and len(str(nombre)) >= 3:
            habs.append(str(nombre))
    if not job.get('descripcion'):
        reqs.append(_req('habilidades', 'Habilidades y herramientas', DESCONOCIDO,
                         'La oferta no trae descripción para comparar.'))
    elif not habs:
        reqs.append(_req('habilidades', 'Habilidades y herramientas', DESCONOCIDO,
                         'El perfil no tiene habilidades registradas.'))
    else:
        hallazgos = [h for h in habs if re.search(r'\b' + re.escape(sin_acentos(h)) + r'\b', texto)]
        estado = CUMPLIDO if len(hallazgos) >= 3 else PARCIAL if hallazgos else NO_CUMPLIDO
        reqs.append(_req('habilidades', 'Habilidades y herramientas', estado,
                         f'{len(hallazgos)} habilidad(es) del perfil aparecen en la oferta'
                         + (f': {", ".join(hallazgos[:6])}.' if hallazgos else '.')))

    # Idiomas
    idiomas_perfil = _idiomas_candidato(candidate)
    for i in job.get('idiomas') or []:
        if not isinstance(i, dict) or not i.get('idioma'):
            continue
        nombre = sin_acentos(i['idioma'])
        if nombre in idiomas_perfil:
            reqs.append(_req('idiomas', f"{i['idioma']}", CUMPLIDO, 'El perfil lo confirma.'))
        else:
            reqs.append(_req('idiomas', f"{i['idioma']}", NO_CUMPLIDO,
                             'No está confirmado en el perfil.', obligatorio=True))

    # Ubicación / modalidad / salario
    filtros = aplicar_filtros(job, profile, candidate)
    ubic = [m for m in filtros['motivos'] if 'ubicaci' in sin_acentos(m) or 'ciudad' in sin_acentos(m)]
    if job.get('ciudad') or job.get('ubicacion'):
        reqs.append(_req('ubicacion', 'Ubicación', NO_CUMPLIDO if ubic else CUMPLIDO,
                         ubic[0] if ubic else 'La ubicación es compatible.', obligatorio=bool(ubic)))
    else:
        reqs.append(_req('ubicacion', 'Ubicación', DESCONOCIDO, 'La oferta no indica ubicación.'))

    modalidades = config.get('modalidades') or []
    if not job.get('modalidad'):
        reqs.append(_req('modalidad', 'Modalidad', DESCONOCIDO, 'La oferta no la especifica.'))
    elif modalidades and job['modalidad'] not in modalidades:
        reqs.append(_req('modalidad', 'Modalidad', NO_CUMPLIDO,
                         f"La modalidad {job['modalidad']} no está permitida.", obligatorio=True))
    else:
        reqs.append(_req('modalidad', 'Modalidad', CUMPLIDO, f"Modalidad {job['modalidad']} permitida."))

    minimo = float(config.get('salario_minimo') or 0)
    if not job.get('salario_minimo'):
        reqs.append(_req('salario', 'Salario', DESCONOCIDO, 'La oferta no publica salario.'))
    elif minimo <= 0:
        reqs.append(_req('salario', 'Salario', DESCONOCIDO, 'No hay salario mínimo configurado.'))
    elif job['salario_minimo'] >= minimo:
        reqs.append(_req('salario', 'Salario', CUMPLIDO, 'Cumple el mínimo configurado.'))
    else:
        reqs.append(_req('salario', 'Salario', NO_CUMPLIDO,
                         'Está por debajo del mínimo configurado.', obligatorio=True))

    # Puntaje: solo cuentan los requisitos conocidos; la confianza refleja el resto.
    suma = peso_total = peso_posible = 0.0
    for r in reqs:
        peso = PESOS.get(r['categoria'], 5)
        peso_posible += peso
        if r['estado'] in _VALOR:
            suma += peso * _VALOR[r['estado']]
            peso_total += peso
    score = round(100 * suma / peso_total) if peso_total else 0
    confianza = round(100 * peso_total / peso_posible) if peso_posible else 0

    gates = [r for r in reqs if r['obligatorio'] and r['estado'] == NO_CUMPLIDO]
    motivos_filtro = [m for m in filtros['motivos'] if m not in {g['detalle'] for g in gates}]
    apto = not gates and filtros['pasa']

    explicacion: List[str] = []
    for g in gates:
        explicacion.append(f"Excluyente — {g['requisito']}: {g['detalle']}")
    for m in motivos_filtro:
        explicacion.append(f'Filtro — {m}')
    for r in reqs:
        if r['estado'] == CUMPLIDO:
            explicacion.append(f"✔ {r['requisito']}: {r['detalle']}")
    explicacion.append(f'Afinidad {score}/100 con {confianza}% de requisitos verificables. '
                       'Es un indicador, no una probabilidad de contratación.')

    return {
        'score': score, 'confianza': confianza, 'apto': apto,
        'excluyentes': gates, 'requisitos': reqs,
        'filtros': filtros, 'explicacion': explicacion,
    }
