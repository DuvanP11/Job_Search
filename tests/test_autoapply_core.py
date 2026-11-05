"""Pruebas del núcleo de autoapply: seguridad, envío real y endpoints peligrosos."""
import pytest

from autoapply import adapters
from autoapply.adapters.base import AdapterBase, ResultadoPreparacion, ResultadoPostulacion
from autoapply.engine import AutoApplyEngine
from autoapply.runner import AutoApplyRunner
from autoapply.security import validar_url_aplicacion
from autoapply.storage import Store, reset_store_for_tests


@pytest.mark.parametrize('url', [
    'http://localhost/x', 'http://127.0.0.1/x', 'http://10.0.0.5/x',
    'http://192.168.1.1/x', 'http://169.254.169.254/latest', 'http://[::1]/x',
    'http://servicio.internal/x', 'ftp://empresa.com/x', 'javascript:alert(1)', '',
    'https://www.linkedin.com/jobs/1', 'https://co.indeed.com/viewjob',
])
def test_urls_bloqueadas(url):
    assert validar_url_aplicacion(url)[0] is False


@pytest.mark.parametrize('url', [
    'https://boards.greenhouse.io/acme/jobs/1',
    # Antes se bloqueaba por contener "10." como subcadena:
    'https://empresa.com/ofertas/2024-10.5/ingeniero',
    'https://jobs.lever.co/acme/abc',
])
def test_urls_permitidas(url):
    assert validar_url_aplicacion(url) == (True, '')


def test_admin_reset_all_ya_no_existe():
    import app as modulo
    cliente = modulo.app.test_client()
    assert cliente.get('/admin/reset-all').status_code == 404
    assert cliente.post('/admin/reset-all', data={'admin_password': 'reset2025'}).status_code in (404, 405)


class _Fake(AdapterBase):
    nombre = clave = 'fake'
    resultado = ResultadoPostulacion()

    def preparar(self, job, candidato, credenciales=None):
        return ResultadoPreparacion(listo_para_postular=True)

    def postular(self, job, candidato, credenciales=None, **kw):
        return type(self).resultado


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    store = Store(data_dir=str(tmp_path), database_url='')
    reset_store_for_tests(store)
    monkeypatch.setitem(adapters.REGISTRO, 'fake', _Fake)
    monkeypatch.setattr(AutoApplyEngine, 'descubrir',
                        lambda self, *a, **k: {'nuevas': 0, 'ofertas': [], 'errores': [], 'advertencias': []})
    store.save('jobs', 'u1', {'id': 'j1', 'portal': 'fake', 'titulo': 'Analista', 'empresa': 'Acme',
                              'url': 'https://acme.com/j1', 'status': 'en_evaluacion', 'puntuacion': 90,
                              'filtros': {'pasa': True}, 'fingerprint': 'fp1'})
    yield store
    reset_store_for_tests(None)


PERFIL = {'config': {'cargos': ['Analista'], 'portales': ['fake'], 'max_postulaciones_diarias': 5,
                     'puntuacion_minima': 60}}


def _estado(store):
    return store.list('jobs', 'u1')[0]['status']


def test_automatico_no_marca_enviada_si_el_adaptador_no_envio(entorno):
    _Fake.resultado = ResultadoPostulacion(enviado=False, mensaje='bloqueado por CAPTCHA')
    out = AutoApplyRunner(entorno).ejecutar('u1', PERFIL, {}, modo='automatico')
    assert out['postuladas'] == 0
    assert _estado(entorno) == 'requiere_intervencion'


def test_automatico_envio_sin_confirmacion_no_cuenta_como_confirmada(entorno):
    _Fake.resultado = ResultadoPostulacion(enviado=True, confirmado=False, mensaje='enviado')
    out = AutoApplyRunner(entorno).ejecutar('u1', PERFIL, {}, modo='automatico')
    assert out['postuladas'] == 1
    assert _estado(entorno) == 'enviada_sin_confirmacion'


def test_automatico_con_confirmacion_real(entorno):
    _Fake.resultado = ResultadoPostulacion(enviado=True, confirmado=True, captura_evidencia='shot.png')
    AutoApplyRunner(entorno).ejecutar('u1', PERFIL, {}, modo='automatico')
    assert _estado(entorno) == 'postulacion_confirmada'
