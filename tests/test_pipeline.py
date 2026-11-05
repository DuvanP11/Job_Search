from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from autoapply import adapters
from autoapply.adapters.base import AdapterBase, ResultadoBusqueda
from autoapply.autorizacion import autorizar_envio
from autoapply.browser import (CONFIRMADO, DRY_RUN, ENVIADO_SIN_CONFIRMACION, ERROR, REQUIERE_USUARIO, Aplicador,
                               ResultadoAplicacion)
from autoapply.cv import guardar_perfil_profesional
from autoapply.models import DEFAULT_PROFILE_CONFIG
from autoapply.pipeline import Orquestador
from autoapply.storage import Store, reset_store_for_tests
from tests.test_documents import CAND

BOG = ZoneInfo('America/Bogota')
MARTES_10AM = datetime(2026, 11, 3, 10, 0, tzinfo=BOG)


class Fake(Aplicador):
    clave = 'fake'

    def __init__(self, resultado=None, error=None):
        self.resultado, self.error, self.solicitudes = resultado, error, []

    def soporta(self, job):
        return True

    def aplicar(self, solicitud):
        self.solicitudes.append(solicitud)
        if self.error:
            raise self.error
        return self.resultado


def oferta(i, **kw):
    return {'id': f'j{i}', 'portal': 'fake', 'titulo': 'Analista de datos', 'empresa': f'Acme{i}', 'url': f'https://a.com/{i}',
            'descripcion': 'SQL y Power BI', 'status': 'en_evaluacion', 'puntuacion': 85, 'fingerprint': f'fp{i}',
            'matching': {'apto': True}, **kw}


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER_ORDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('AUTOAPPLY_ENABLE_SUBMIT', raising=False)
    store = Store(data_dir=str(tmp_path), database_url='')
    reset_store_for_tests(store)
    guardar_perfil_profesional('u', dict(CAND))

    def perfil(modo='revision', **cfg):
        c = {**DEFAULT_PROFILE_CONFIG, 'cargos': ['analista'], 'portales': ['fake'], 'modo': modo,
             'horario': {'dias': [0, 1, 2, 3, 4], 'desde': '08:00', 'hasta': '18:00', 'zona': 'America/Bogota'}, **cfg}
        store.save('profiles', 'u', {'id': 'default', 'config': c}, )
    perfil()
    store.save('jobs', 'u', oferta(1), record_id='j1')
    o = Orquestador(store, ahora=MARTES_10AM)
    yield store, o, perfil
    reset_store_for_tests(None)


def estado(store, j='j1'):
    return store.get('jobs', 'u', j)['status']


def preparado(store, o):
    assert o.preparar('u', 'j1')['ok']
    return store.list('documents', 'u')


def test_preparar_genera_documentos_y_espera_autorizacion(mundo):
    store, o, _ = mundo
    docs = preparado(store, o)
    assert {d['tipo'] for d in docs} == {'cv', 'carta'} and estado(store) == 'pendiente_autorizacion'


def test_enviar_sin_autorizacion_no_toca_el_navegador(mundo):
    store, o, _ = mundo
    preparado(store, o)
    ap = Fake(ResultadoAplicacion(CONFIRMADO))
    r = o.enviar('u', 'j1', aplicador=ap)
    assert r['estado'] == REQUIERE_USUARIO and ap.solicitudes == []
    assert estado(store) == 'pendiente_autorizacion'


