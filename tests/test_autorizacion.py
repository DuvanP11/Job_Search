from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from autoapply.autorizacion import (autorizar_envio, autorizacion_vigente, consumir_autorizacion,
                                    evaluar_autonomo)
from autoapply.storage import Store

BOG = ZoneInfo('America/Bogota')
MARTES_10AM = datetime(2026, 11, 3, 10, 0, tzinfo=BOG)


def perfil(**auto):
    return {'config': {'portales': ['greenhouse'], 'puntuacion_minima': 60, 'max_postulaciones_diarias': 5,
                       'empresas_excluidas': ['Mala SA'],
                       'horario': {'dias': [0, 1, 2, 3, 4], 'desde': '08:00', 'hasta': '18:00', 'zona': 'America/Bogota'},
                       'autonomo': {'habilitado': True, 'habilitado_en': '2026-11-01', **auto}}}


JOB = {'portal': 'greenhouse', 'empresa': 'Acme', 'puntuacion': 80, 'status': 'pendiente_autorizacion',
       'matching': {'apto': True}}


def evaluar(job=None, prof=None, **kw):
    args = dict(docs_listos=True, adapter_envia=True, postuladas_hoy=0, ahora=MARTES_10AM)
    args.update(kw)
    return evaluar_autonomo({**JOB, **(job or {})}, prof or perfil(), **args)


def test_todo_en_regla():
    assert evaluar() == (True, [])


def test_apagado_por_defecto_y_sin_fecha_de_confirmacion():
    ok, m = evaluar(prof={'config': {'autonomo': {'habilitado': False}}})
    assert not ok and 'no está habilitado' in m[0]
    ok, _ = evaluar(prof=perfil(habilitado_en=''))
    assert not ok


@pytest.mark.parametrize('cambio,texto', [
    ({'matching': {'apto': False}}, 'excluyentes'),
    ({'puntuacion': 40}, 'por debajo del mínimo'),
    ({'empresa': 'Mala SA'}, 'excluida'),
    ({'portal': 'indeed'}, 'fuentes autorizadas'),
    ({'status': 'postulacion_confirmada'}, 'Ya existe'),
    ({'vigente_hasta': '2020-01-01'}, 'vencida'),
])
def test_cada_regla_bloquea(cambio, texto):
    ok, m = evaluar(job=cambio)
    assert not ok and any(texto in x for x in m)


def test_otras_condiciones():
    assert not evaluar(docs_listos=False)[0]
    assert not evaluar(adapter_envia=False)[0]
    assert not evaluar(postuladas_hoy=5)[0]
    assert not evaluar(ya_postulado=True)[0]
    assert not evaluar(ahora=MARTES_10AM.replace(hour=22))[0]                    # fuera de horario
    assert not evaluar(ahora=MARTES_10AM + timedelta(days=4))[0]                 # sábado
    assert evaluar(prof=perfil(ventana_horaria=False), ahora=MARTES_10AM.replace(hour=22))[0]


def test_lista_de_empresas_permitidas():
    assert evaluar(prof=perfil(empresas_permitidas=['acme']))[0]
    ok, m = evaluar(prof=perfil(empresas_permitidas=['Otra']))
    assert not ok and 'permitidas' in m[0]


def test_autorizacion_manual_se_invalida_si_cambian_los_documentos(tmp_path):
    st = Store(data_dir=str(tmp_path), database_url='')
    docs = [{'id': 'a', 'tipo': 'cv', 'contenido': {'x': 1}}, {'id': 'b', 'tipo': 'carta', 'contenido': 'hola'}]
    assert not autorizacion_vigente(st, 'u', 'j1', docs)[0]
    autorizar_envio(st, 'u', 'j1', docs)
    assert autorizacion_vigente(st, 'u', 'j1', docs) == (True, '')
    cambiados = [docs[0], {**docs[1], 'contenido': 'hola editada'}]
    ok, m = autorizacion_vigente(st, 'u', 'j1', cambiados)
    assert not ok and 'cambiaron' in m
    consumir_autorizacion(st, 'u', 'j1')
    ok, m = autorizacion_vigente(st, 'u', 'j1', docs)
    assert not ok and 'ya se usó' in m
    autorizar_envio(st, 'u', 'j1', docs)                    # volver a autorizar la reactiva
    assert autorizacion_vigente(st, 'u', 'j1', docs)[0]
