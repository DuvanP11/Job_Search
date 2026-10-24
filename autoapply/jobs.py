#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalización de ofertas y aplicación de filtros obligatorios."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    NIVELES_EDUCATIVOS, NIVELES_IDIOMA, PORTALES_SOPORTADOS,
)
from .storage import huella_empresa_cargo, huella_job

_EDUCACION_RANGO = {n: i for i, n in enumerate(NIVELES_EDUCATIVOS)}
_IDIOMA_RANGO = {n: i for i, n in enumerate(NIVELES_IDIOMA)}


def sin_acentos(texto: Any) -> str:
    normalizado = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in normalizado if not unicodedata.combining(c)).lower()


def limpiar(texto: Any, limite: int = 4000) -> str:
    if texto is None:
        return ''
    return re.sub(r'\s+', ' ', str(texto)).strip()[:limite]


def _lista(valor: Any) -> List[str]:
    if not valor:
        return []
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor if v]
    return []


def parsear_fecha(valor: Any) -> Optional[str]:
    """Devuelve YYYY-MM-DD o None. Nunca inventa la fecha de hoy."""
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()

    texto = sin_acentos(valor).strip()
    if not texto:
        return None

    if 'hoy' in texto or 'today' in texto:
        return date.today().isoformat()
    if 'ayer' in texto or 'yesterday' in texto:
        return (date.today() - timedelta(days=1)).isoformat()

    relativo = re.search(r'hace\s+(\d+)\s+(dia|dias|hora|horas|semana|semanas|mes|meses)', texto)
    if relativo:
        cantidad = int(relativo.group(1))
        unidad = relativo.group(2)
        if unidad.startswith('hora'):
            return date.today().isoformat()
        if unidad.startswith('semana'):
            return (date.today() - timedelta(weeks=cantidad)).isoformat()
        if unidad.startswith('mes'):
            return (date.today() - timedelta(days=cantidad * 30)).isoformat()
        return (date.today() - timedelta(days=cantidad)).isoformat()

    iso = re.search(r'(20\d{2})-(\d{1,2})-(\d{1,2})', texto)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat()
        except ValueError:
            pass

    dmy = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](20\d{2}|\d{2})', texto)
    if dmy:
        dia, mes, anio = dmy.groups()
        anio = int(anio) + (2000 if len(anio) == 2 else 0)
        try:
            return date(anio, int(mes), int(dia)).isoformat()
        except ValueError:
            pass

    return None


def _detectar_modalidad(texto: str) -> str:
    t = sin_acentos(texto)
    if re.search(r'\bremot[oa]\b|\bteletrabajo\b|home office|work from home', t):
        return 'remota'
    if re.search(r'\bhibrid[oa]\b', t):
        return 'hibrida'
    if re.search(r'\bpresencial\b', t):
        return 'presencial'
    return ''


def _detectar_contrato(texto: str) -> str:
    t = sin_acentos(texto)
    if 'indefinido' in t:
        return 'indefinido'
    if 'obra o labor' in t or 'obra labor' in t:
        return 'obra_labor'
    if 'prestacion de servicios' in t or 'honorarios' in t or 'contratista' in t:
        return 'prestacion_servicios'
    if 'aprendizaje' in t or 'aprendiz' in t:
        return 'aprendizaje'
    if 'practica' in t or 'practicante' in t or 'pasantia' in t:
        return 'practicas'
    if 'termino fijo' in t or 'temporal' in t:
        return 'temporal'
    return ''


def _detectar_educacion(texto: str) -> str:
    t = sin_acentos(texto)
    if 'doctorado' in t or 'phd' in t:
        return 'doctorado'
    if 'maestria' in t or 'magister' in t:
        return 'maestria'
    if 'especializacion' in t:
        return 'especializacion'
    if 'tecnologo' in t:
        return 'tecnologo'
    if 'tecnico' in t:
        return 'tecnico'
    if 'profesional' in t or 'pregrado' in t or 'universitario' in t:
        return 'pregrado'
    if 'bachiller' in t or 'secundaria' in t:
        return 'bachiller'
    return ''