def test_envio_confirmado_con_autorizacion_manual_y_sin_duplicar(mundo, monkeypatch):
    store, o, _ = mundo
    monkeypatch.setenv('AUTOAPPLY_ENABLE_SUBMIT', '1')
    docs = preparado(store, o)
    autorizar_envio(store, 'u', 'j1', docs)
    ap = Fake(ResultadoAplicacion(CONFIRMADO, evidencia={'senal': 'url /confirmation', 'url_final': 'https://x/confirmation'}))
    r = o.enviar('u', 'j1', aplicador=ap)
    assert r['estado'] == CONFIRMADO and estado(store) == 'postulacion_confirmada'
    assert store.get('jobs', 'u', 'j1')['evidencia_envio']['senal'] == 'url /confirmation'
    assert ap.solicitudes[0].enviar_real is True and set(ap.solicitudes[0].archivos) == {'cv', 'carta'}
    # un segundo intento NO vuelve a enviar
    assert o.enviar('u', 'j1', aplicador=ap)['estado'] == 'omitida' and len(ap.solicitudes) == 1


def test_sin_variable_de_operador_solo_hace_dry_run(mundo):
    store, o, _ = mundo
    docs = preparado(store, o)
    autorizar_envio(store, 'u', 'j1', docs)
    ap = Fake(ResultadoAplicacion(DRY_RUN, evidencia={'capturas': ['x.png']}))
    o.enviar('u', 'j1', aplicador=ap)
    assert ap.solicitudes[0].enviar_real is False
    assert estado(store) == 'lista_para_postular'
    from autoapply.autorizacion import autorizacion_vigente
    assert autorizacion_vigente(store, 'u', 'j1', store.list('documents', 'u'))[0]     # no se consumió


def test_enviado_sin_confirmacion_no_cuenta_como_confirmado(mundo, monkeypatch):
    store, o, _ = mundo
    monkeypatch.setenv('AUTOAPPLY_ENABLE_SUBMIT', '1')
    autorizar_envio(store, 'u', 'j1', preparado(store, o))
    o.enviar('u', 'j1', aplicador=Fake(ResultadoAplicacion(ENVIADO_SIN_CONFIRMACION, motivo='sin señal')))
    assert estado(store) == 'enviada_sin_confirmacion'
    assert o.engine.estadisticas('u')['postuladas'] == 1


def test_captcha_detiene_y_pasa_al_usuario(mundo):
    store, o, _ = mundo
    autorizar_envio(store, 'u', 'j1', preparado(store, o))
    r = o.enviar('u', 'j1', aplicador=Fake(ResultadoAplicacion(REQUIERE_USUARIO, motivo='CAPTCHA detectado')))
    assert r['estado'] == REQUIERE_USUARIO and estado(store) == 'requiere_intervencion'
    from autoapply import bitacora
    assert any(e['evento'] == 'requiere_usuario' for e in bitacora.listar(store, 'u'))


def test_documentos_editados_despues_de_autorizar_invalidan(mundo):
    store, o, _ = mundo
    docs = preparado(store, o)
    autorizar_envio(store, 'u', 'j1', docs)
    carta = next(d for d in docs if d['tipo'] == 'carta')
    store.mutate('documents', 'u', carta['id'], lambda a: {**a, 'contenido': 'texto cambiado'})
    ap = Fake(ResultadoAplicacion(CONFIRMADO))
    assert o.enviar('u', 'j1', aplicador=ap)['estado'] == REQUIERE_USUARIO and ap.solicitudes == []


def test_portal_sin_aplicador_requiere_postular_manual(mundo):
    store, o, _ = mundo
    autorizar_envio(store, 'u', 'j1', preparado(store, o))
    r = o.enviar('u', 'j1')                     # no hay aplicador registrado para 'fake'
    assert r['estado'] == REQUIERE_USUARIO and 'manualmente' in r['motivo']


def test_modo_autonomo_apagado_nunca_envia_solo(mundo):
    store, o, perfil = mundo
    perfil('automatico')                        # modo autónomo elegido pero NO habilitado
    preparado(store, o)
    ap = Fake(ResultadoAplicacion(CONFIRMADO))
    r = o.enviar('u', 'j1', aplicador=ap)
    assert r['estado'] == REQUIERE_USUARIO and ap.solicitudes == []


