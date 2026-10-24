#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from .base import AdapterBase, ResultadoBusqueda, ResultadoPreparacion, ResultadoPostulacion
from .computrabajo import ComputrabajoAdapter
from .elempleo import ElEmpleoAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter

REGISTRO = {
    'computrabajo': ComputrabajoAdapter,
    'elempleo': ElEmpleoAdapter,
    'greenhouse': GreenhouseAdapter,
    'lever': LeverAdapter,
}


def obtener_adapter(portal: str):
    cls = REGISTRO.get((portal or '').strip().lower())
    return cls() if cls else None


def listar_adapters():
    return [
        {'clave': k, 'nombre': cls().nombre, 'soporta_busqueda': cls().soporta_busqueda,
         'soporta_postulacion': cls().soporta_postulacion}
        for k, cls in REGISTRO.items()
    ]