def _detectar_anios_experiencia(texto: str) -> Optional[float]:
    t = sin_acentos(texto)
    if re.search(r'sin experiencia|no se requiere experiencia|recien egresado', t):
        return 0.0
    coincidencias = re.findall(
        r'(\d{1,2})\s*(?:años?|anos?)\s*(?:de\s*)?(?:experiencia|experiencia laboral)?',
        t,
    )
    valores = []
    for valor in coincidencias:
        try:
            numero = float(valor)
        except ValueError:
            continue
        if 0 <= numero <= 40:
            valores.append(numero)
    return max(valores) if valores else None


def _detectar_salario(texto: str, moneda: str = 'COP') -> Tuple[Optional[float], Optional[float], str]:
    """Extrae un salario solo cuando el texto lo declara de forma explícita."""
    t = texto or ''
    t_norm = sin_acentos(t)
    if not re.search(r'salario|sueldo|remuneracion|pago|ingreso|asignacion', t_norm):
        return None, None, moneda

    millones = re.search(
        r'\$?\s*(\d+(?:[.,]\d+)?)\s*(?:a|hasta|-)\s*(\d+(?:[.,]\d+)?)\s*millones',
        t_norm,
    )
    if millones:
        a = float(millones.group(1).replace(',', '.')) * 1_000_000
        b = float(millones.group(2).replace(',', '.')) * 1_000_000
        return a, b, 'COP'

    un_millon = re.search(r'\$?\s*(\d+(?:[.,]\d+)?)\s*millones', t_norm)
    if un_millon:
        valor = float(un_millon.group(1).replace(',', '.')) * 1_000_000
        return valor, None, 'COP'

    rango = re.search(
        r'\$?\s*(\d{1,3}(?:[.,]\d{3})+|\d{5,9})\s*(?:a|hasta|-)\s*\$?\s*(\d{1,3}(?:[.,]\d{3})+|\d{5,9})',
        t_norm,
    )
    if rango:
        try:
            a = float(rango.group(1).replace('.', '').replace(',', ''))
            b = float(rango.group(2).replace('.', '').replace(',', ''))
            if 100_000 <= a <= 100_000_000 and 100_000 <= b <= 100_000_000:
                return a, b, moneda
        except ValueError:
            pass

    simple = re.search(r'\$?\s*(\d{1,3}(?:[.,]\d{3})+|\d{6,9})', t_norm)
    if simple:
        try:
            valor = float(simple.group(1).replace('.', '').replace(',', ''))
            if 100_000 <= valor <= 100_000_000:
                return valor, None, moneda
        except ValueError:
            pass
    return None, None, moneda


def _detectar_idiomas(texto: str) -> List[Dict[str, str]]:
    t = sin_acentos(texto)
    idiomas = []
    mapa = {
        'ingles': 'Inglés',
        'english': 'Inglés',
        'frances': 'Francés',
        'portugues': 'Portugués',
        'aleman': 'Alemán',
        'italiano': 'Italiano',
    }
    niveles = {
        'nativo': 'nativo',
        'avanzado': 'avanzado',
        'b2': 'avanzado',
        'c1': 'avanzado',
        'intermedio': 'intermedio',
        'b1': 'intermedio',
        'basico': 'basico',
        'a1': 'basico',
        'a2': 'basico',
    }
    for clave, nombre in mapa.items():
        if not re.search(rf'\b{clave}\b', t):
            continue
        nivel = ''
        for marca, valor in niveles.items():
            if re.search(rf'\b{marca}\b', t):
                nivel = valor
                break
        idiomas.append({'idioma': nombre, 'nivel': nivel})
    return idiomas


def _buscar_requisitos(descripcion: str) -> List[str]:
    """Lista corta de líneas que parecen requisitos. No inventa nada."""
    if not descripcion:
        return []
    lineas = re.split(r'(?<=[.;:])\s+|\n+', descripcion)
    requisitos = [
        limpiar(linea, 300) for linea in lineas
        if re.search(r'requiere|requisito|debe|experiencia|estudios|titulo|conocimiento|manejo de',
                     sin_acentos(linea))
    ]
    return [r for r in requisitos if 15 <= len(r) <= 300][:12]


