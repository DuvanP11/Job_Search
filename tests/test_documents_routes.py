import io

import pytest

from autoapply.storage import Store, reset_store_for_tests
from tests.test_documents import CAND, JOB


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER_ORDER', 'openai')          # sin IA: determinista
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    store = Store(data_dir=str(tmp_path), database_url='')
    reset_store_for_tests(store)
    from autoapply.cv import guardar_perfil_profesional
    guardar_perfil_profesional('u1', dict(CAND))
    guardar_perfil_profesional('u2', {})
    store.save('jobs', 'u1', {**JOB, 'id': 'j1', 'portal': 'x', 'url': 'https://a.com/1', 'status': 'en_evaluacion',
                              'fingerprint': 'fp'}, record_id='j1')
    import app as modulo
    modulo.app.config['TESTING'] = True
    def cliente(uid):
        c = modulo.app.test_client()
        with c.session_transaction() as s:
            s['user_id'] = uid
        return c
    yield store, cliente
    reset_store_for_tests(None)


def test_generar_ver_editar_y_descargar(entorno):
    store, cliente = entorno
    c = cliente('u1')
    assert c.post('/autoaplicar/oferta/j1/documentos', data={'usar_ia': '0'}).status_code == 302
    docs = store.list('documents', 'u1')
    assert {d['tipo'] for d in docs} == {'cv', 'carta'} and all(d['job_id'] == 'j1' for d in docs)
    assert store.get('jobs', 'u1', 'j1')['status'] == 'pendiente_revision'

    html = c.get('/autoaplicar/oferta/j1').get_data(as_text=True)
    assert 'Carta de presentación' in html and 'Habilidades de tu perfil que pide la oferta: SQL, Power BI' in html

    carta = next(d for d in docs if d['tipo'] == 'carta')
    c.post(f"/autoaplicar/documento/{carta['id']}/editar", data={'contenido': 'Mi carta corregida a mano'})
    assert store.get('documents', 'u1', carta['id'])['contenido'] == 'Mi carta corregida a mano'
    assert store.get('documents', 'u1', carta['id'])['generado_con'] == 'editado_por_usuario'

    cv = next(d for d in docs if d['tipo'] == 'cv')
    r = c.get(f"/autoaplicar/documento/{cv['id']}/descargar/pdf")
    assert r.status_code == 200 and r.data.startswith(b'%PDF')
    assert 'attachment; filename="CV_Acme_Analista_de_datos.pdf"' in r.headers['Content-Disposition']
    r = c.get(f"/autoaplicar/documento/{carta['id']}/descargar/docx")
    assert r.status_code == 200 and r.data[:2] == b'PK'
    # el CV original no se toca
    assert store.get('candidate', 'u1', 'principal')['resumen'] == CAND['resumen']


def test_otro_usuario_no_puede_descargar(entorno):
    store, cliente = entorno
    cliente('u1').post('/autoaplicar/oferta/j1/documentos', data={'usar_ia': '0'})
    doc = store.list('documents', 'u1')[0]
    r = cliente('u2').get(f"/autoaplicar/documento/{doc['id']}/descargar/pdf")
    assert r.status_code == 302 and not r.data.startswith(b'%PDF')
    r = cliente('u2').post(f"/autoaplicar/documento/{doc['id']}/editar", data={'contenido': 'hack'})
    assert store.get('documents', 'u1', doc['id'])['contenido'] != 'hack'


def test_sin_perfil_completo_redirige(entorno):
    store, cliente = entorno
    store.save('jobs', 'u2', {**JOB, 'id': 'j2', 'portal': 'x', 'url': 'https://a.com/2', 'fingerprint': 'f2'}, record_id='j2')
    r = cliente('u2').post('/autoaplicar/oferta/j2/documentos')
    assert r.status_code == 302 and '/candidato' in r.headers['Location']
    assert store.list('documents', 'u2') == []


def test_pregunta_sensible_endpoint(entorno):
    _, cliente = entorno
    r = cliente('u1').post('/autoaplicar/oferta/j1/pregunta', json={'pregunta': '¿Tiene antecedentes penales?'})
    assert r.get_json()['estado'] == 'requiere_usuario'
    assert cliente('u1').post('/autoaplicar/oferta/j1/pregunta', json={}).status_code == 400
