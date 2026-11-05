import io
import json
import os
import zipfile

import pytest

from autoapply.cv import guardar_perfil_profesional
from autoapply.models import DEFAULT_PROFILE_CONFIG
from autoapply.storage import Store, reset_store_for_tests
from tests.test_documents import CAND


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER_ORDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('AUTOAPPLY_ENABLE_SUBMIT', raising=False)
    st = Store(data_dir=str(tmp_path), database_url='')
    reset_store_for_tests(st)
    guardar_perfil_profesional('u1', {**CAND, 'campos_confirmados': ['nombre_completo', 'email', 'telefono']})
    st.save('profiles', 'u1', {'id': 'default', 'config': {**DEFAULT_PROFILE_CONFIG, 'cargos': ['analista'],
                                                           'portales': ['greenhouse']}})
    for i in range(30):
        st.save('jobs', 'u1', {'id': f'j{i}', 'portal': 'greenhouse', 'titulo': f'Analista {i}', 'empresa': f'Emp{i % 3}',
                               'ubicacion': 'Bogotá', 'url': f'https://x.com/{i}', 'status': 'en_evaluacion',
                               'puntuacion': i, 'fingerprint': f'fp{i}', 'matching': {'apto': True, 'confianza': 70}},
                record_id=f'j{i}')
    import app as modulo

    def cliente(uid='u1'):
        c = modulo.app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = uid
        return c
    yield st, cliente
    reset_store_for_tests(None)


RUTAS = ['/panel', '/candidato', '/perfil', '/', '/ofertas', '/cola', '/autonomo', '/historial', '/documentos',
         '/ia', '/fuentes', '/actividad', '/privacidad', '/cv', '/diagnostico', '/api/worker']


@pytest.mark.parametrize('ruta', RUTAS)
def test_todas_las_secciones_cargan_con_navegacion(entorno, ruta):
    _, cliente = entorno
    r = cliente().get('/autoaplicar' + ruta)
    assert r.status_code == 200, ruta
    if ruta != '/api/worker':
        html = r.get_data(as_text=True)
        assert 'Historial' in html and 'Actividad' in html                     # subnav presente


def test_panel_cuenta_estados(entorno):
    st, cliente = entorno
    st.mutate('jobs', 'u1', 'j1', lambda a: {**a, 'status': 'postulacion_confirmada'})
    st.mutate('jobs', 'u1', 'j2', lambda a: {**a, 'status': 'entrevista'})
    st.mutate('jobs', 'u1', 'j3', lambda a: {**a, 'status': 'pendiente_autorizacion'})
    from autoapply.routes_extra import estadisticas_panel
    s = estadisticas_panel(st, 'u1')
    assert s['descubiertas'] == 30 and s['confirmadas'] == 2 and s['entrevistas'] == 1 and s['por_autorizar'] == 1
    assert s['enviadas'] == 2 and s['compat_promedio'] is not None
    html = cliente().get('/autoaplicar/panel').get_data(as_text=True)
    assert 'Worker:' in html and 'nunca se ha ejecutado' in html


def test_ofertas_filtra_busca_ordena_y_pagina(entorno):
    _, cliente = entorno
    c = cliente()
    html = c.get('/autoaplicar/ofertas').get_data(as_text=True)
    assert 'Analista 29' in html and 'Analista 0<' not in html.split('Analista 29')[0]    # mayor puntuación primero
    assert 'page=2' in html                                                             # 30 > 25 por página
    assert 'Analista 3<' in c.get('/autoaplicar/ofertas?q=analista 3&orden=empresa').get_data(as_text=True)
    assert 'No hay vacantes' in c.get('/autoaplicar/ofertas?q=zzz').get_data(as_text=True)
    assert c.get('/autoaplicar/ofertas?page=999&status=descartada').status_code == 200
    assert c.get('/autoaplicar/ofertas?page=abc').status_code == 200