def normalizar_job(raw: Dict[str, Any], portal_key: str) -> Dict[str, Any]:
    """Convierte la salida cruda de cualquier adaptador al modelo común."""
    portal = (portal_key or raw.get('portal') or '').strip().lower()
    portal_nombre = str(
        raw.get('portal_nombre')
        or PORTALES_SOPORTADOS.get(portal, {}).get('nombre')
        or raw.get('portal')
        or portal
    )
    titulo = limpiar(raw.get('titulo') or raw.get('title'), 200)
    empresa = limpiar(raw.get('empresa') or raw.get('company'), 160) or 'No especificada'
    ubicacion = limpiar(raw.get('ubicacion') or raw.get('location'), 160)
    descripcion = limpiar(
        raw.get('descripcion') or raw.get('description') or raw.get('content'), 12000
    )
    url = limpiar(raw.get('url') or raw.get('link') or raw.get('absolute_url'), 1000)
    texto = f'{titulo} {ubicacion} {descripcion}'

    modalidad = (raw.get('modalidad') or '').strip().lower()
    if modalidad not in ('presencial', 'hibrida', 'remota'):
        modalidad = _detectar_modalidad(texto)

    salario_min = raw.get('salario_minimo') or raw.get('salary_min')
    salario_max = raw.get('salario_maximo') or raw.get('salary_max')
    moneda = str(raw.get('moneda') or raw.get('currency') or 'COP').upper()[:3]
    if salario_min is None and salario_max is None:
        salario_min, salario_max, moneda = _detectar_salario(descripcion, moneda)
    try:
        salario_min = float(salario_min) if salario_min is not None else None
    except (TypeError, ValueError):
        salario_min = None
    try:
        salario_max = float(salario_max) if salario_max is not None else None
    except (TypeError, ValueError):
        salario_max = None

    contrato = (raw.get('tipo_contrato') or '').strip().lower()
    if contrato not in ('indefinido', 'temporal', 'obra_labor', 'prestacion_servicios',
                        'aprendizaje', 'practicas', 'otro'):
        contrato = _detectar_contrato(texto)

    experiencia = raw.get('anios_experiencia')
    if experiencia is None:
        experiencia = _detectar_anios_experiencia(texto)
    try:
        experiencia = float(experiencia) if experiencia is not None else None
    except (TypeError, ValueError):
        experiencia = None

    educacion = (raw.get('nivel_educativo') or '').strip().lower()
    if educacion not in _EDUCACION_RANGO:
        educacion = _detectar_educacion(texto)

    idiomas = raw.get('idiomas')
    if not isinstance(idiomas, list) or not idiomas:
        idiomas = _detectar_idiomas(texto)

    fecha = parsear_fecha(raw.get('fecha_publicacion') or raw.get('published_at')
                          or raw.get('created_at') or raw.get('date'))

    job = {
        'portal': portal,
        'portal_nombre': portal_nombre,
        'external_id': limpiar(raw.get('external_id') or raw.get('id'), 160),
        'titulo': titulo,
        'empresa': empresa,
        'ubicacion': ubicacion,
        'ciudad': limpiar(raw.get('ciudad'), 100),
        'departamento': limpiar(raw.get('departamento'), 100),
        'pais': limpiar(raw.get('pais') or 'Colombia', 80),
        'modalidad': modalidad,
        'salario_minimo': salario_min,
        'salario_maximo': salario_max,
        'moneda': moneda,
        'tipo_contrato': contrato,
        'nivel_experiencia': limpiar(raw.get('nivel_experiencia'), 40),
        'anios_experiencia': experiencia,
        'nivel_educativo': educacion,
        'idiomas': idiomas,
        'jornada': limpiar(raw.get('jornada'), 40),
        'fecha_publicacion': fecha,
        'descripcion': descripcion,
        'requisitos': raw.get('requisitos') or _buscar_requisitos(descripcion),
        'url': url,
        'application_url': limpiar(raw.get('application_url') or url, 1000),
        'fuente': limpiar(raw.get('fuente') or raw.get('source'), 80),
    }
    job['fingerprint'] = huella_job(job)
    job['fingerprint_empresa'] = huella_empresa_cargo(job)
    job['clave_empresa_cargo'] = (
        f"{sin_acentos(job['empresa'])}|{sin_acentos(job['titulo'])}|{sin_acentos(job['ubicacion'])}"
    )
    return job


def _candidato_anios(candidate: Dict[str, Any]) -> float:
    try:
        return float(candidate.get('anios_experiencia') or 0)
    except (TypeError, ValueError):
        return 0.0


