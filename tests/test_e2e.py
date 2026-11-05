"""Integración completa: perfil verificado → preparar → autorizar → worker (Chromium real) → confirmado → historial."""
import os

import pytest

pytest.importorskip('playwright')

from autoapply.browser.formulario import GreenhouseAplicador
from autoapply.cv import guardar_perfil_profesional
from autoapply.models import DEFAULT_PROFILE_CONFIG
from autoapply.pipeline import Orquestador
from autoapply.storage import Store, reset_store_for_tests
from tests.servidor_ats import Servidor
from tests.test_documents import CAND


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f'Chromium no disponible: {exc}')
    monkeypatch.setenv('AI_PROVIDER_ORDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    st = Store(data_dir=str(tmp_path), database_url='')
    reset_store_for_tests(st)
    guardar_perfil_profesional('u1', {**CAND, 'campos_confirmados': ['nombre_completo', 'email', 'telefono', 'ciudad', 'linkedin']})
    st.save('profiles', 'u1', {'id': 'default', 'config': {**DEFAULT_PROFILE_CONFIG, 'cargos': ['analista'],
                                                           'portales': ['greenhouse'], 'modo': 'revision'}})
    with Servidor() as srv:
        st.save('jobs', 'u1', {'id': 'j1', 'portal': 'greenhouse', 'titulo': 'Analista de datos', 'empresa': 'Acme',
                               'descripcion': 'SQL y Power BI', 'url': srv.base + '/form/ok',
                               'application_url': srv.base + '/form/ok', 'status': 'en_evaluacion', 'puntuacion': 90,
                               'fingerprint': 'fp', 'matching': {'apto': True, 'confianza': 80}}, record_id='j1')
        import app as modulo
        c = modulo.app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = 'u1'
        yield st, srv, c
    reset_store_for_tests(None)


def test_flujo_completo(mundo, monkeypatch):
    st, srv, c = mundo
    aplicador = GreenhouseAplicador(permitir_local=True)
    o = Orquestador(st)

    # 1) el agente prepara los documentos y se detiene esperando al usuario
    o.cola.encolar('u1', 'j1', 'preparar')
    assert o.tick(aplicador=aplicador)['tareas'] == 1
    assert st.get('jobs', 'u1', 'j1')['status'] == 'pendiente_autorizacion' and not srv.posts

    # 2) sin autorización, aunque haya tarea de envío, no se toca el portal
    o.cola.encolar('u1', 'j1', 'enviar')
    o.tick(aplicador=aplicador)
    assert not srv.posts and st.get('jobs', 'u1', 'j1')['status'] == 'pendiente_autorizacion'

    # 3) el usuario autoriza desde la web (queda en cola); el worker SIN habilitar envío real solo verifica
    c.post('/autoaplicar/oferta/j1/autorizar')
    o.tick(aplicador=aplicador)
    assert not srv.posts and st.get('jobs', 'u1', 'j1')['status'] == 'lista_para_postular'
    assert st.get('jobs', 'u1', 'j1')['evidencia_dry_run']['capturas']

    # 4) el operador habilita el envío real y el usuario vuelve a encolar: envío + confirmación
    monkeypatch.setenv('AUTOAPPLY_ENABLE_SUBMIT', '1')
    c.post('/autoaplicar/oferta/j1/autorizar')
    o.tick(aplicador=aplicador)
    job = st.get('jobs', 'u1', 'j1')
    assert job['status'] == 'postulacion_confirmada' and len(srv.posts) == 1
    assert job['evidencia_envio']['senal'] and os.path.exists(job['evidencia_envio']['capturas'][-1])
    assert b'duvan@example.com' in srv.posts[0][1]

    # 5) no se puede duplicar: ni reautorizando ni reencolando
    c.post('/autoaplicar/oferta/j1/autorizar')
    o.cola.encolar('u1', 'j1', 'enviar')
    o.tick(aplicador=aplicador)
    assert len(srv.posts) == 1

    # 6) el historial lo muestra con evidencia
    html = c.get('/autoaplicar/historial').get_data(as_text=True)
    assert 'Analista de datos' in html and 'captura' in html and 'Postulación confirmada' in html
    assert c.get('/autoaplicar/evidencia/j1/0').status_code == 200
    from autoapply import bitacora
    eventos = [e['evento'] for e in bitacora.listar(st, 'u1', 100)]
    assert {'documentos', 'autorizacion', 'dry_run', 'envio_confirmado'} <= set(eventos)
