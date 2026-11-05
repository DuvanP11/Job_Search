#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Constantes y estructuras del módulo de postulación."""

from __future__ import annotations

from typing import Any, Dict, List

# ==================== ESTADOS ====================
ESTADOS = {
    'detectada': 'Descubierta',
    'en_evaluacion': 'Evaluada',
    'descartada': 'Descartada',
    'compatible': 'Compatible',
    'pendiente_documentos': 'Pendiente de documentos',
    'pendiente_revision': 'Lista para revisión',
    'lista_para_postular': 'Lista para postular',
    'pendiente_autorizacion': 'Pendiente de autorización',
    'enviando': 'Enviando (agente trabajando)',
    'enviada_sin_confirmacion': 'Enviada sin confirmación verificable',
    'postulacion_confirmada': 'Postulación confirmada',
    'en_proceso': 'En proceso de selección',
    'entrevista': 'Entrevista',
    'rechazada': 'Rechazada',
    'oferta_laboral': 'Oferta laboral',
    'cerrada': 'Cerrada',
    'requiere_intervencion': 'Requiere intervención',
    'error': 'Error',
}

# Estados que implican que YA se postuló: no se vuelve a postular ni a ofrecer.
ESTADOS_POSTULADOS = {'enviada_sin_confirmacion', 'postulacion_confirmada', 'en_proceso',
                      'entrevista', 'rechazada', 'oferta_laboral', 'cerrada_postulada'}
# Solo estos cuentan como evidencia de envío real confirmado por el portal.
ESTADOS_CONFIRMADOS = {'postulacion_confirmada', 'en_proceso', 'entrevista', 'rechazada', 'oferta_laboral'}
ESTADOS_TERMINALES = {'descartada', 'postulacion_confirmada', 'error', 'rechazada', 'oferta_laboral', 'cerrada'}

MODOS = {
    'simulacion': 'Manual (solo encuentra y evalúa; no prepara formularios)',
    'revision': 'Asistido (prepara documentos y formulario; tú autorizas el envío)',
    'automatico': 'Autónomo (envía solo lo que cumple tus reglas; desactivado hasta que lo habilites)',
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
    'ashby': {
        'nombre': 'Ashby',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'API pública de tableros. Incluye salario cuando la empresa lo publica.',
    },
    'smartrecruiters': {
        'nombre': 'SmartRecruiters',
        'descubrimiento': True,
        'envio_automatico': False,
        'nota': 'API pública de ofertas. La descripción solo se consulta para cargos que coinciden.',
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
    'ashby_boards': [],
    'smartrecruiters_companies': [],
    'puntuacion_minima': 60,
    'max_postulaciones_diarias': 5,
    'horario': {
        'dias': [0, 1, 2, 3, 4],
        'desde': '08:00',
        'hasta': '18:00',
        'zona': 'America/Bogota',
    },
    'resultados_por_cargo': 20,
    'modo': 'revision',                 # simulacion=manual · revision=asistido · automatico=autónomo
    'programacion': {'activa': False, 'cada_horas': 24, 'max_vacantes': 50},
    # Modo autónomo: APAGADO hasta que el usuario lo habilite de forma explícita.
    'autonomo': {
        'habilitado': False,
        'habilitado_en': '',            # fecha en que el usuario lo confirmó
        'empresas_permitidas': [],      # si no está vacía, solo estas
        'ubicaciones': [],              # vacío = las del perfil
        'permitir_respuestas_ia': False,  # preguntas abiertas con borrador de IA
        'ventana_horaria': True,        # respetar el horario del perfil
    },
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
