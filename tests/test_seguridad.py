import os
import subprocess
import sys

import pytest

from autoapply.storage import Store, reset_store_for_tests


@pytest.fixture
def cliente(tmp_path):
    reset_store_for_tests(Store(data_dir=str(tmp_path), database_url=''))
    import app as modulo
    modulo.app.config['AUTOAPPLY_CSRF_DISABLED'] = False        # aquí SÍ se exige el token

    def nuevo(uid='u1'):
        c = modulo.app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = uid
        return c
    yield nuevo
    reset_store_for_tests(None)


def token(c):
    html = c.get('/autoaplicar/privacidad').get_data(as_text=True)
    return html.split('name="csrf_token" value="')[1].split('"')[0]


def test_post_sin_token_se_rechaza(cliente):
    c = cliente()
    assert c.post('/autoaplicar/privacidad', data={'confirmacion': 'ELIMINAR'}).status_code == 400
    assert c.post('/autoaplicar/privacidad', data={'confirmacion': 'ELIMINAR', 'csrf_token': 'falso'}).status_code == 400
    assert c.post('/autoaplicar/oferta/x/pregunta', json={'pregunta': 'a'}).status_code == 400


def test_post_con_token_correcto_pasa(cliente):
    c = cliente()
    t = token(c)
    assert c.post('/autoaplicar/privacidad', data={'confirmacion': 'no', 'csrf_token': t}).status_code == 302
    assert c.post('/autoaplicar/oferta/x/pregunta', json={'pregunta': 'a'}, headers={'X-CSRF-Token': t}).status_code == 400
    # 400 aquí es "oferta no encontrada", no CSRF: el mensaje lo distingue
    r = c.post('/autoaplicar/oferta/x/pregunta', json={'pregunta': 'a'}, headers={'X-CSRF-Token': t})
    assert b'CSRF' not in r.data


def test_token_de_otra_sesion_no_sirve(cliente):
    a, b = cliente('u1'), cliente('u2')
    ta = token(a)
    assert b.post('/autoaplicar/privacidad', data={'confirmacion': 'no', 'csrf_token': ta}).status_code == 400


def test_todos_los_formularios_post_llevan_token():
    import glob
    import re
    for f in glob.glob('templates/autoapply*.html'):
        t = open(f, encoding='utf-8').read()
        for form in re.finditer(r'<form\b[^>]*method="POST"[^>]*>(.{0,200})', t, re.I | re.S):
            assert 'csrf_token' in form.group(1), f'{f}: formulario POST sin token'


def test_las_rutas_get_no_exigen_token(cliente):
    assert cliente().get('/autoaplicar/panel').status_code == 200


def test_endpoints_peligrosos_cerrados(monkeypatch):
    import app as modulo
    monkeypatch.delenv('ENABLE_DEBUG_ENDPOINTS', raising=False)
    c = modulo.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 'u'
    assert c.get('/admin/reset-all').status_code == 404
    assert c.get('/debug/storage').status_code in (401, 404)


def test_en_produccion_no_se_usa_la_clave_de_desarrollo():
    env = {**os.environ, 'VERCEL': '1'}
    env.pop('SECRET_KEY', None)
    out = subprocess.run([sys.executable, '-c', 'import app; print(app.app.config["SECRET_KEY"])'], env=env,
                         capture_output=True, text=True, cwd=os.getcwd(), timeout=60)
    clave = out.stdout.strip().splitlines()[-1]
    assert clave != 'dev-only-inseguro-cambiar-en-produccion' and len(clave) >= 32
