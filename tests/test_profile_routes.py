import io

import pytest

from autoapply.storage import Store, reset_store_for_tests
from tests.test_profile import CV


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    # Sin IA disponible: se prueba la ruta con lectura básica, de forma determinista.
    monkeypatch.setenv('AI_PROVIDER_ORDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    reset_store_for_tests(Store(data_dir=str(tmp_path), database_url=''))
    import app as modulo
    modulo.app.config['TESTING'] = True
    c = modulo.app.test_client()
    with c.session_transaction() as s:
        s['user_id'] = 'u-test'
    yield c
    reset_store_for_tests(None)


def test_requiere_login(tmp_path):
    reset_store_for_tests(Store(data_dir=str(tmp_path), database_url=''))
    import app as modulo
    r = modulo.app.test_client().post('/autoaplicar/cv/importar')
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_importar_editar_y_confirmar(cliente):
    r = cliente.post('/autoaplicar/cv/importar', data={
        'archivo': (io.BytesIO(CV.encode()), 'cv.txt'), 'usar_ia': '1'},
        content_type='multipart/form-data')
    assert r.status_code == 302
    html = cliente.get('/autoaplicar/candidato').get_data(as_text=True)
    assert 'duvan@example.com' in html and 'Picap' in html
    assert 'Inferido' in html            # salió del CV, aún sin confirmar
    assert 'Verificado' not in html.split('Datos personales')[1][:600]

    # El usuario confirma el email y corrige el nombre
    r = cliente.post('/autoaplicar/candidato', data={
        'nombre_completo': 'Duvan A. Perilla', 'email': 'duvan@example.com', 'telefono': '', 'ciudad': 'Bogotá',
        'linkedin': '', 'titular': '', 'resumen': '', 'anios_experiencia': '4.5', 'aspiracion_salarial': '0',
        'habilidades': 'SQL, Python', 'confirmar': ['email'],
        'exp_empresa': ['Picap', ''], 'exp_cargo': ['Analista', ''], 'exp_desde': ['2022-03', ''],
        'exp_hasta': ['actual', ''], 'exp_responsabilidades': ['Reportes\nDashboards', ''],
    })
    assert r.status_code == 302
    from autoapply.cv import obtener_perfil_profesional
    p = obtener_perfil_profesional('u-test')
    assert p['campos_confirmados'] == ['email']
    assert p['nombre_completo'] == 'Duvan A. Perilla'
    assert p['experiencia'][0]['responsabilidades'] == ['Reportes', 'Dashboards']
    assert len(p['experiencia']) == 1       # la fila vacía no se guarda

    # Reimportar no pisa lo verificado
    cliente.post('/autoaplicar/cv/importar', data={'cv_texto': CV.replace('duvan@', 'otro@'), 'usar_ia': '0'})
    assert obtener_perfil_profesional('u-test')['email'] == 'duvan@example.com'


def test_archivo_invalido_no_guarda_nada(cliente):
    r = cliente.post('/autoaplicar/cv/importar', data={'archivo': (io.BytesIO(b'MZ...'), 'virus.exe')},
                     content_type='multipart/form-data')
    assert r.status_code == 302
    from autoapply.cv import cargar_cv
    assert cargar_cv('u-test') is None


def test_aislamiento_entre_usuarios(cliente):
    cliente.post('/autoaplicar/cv/importar', data={'cv_texto': CV, 'usar_ia': '0'})
    from autoapply.cv import obtener_perfil_profesional
    assert obtener_perfil_profesional('u-test')['email']
    assert not obtener_perfil_profesional('otro-usuario').get('email')
