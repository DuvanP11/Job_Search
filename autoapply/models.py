#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Constantes y estructuras del módulo de postulación."""

from __future__ import annotations

from typing import Any, Dict, List

# ==================== ESTADOS ====================
ESTADOS = {
    'detectada': 'Detectada',
    'en_evaluacion': 'En evaluación',
    'descartada': 'Descartada',
    'pendiente_revision': 'Pendiente de revisión',
    'lista_para_postular': 'Lista para postular',
    'en_proceso': 'En proceso',
    'enviada_sin_confirmacion': 'Enviada sin confirmación verificable',
    'postulacion_confirmada': 'Postulación confirmada',
    'requiere_intervencion': 'Requiere intervención',
    'error': 'Error',
}

ESTADOS_POSTULADOS = {'enviada_sin_confirmacion', 'postulacion_confirmada'}
ESTADOS_TERMINALES = {'descartada', 'postulacion_confirmada', 'error'}

MODOS = {
    'simulacion': 'Simulación (no envía)',
    'revision': 'Revisión (prepara y pide aprobación)',
    'automatico': 'Automático (envía si el portal lo permite)',
}

MODALIDADES = ['presencial', 'hibrida', 'remota']
CONTRATOS = ['indefinido', 'temporal', 'obra_labor', 'prestacion_servicios',
             'aprendizaje', 'practicas', 'otro']
NIVELES_EXPERIENCIA = ['sin_experiencia', 'junior', 'semi_senior', 'senior', 'lead']
NIVELES_EDUCATIVOS = ['bachiller', 'tecnico', 'tecnologo', 'pregrado', 'especializacion',
                      'maestria', 'doctorado']
NIVELES_IDIOMA = ['basico', 'intermedio', 'avanzado', 'nativo']
JORNADAS = ['tiempo_completo', 'medio_tiempo', 'por_horas', 'flexible']

PORTALES_SOPORTADOS = {
    'computrabajo': {
        'nombre': 'Computrabajo',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'Descubrimiento y preparación. El envío se hace en el portal.',
    },
    'elempleo': {
        'nombre': 'ElEmpleo',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'Descubrimiento y preparación. El envío se hace en el portal.',
    },
    'greenhouse': {
        'nombre': 'Greenhouse',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'Requiere tableros públicos configurados. Formulario propio del ATS.',
    },
    'lever': {
        'nombre': 'Lever',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'Requiere empresas públicas configuradas. Formulario propio del ATS.',
    },
}

PORTALES_NO_DISPONIBLES = {
    'magneto': 'Sin adaptador verificado; la búsqueda general existente lo intenta, pero no se usa para postular.',
    'indeed': 'Indeed no ofrece una API pública de postulación y bloquea automatización.',
    'trabajando': 'Sin adaptador de postulación verificado.',
    'linkedin': 'LinkedIn prohíbe la automatización de postulaciones en sus términos.',
    'serviciodeempleo': 'Sin adaptador funcional verificado.',
    'talentbox': 'Sin adaptador funcional verificado.',
    'colsubsidio': 'Sin adaptador funcional verificado.',
    'unmejorempleo': 'Sin adaptador funcional verificado.',
}

# ==================== CONFIGURACIÓN POR DEFECTO ====================
DEFAULT_PROFILE_CONFIG: Dict[str, Any] = {
    'cargos': [],
    'sinonimos': [],
    'keywords_obligatorias': [],
    'keywords_excluyentes': [],
    'pais': 'Colombia',
    'departamento': '',
    'ciudad': '',
    'radio_km': 0,
    'modalidades': ['presencial', 'hibrida', 'remota'],
    'salario_minimo': 0,
    'moneda': 'COP',
    'tipos_contrato': [],
    'nivel_experiencia': '',
    'nivel_educativo': '',
    'idiomas': [],
    'jornada': '',
    'fecha_publicacion_dias': 30,
    'empresas_excluidas': [],
    'portales': ['computrabajo', 'elempleo'],
    'greenhouse_boards': [],
    'lever_companies': [],
    'puntuacion_minima': 60,
    'max_postulaciones_diarias': 5,
    'horario': {
        'dias': [0, 1, 2, 3, 4],
        'desde': '08:00',
        'hasta': '18:00',
        'zona': 'America/Bogota',
    },
    'resultados_por_cargo': 20,
}

DEFAULT_CANDIDATE: Dict[str, Any] = {
    'nombre_completo': '',
    'email': '',
    'telefono': '',
    'ciudad': '',
    'pais': 'Colombia',
    'linkedin': '',
    'titular': '',
    'resumen': '',
    'anios_experiencia': 0,
    'habilidades': [],
    'habilidades_blandas': [],
    'educacion': [],
    'idiomas': [],
    'certificaciones': [],
    'experiencia': [],
    'aspiracion_salarial': 0,
    'moneda': 'COP',
    'autorizacion_laboral': '',
    'disponibilidad': '',
    'campos_confirmados': [],
}


def candidate_vacio() -> Dict[str, Any]:
    import copy
    return copy.deepcopy(DEFAULT_CANDIDATE)


def profile_vacio(nombre: str = 'Perfil principal') -> Dict[str, Any]:
    import copy
    return {
        'nombre': nombre,
        'activo': True,
        'config': copy.deepcopy(DEFAULT_PROFILE_CONFIG),
    }


def lista_texto(valor: Any, limite: int = 40, largo: int = 120) -> List[str]:
    """Normaliza una lista de cadenas recibida del formulario o de JSON."""
    if valor is None:
        return []
    if isinstance(valor, str):
        valor = valor.replace('\n', ',').split(',')
    if not isinstance(valor, (list, tuple)):
        return []
    salida: List[str] = []
    vistos = set()
    for item in valor:
        texto = str(item or '').strip()[:largo]
        clave = texto.lower()
        if not texto or clave in vistos:
            continue
        vistos.add(clave)
        salida.append(texto)
        if len(salida) >= limite:
            break
    return salida