def _nivel_educativo_candidato(candidate: Dict[str, Any]) -> str:
    mejor = ''
    for estudio in candidate.get('educacion') or []:
        if not isinstance(estudio, dict):
            continue
        nivel = str(estudio.get('nivel') or _detectar_educacion(estudio.get('titulo', ''))).lower()
        if nivel in _EDUCACION_RANGO and _EDUCACION_RANGO[nivel] > _EDUCACION_RANGO.get(mejor, -1):
            mejor = nivel
    return mejor


def _idiomas_candidato(candidate: Dict[str, Any]) -> Dict[str, str]:
    salida = {}
    for item in candidate.get('idiomas') or []:
        if isinstance(item, dict):
            nombre = sin_acentos(item.get('idioma') or '')
            nivel = str(item.get('nivel') or '').lower()
            if nombre:
                salida[nombre] = nivel
        elif isinstance(item, str):
            salida[sin_acentos(item)] = 'avanzado'
    return salida


def _coincide_cargo(job: Dict[str, Any], config: Dict[str, Any]) -> bool:
    cargos = _lista(config.get('cargos')) + _lista(config.get('sinonimos'))
    if not cargos:
        return True
    texto = sin_acentos(f"{job.get('titulo', '')} {job.get('descripcion', '')[:2000]}")
    for cargo in cargos:
        tokens = [t for t in re.split(r'[^a-z0-9]+', sin_acentos(cargo)) if len(t) > 2]
        if not tokens:
            continue
        if sin_acentos(cargo) in texto:
            return True
        if all(token in texto for token in tokens):
            return True
    return False


def _ubicacion_compatible(job: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, str]:
    ciudad = sin_acentos(config.get('ciudad')) if config.get('ciudad') else ''
    departamento = sin_acentos(config.get('departamento')) if config.get('departamento') else ''
    pais = sin_acentos(config.get('pais') or 'Colombia')
    ubicacion = sin_acentos(job.get('ubicacion'))
    modalidad = job.get('modalidad')

    if modalidad == 'remota':
        return True, ''
    if not ubicacion or ubicacion in ('colombia', 'no especificada'):
        return True, 'La ubicación de la oferta no está especificada.'
    if ciudad and ciudad in ubicacion:
        return True, ''
    if departamento and departamento in ubicacion:
        return True, ''
    if pais and pais in ubicacion:
        return True, ''
    if ciudad and not departamento:
        if pais and pais in ubicacion:
            return True, ''
        return False, f'La oferta está en "{job.get("ubicacion")}" y el perfil busca {config.get("ciudad")}.'
    if departamento and not ciudad:
        if pais and pais in ubicacion:
            return True, ''
        return False, f'La oferta no coincide con el departamento {config.get("departamento")}.'
    if ciudad and departamento:
        if ciudad in ubicacion or departamento in ubicacion:
            return True, ''
        return False, f'La oferta está en "{job.get("ubicacion")}" y el perfil busca {config.get("ciudad") or config.get("departamento")}.'
    return True, ''