def test_autorizar_requiere_documentos_y_encola(entorno):
    st, cliente = entorno
    c = cliente()
    r = c.post('/autoaplicar/oferta/j1/autorizar')
    assert r.status_code == 302 and st.list('queue', 'u1') == []                      # sin documentos no hay cola
    c.post('/autoaplicar/oferta/j1/documentos', data={'usar_ia': '0'})
    r = c.post('/autoaplicar/oferta/j1/autorizar')
    tareas = st.list('queue', 'u1')
    assert len(tareas) == 1 and tareas[0]['accion'] == 'enviar' and st.get('authorizations', 'u1', 'j1')['usada'] is False
    c.post('/autoaplicar/oferta/j1/autorizar')                                           # no duplica la tarea
    assert len(st.list('queue', 'u1')) == 1
    html = c.get('/autoaplicar/cola').get_data(as_text=True)
    assert 'enviar' in html and 'Cancelar' in html
    c.post(f"/autoaplicar/cola/{tareas[0]['id']}/cancelar")
    assert st.list('queue', 'u1')[0]['estado'] == 'cancelada'


def test_modo_autonomo_exige_confirmacion_explicita(entorno):
    st, cliente = entorno
    c = cliente()
    cfg = lambda: st.get('profiles', 'u1', 'default')['config']['autonomo']            # noqa: E731
    assert cfg()['habilitado'] is False
    c.post('/autoaplicar/autonomo', data={'accion': 'activar', 'confirmacion': 'si', 'acepto': 'on'})
    assert cfg()['habilitado'] is False                                                  # frase incorrecta
    c.post('/autoaplicar/autonomo', data={'accion': 'activar', 'confirmacion': 'ACTIVAR'})
    assert cfg()['habilitado'] is False                                                  # sin casilla
    c.post('/autoaplicar/autonomo', data={'accion': 'activar', 'confirmacion': 'activar', 'acepto': 'on'})
    assert cfg()['habilitado'] is True and cfg()['habilitado_en']
    c.post('/autoaplicar/autonomo', data={'accion': 'desactivar'})
    assert cfg()['habilitado'] is False
    # guardar reglas
    c.post('/autoaplicar/autonomo', data={'modo': 'automatico', 'puntuacion_minima': '80', 'max_postulaciones_diarias': '3',
                                         'empresas_permitidas': 'Acme\nGlobex', 'prog_activa': 'on', 'prog_cada_horas': '12'})
    conf = st.get('profiles', 'u1', 'default')['config']
    assert conf['modo'] == 'automatico' and conf['puntuacion_minima'] == 80 and conf['max_postulaciones_diarias'] == 3
    assert conf['autonomo']['empresas_permitidas'] == ['Acme', 'Globex'] and conf['programacion']['cada_horas'] == 12
    assert conf['autonomo']['habilitado'] is False                                       # guardar no activa nada
    c.post('/autoaplicar/autonomo', data={'modo': 'basura', 'max_postulaciones_diarias': 'x'})
    assert st.get('profiles', 'u1', 'default')['config']['modo'] == 'automatico'         # entrada inválida no cambia nada


def test_ia_por_tarea_se_guarda_y_se_usa(entorno):
    st, cliente = entorno
    cliente().post('/autoaplicar/ia', data={'prov_documentos': 'anthropic', 'modelo_documentos': 'claude-haiku-5-5',
                                           'prov_matching': 'no-existe'})
    guardado = st.get('settings', 'u1', 'ia')['tareas']
    assert guardado == {'documentos': [{'proveedor': 'anthropic', 'modelo': 'claude-haiku-5-5'}]}
    from autoapply.ai import router_para_usuario
    orden = [p.clave for p in router_para_usuario(st, 'u1')._orden('documentos')]
    assert orden == ['anthropic']
    assert 'sk-' not in json.dumps(st.get('settings', 'u1', 'ia'))
    html = cliente().get('/autoaplicar/ia').get_data(as_text=True)
    assert 'OPENAI_API_KEY' in html and 'Ollama' in html


def test_postular_manual_confirmada_exige_evidencia(entorno):
    st, cliente = entorno
    c = cliente()
    c.post('/autoaplicar/oferta/j1/postular', data={'confirmado': 'on', 'evidencia': ''})
    assert st.get('jobs', 'u1', 'j1')['status'] == 'en_evaluacion'
    c.post('/autoaplicar/oferta/j1/postular', data={'confirmado': 'on', 'evidencia': 'correo de confirmación 5/nov'})
    assert st.get('jobs', 'u1', 'j1')['status'] == 'postulacion_confirmada'
    c.post('/autoaplicar/oferta/j2/postular', data={'evidencia': ''})
    assert st.get('jobs', 'u1', 'j2')['status'] == 'enviada_sin_confirmacion'            # sin evidencia: nunca "confirmada"


