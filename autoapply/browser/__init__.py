#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from .base import (CONFIRMADO, DRY_RUN, ENVIADO_SIN_CONFIRMACION, ERROR, REQUIERE_USUARIO, Aplicador,
                   ResultadoAplicacion, SolicitudAplicacion, obtener_aplicador, portales_con_envio,
                   registrar_aplicador)

__all__ = ['CONFIRMADO', 'DRY_RUN', 'ENVIADO_SIN_CONFIRMACION', 'ERROR', 'REQUIERE_USUARIO', 'Aplicador',
           'ResultadoAplicacion', 'SolicitudAplicacion', 'obtener_aplicador', 'portales_con_envio',
           'registrar_aplicador']


def _registrar_aplicadores():
    from .formulario import GreenhouseAplicador, LeverAplicador
    registrar_aplicador('greenhouse', GreenhouseAplicador)
    registrar_aplicador('lever', LeverAplicador)


_registrar_aplicadores()