def aplicar_filtros(job: Dict[str, Any], profile: Dict[str, Any],
                    candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa los filtros obligatorios.

    Devuelve un diccionario con:
      pasa, motivos (por qué se descarta), requisitos_incumplidos y advertencias.
    """
    config = profile.get('config') or {}
    motivos: List[str] = []
    incumplidos: List[str] = []
    advertencias: List[str] = []

    if job.get('portal') not in (config.get('portales') or []):
        motivos.append('El portal de esta oferta no está habilitado en el perfil.')

    if not job.get('titulo'):
        motivos.append('La oferta no tiene título legible.')

    if not _coincide_cargo(job, config):
        motivos.append('El cargo no coincide con los cargos o sinónimos configurados.')

    texto = sin_acentos(f"{job.get('titulo', '')} {job.get('descripcion', '')}")

    for keyword in _lista(config.get('keywords_excluyentes')):
        if sin_acentos(keyword) in texto:
            motivos.append(f'Contiene la palabra excluyente "{keyword}".')

    for keyword in _lista(config.get('keywords_obligatorias')):
        if sin_acentos(keyword) not in texto:
            motivos.append(f'No contiene la palabra obligatoria "{keyword}".')

    for empresa in _lista(config.get('empresas_excluidas')):
        if sin_acentos(empresa) and sin_acentos(empresa) in sin_acentos(job.get('empresa')):
            motivos.append(f'La empresa "{job.get("empresa")}" está excluida.')

    compatible, motivo_ubicacion = _ubicacion_compatible(job, config)
    if not compatible:
        motivos.append(motivo_ubicacion)

    modalidades = config.get('modalidades') or []
    if modalidades and job.get('modalidad') and job['modalidad'] not in modalidades:
        motivos.append(f'La modalidad "{job["modalidad"]}" no está permitida.')

    moneda = (config.get('moneda') or 'COP').upper()
    salario_minimo = float(config.get('salario_minimo') or 0)
    if salario_minimo > 0 and job.get('salario_minimo'):
        if (job.get('moneda') or moneda).upper() == moneda and job['salario_minimo'] < salario_minimo:
            motivos.append(
                f'El salario publicado (${job["salario_minimo"]:,.0f}) está por debajo del mínimo del perfil.'
            )
        elif (job.get('moneda') or moneda).upper() != moneda:
            advertencias.append('La moneda del salario no coincide; no se pudo comparar.')

    contratos = config.get('tipos_contrato') or []
    if contratos and job.get('tipo_contrato') and job['tipo_contrato'] not in contratos:
        motivos.append(f'El tipo de contrato "{job["tipo_contrato"]}" no está permitido.')

    anios = _candidato_anios(candidate)
    requerido = job.get('anios_experiencia')
    if requerido is not None and requerido > anios:
        incumplidos.append(
            f'La oferta pide {requerido:g} años de experiencia y el perfil confirma {anios:g}.'
        )

    nivel_perfil = str(config.get('nivel_experiencia') or '')
    if nivel_perfil and job.get('nivel_experiencia') and job['nivel_experiencia'] != nivel_perfil:
        motivos.append(f'El nivel de experiencia "{job["nivel_experiencia"]}" no coincide.')

    educacion_job = job.get('nivel_educativo')
    educacion_perfil = _nivel_educativo_candidato(candidate)
    if educacion_job in _EDUCACION_RANGO:
        if not educacion_perfil:
            incumplidos.append('No hay nivel educativo confirmado en el perfil profesional.')
        elif _EDUCACION_RANGO[educacion_perfil] < _EDUCACION_RANGO[educacion_job]:
            incumplidos.append(
                f'La oferta pide {educacion_job} y el perfil confirma {educacion_perfil}.'
            )

    idiomas_perfil = _idiomas_candidato(candidate)
    for requerido_idioma in job.get('idiomas') or []:
        if not isinstance(requerido_idioma, dict):
            continue
        nombre = sin_acentos(requerido_idioma.get('idioma') or '')
        nivel = str(requerido_idioma.get('nivel') or '').lower()
        if not nombre:
            continue
        if nombre not in idiomas_perfil:
            incumplidos.append(f'La oferta pide {requerido_idioma.get("idioma")} y no está confirmado en el perfil.')
        elif nivel in _IDIOMA_RANGO:
            actual = idiomas_perfil.get(nombre, '')
            if _IDIOMA_RANGO.get(actual, -1) < _IDIOMA_RANGO[nivel]:
                incumplidos.append(
                    f'La oferta pide {requerido_idioma.get("idioma")} nivel {nivel} y el perfil confirma {actual or "sin nivel"}.'
                )

    dias = int(config.get('fecha_publicacion_dias') or 0)
    fecha = job.get('fecha_publicacion')
    if dias > 0 and fecha:
        try:
            publicada = date.fromisoformat(fecha)
            if (date.today() - publicada).days > dias:
                motivos.append(f'La oferta se publicó hace más de {dias} días.')
        except ValueError:
            pass

    if job.get('modalidad') == '':
        advertencias.append('La modalidad no está especificada en la oferta.')
    if job.get('salario_minimo') is None:
        advertencias.append('El salario no está publicado.')
    if not job.get('fecha_publicacion'):
        advertencias.append('La fecha de publicación no está disponible.')

    motivos.extend(incumplidos)
    return {
        'pasa': not motivos,
        'motivos': motivos,
        'requisitos_incumplidos': incumplidos,
        'advertencias': advertencias,
    }