def test_historial_y_evidencia_sin_salirse_de_su_carpeta(entorno, tmp_path):
    st, cliente = entorno
    carpeta = os.path.join(st.data_dir, 'evidencia', 'u1', 'j1')
    os.makedirs(carpeta)
    ok, fuera = os.path.join(carpeta, 'a.png'), os.path.join(str(tmp_path), 'secreto.png')
    for r in (ok, fuera):
        open(r, 'wb').write(b'\x89PNG fake')
    st.mutate('jobs', 'u1', 'j1', lambda a: {**a, 'status': 'postulacion_confirmada',
                                             'evidencia_envio': {'capturas': [ok, fuera], 'senal': 'URL de confirmación'}})
    c = cliente()
    html = c.get('/autoaplicar/historial').get_data(as_text=True)
    assert 'URL de confirmación' in html and 'captura 1' in html
    assert c.get('/autoaplicar/evidencia/j1/0').data.startswith(b'\x89PNG')
    assert c.get('/autoaplicar/evidencia/j1/1').status_code == 404                       # fuera de su carpeta
    assert c.get('/autoaplicar/evidencia/j1/9').status_code == 404
    assert cliente('u2').get('/autoaplicar/evidencia/j1/0').status_code == 404           # otro usuario


def test_exportar_y_eliminar_datos(entorno):
    st, cliente = entorno
    c = cliente()
    c.post('/autoaplicar/oferta/j1/documentos', data={'usar_ia': '0'})
    z = zipfile.ZipFile(io.BytesIO(c.get('/autoaplicar/privacidad/exportar').data))
    datos = json.loads(z.read('datos.json'))
    assert len(datos['jobs']) == 30 and len(datos['documents']) == 2 and datos['candidate'][0]['email'] == 'duvan@example.com'
    c.post('/autoaplicar/privacidad', data={'confirmacion': 'no'})
    assert st.list('jobs', 'u1')
    c.post('/autoaplicar/privacidad', data={'confirmacion': 'ELIMINAR'})
    assert all(st.list(col, 'u1') == [] for col in ('jobs', 'documents', 'candidate', 'profiles', 'cv'))
    assert not os.path.exists(os.path.join(st.data_dir, 'evidencia', 'u1'))


def test_descubrir_en_vercel_encola_y_no_busca(entorno, monkeypatch):
    st, cliente = entorno
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('AUTOAPPLY_BUSQUEDA', raising=False)
    from autoapply.engine import AutoApplyEngine

    def no_debe_buscar(*a, **k):
        raise AssertionError('la web no debe buscar en línea en Vercel')
    monkeypatch.setattr(AutoApplyEngine, 'descubrir', no_debe_buscar)
    c = cliente()
    r = c.post('/autoaplicar/api/descubrir')
    assert r.status_code == 202 and r.get_json()['encolada'] is True
    assert c.post('/autoaplicar/api/descubrir').get_json()['encolada'] is False     # ya hay una activa
    r = c.post('/autoaplicar/descubrir')
    assert r.status_code == 302 and r.headers['Location'].endswith('/autoaplicar/cola')
    assert [t['accion'] for t in st.list('queue', 'u1')] == ['descubrir']


def test_descubrir_en_local_sigue_siendo_directo(entorno, monkeypatch):
    st, cliente = entorno
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('AUTOAPPLY_BUSQUEDA', raising=False)
    from autoapply.engine import AutoApplyEngine
    monkeypatch.setattr(AutoApplyEngine, 'descubrir',
                        lambda *a, **k: {'nuevas': 0, 'ofertas': [], 'errores': [], 'advertencias': []})
    r = cliente().post('/autoaplicar/api/descubrir')
    assert r.status_code == 200 and st.list('queue', 'u1') == []


def test_ejecutar_en_vercel_encola_y_no_corre_en_linea(entorno, monkeypatch):
    st, cliente = entorno
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('AUTOAPPLY_BUSQUEDA', raising=False)
    from autoapply.runner import AutoApplyRunner

    def no_debe_correr(*a, **k):
        raise AssertionError('Ejecutar no debe correr en la petición web en Vercel')
    monkeypatch.setattr(AutoApplyRunner, 'ejecutar', no_debe_correr)
    r = cliente().post('/autoaplicar/ejecutar', data={'modo': 'automatico'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/autoaplicar/cola')
    assert [t['accion'] for t in st.list('queue', 'u1')] == ['descubrir']