def test_modo_autonomo_habilitado_envia_lo_que_cumple_y_respeta_el_limite(mundo, monkeypatch):
    store, o, perfil = mundo
    monkeypatch.setenv('AUTOAPPLY_ENABLE_SUBMIT', '1')
    perfil('automatico', max_postulaciones_diarias=1,
           autonomo={'habilitado': True, 'habilitado_en': '2026-11-01', 'empresas_permitidas': [],
                     'ubicaciones': [], 'permitir_respuestas_ia': False, 'ventana_horaria': True})
    store.save('jobs', 'u', oferta(2), record_id='j2')
    ap = Fake(ResultadoAplicacion(CONFIRMADO, evidencia={'senal': 'texto gracias'}))
    for j in ('j1', 'j2'):
        o.preparar('u', j)
    assert o.enviar('u', 'j1', aplicador=ap)['estado'] == CONFIRMADO                 # sin autorización manual
    r2 = o.enviar('u', 'j2', aplicador=ap)                                             # límite diario = 1
    assert r2['estado'] == REQUIERE_USUARIO and 'máximo' in r2['motivo'] and len(ap.solicitudes) == 1


def test_excepcion_del_navegador_se_registra_y_se_reintenta(mundo):
    store, o, _ = mundo
    autorizar_envio(store, 'u', 'j1', preparado(store, o))
    o.cola.encolar('u', 'j1', 'enviar')
    o._ahora = datetime.now(timezone.utc)
    o.tick(aplicador=Fake(error=RuntimeError('chromium murió')))
    t = o.cola.listar('u')[0]
    assert t['estado'] == 'pendiente' and 'chromium murió' in t['ultimo_error']
    from autoapply import bitacora
    assert bitacora.listar(store, 'u', nivel='error')


def test_tick_recupera_tarea_tras_caida_del_worker(mundo, monkeypatch):
    store, o, _ = mundo
    o.cola.encolar('u', 'j1', 'preparar')
    ahora = datetime.now(timezone.utc)
    o.cola.reclamar('worker-muerto', ahora=ahora, lease_seg=60)           # el worker "muere" sin terminar
    o._ahora = ahora + timedelta(minutes=5)
    assert o.tick('worker-nuevo')['tareas'] == 1
    assert o.cola.listar('u')[0]['estado'] == 'completada' and estado(store) == 'pendiente_autorizacion'


class Portal(AdapterBase):
    clave = nombre = 'fake'

    def buscar(self, config, **kw):
        return ResultadoBusqueda(ofertas=[{'portal': 'fake', 'titulo': 'Analista de datos senior', 'empresa': 'Zeta',
                                           'descripcion': 'Buscamos analista con SQL y Power BI.', 'url': 'https://z.com/1',
                                           'modalidad': 'remota', 'pais': 'Colombia'}])


def test_programacion_descubre_prepara_y_se_detiene_en_autorizacion(mundo, monkeypatch):
    store, o, perfil = mundo
    monkeypatch.setitem(adapters.REGISTRO, 'fake', Portal)
    store.delete_collection('jobs', 'u')
    perfil('revision', programacion={'activa': True, 'cada_horas': 24, 'max_vacantes': 10}, puntuacion_minima=50)
    o._ahora = datetime.now(timezone.utc) + timedelta(minutes=1)   # las tareas se encolan con la hora real
    r = o.tick()
    assert r['descubrimientos'] == 1 and r['tareas'] == 1
    jobs = store.list('jobs', 'u')
    assert len(jobs) == 1 and jobs[0]['status'] == 'pendiente_autorizacion'
    assert len(store.list('documents', 'u')) == 2
    # no vuelve a descubrir hasta que pase el intervalo
    assert o.tick() == {'descubrimientos': 0, 'tareas': 0}
    o._ahora += timedelta(hours=25)
    assert o.tick()['descubrimientos'] == 1
    assert len(store.list('jobs', 'u')) == 1                              # la oferta repetida no se duplica
