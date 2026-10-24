#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puntuación y evaluación de ofertas."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .jobs import sin_acentos


def _coincidencia_texto(texto: str, terminos: List[str]) -> int:
    if not terminos or not texto:
        return 0
    aciertos = 0
    for termino in terminos:
        if not termino:
            continue
        t = sin_acentos(termino)
        if len(t) < 3:
            continue
        if t in texto:
            aciertos += 1
    return aciertos


def puntuar_oferta(job: Dict[str, Any], profile: Dict[str, Any],
                   candidate: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    config = profile.get('config') or {}
    detalle: Dict[str, Any] = {
        'puntos': [],
        'total': 0,
        'razones': [],
    }
    puntuacion = 0

    texto = sin_acentos(f"{job.get('titulo', '')} {job.get('descripcion', '')}")

    cargos = [c for c in (config.get('cargos') or []) + (config.get('sinonimos') or []) if c]
    if cargos:
        if _coincidencia_texto(sin_acentos(job.get('titulo', '')), cargos) >= 1:
            puntuacion += 25
            detalle['razones'].append('Coincidencia con cargo objetivo')
        else:
            aciertos = _coincidencia_texto(texto, cargos)
            puntuacion += min(15, aciertos * 5)
            if aciertos:
                detalle['razones'].append('Coincidencia parcial con cargo')

    habilidades_cand = []
    for h in candidate.get('habilidades') or []:
        if isinstance(h, str):
            habilidades_cand.append(h)
        elif isinstance(h, dict):
            if h.get('nombre'):
                habilidades_cand.append(h['nombre'])
    if habilidades_cand:
        aciertos = _coincidencia_texto(texto, habilidades_cand)
        puntos = min(25, aciertos * 5)
        puntuacion += puntos
        if aciertos:
            detalle['razones'].append(f'{aciertos} habilidad(es) coincidente(s)')

    if job.get('modalidad') in (config.get('modalidades') or []):
        puntuacion += 10
        detalle['razones'].append('Modalidad compatible')

    if job.get('salario_minimo'):
        salario_minimo = float(config.get('salario_minimo') or 0)
        if salario_minimo > 0 and job['salario_minimo'] >= salario_minimo:
            puntuacion += 10
            detalle['razones'].append('Cumple aspiración salarial')

    if job.get('fecha_publicacion'):
        puntuacion += 10
        detalle['razones'].append('Tiene fecha de publicación')

    if job.get('descripcion') and len(job['descripcion']) > 200:
        puntuacion += 10
        detalle['razones'].append('Descripción detallada')

    puntuacion = max(0, min(100, puntuacion))
    detalle['total'] = puntuacion
    return puntuacion, detalle
