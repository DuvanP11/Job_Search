"""Conectores ATS con respuestas simuladas (sin red) + casos de error."""
import pytest
import requests

from autoapply.adapters import obtener_adapter
from autoapply.adapters import ats_api
from autoapply.adapters.ats_api import FuenteError, a_iso, a_mensual, html_a_texto


class Resp:
    def __init__(self, datos=None, status=200, headers=None):
        self._d, self.status_code, self.headers = datos, status, headers or {}

    def json(self):
        if self._d is None:
            raise ValueError('no json')
        return self._d


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(ats_api.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(ats_api.AtsApiAdapter, 'intervalo_min', 0)


def falso_get(monkeypatch, respuestas):
    llamadas = []

    def get(url, params=None, **kw):
        llamadas.append((url, params))
        r = respuestas(url, params) if callable(respuestas) else respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(ats_api.requests, 'get', get)
    return llamadas


def test_greenhouse_mapea_y_limpia_html_escapado(monkeypatch):
    datos = {'jobs': [{'id': 1, 'title': 'Data Analyst', 'company_name': 'Acme',
                       'location': {'name': 'Bogotá'}, 'absolute_url': 'https://acme.com/j/1',
                       'first_published': '2026-09-03T13:30:34-04:00',
                       'content': '&lt;p&gt;Requisitos: &lt;b&gt;SQL&lt;/b&gt; y 3 años de experiencia&lt;/p&gt;'}]}
    llamadas = falso_get(monkeypatch, [Resp(datos)])
    r = obtener_adapter('greenhouse').buscar({'greenhouse_boards': ['acme']})
    assert llamadas[0][0].endswith('/boards/acme/jobs')
    o = r.ofertas[0]
    assert o['titulo'] == 'Data Analyst' and o['ubicacion'] == 'Bogotá'
    assert '<' not in o['descripcion'] and 'SQL' in o['descripcion']
    assert o['fecha_publicacion'] == '2026-09-03'
    assert o['pais'] == ''           # no se asume Colombia para fuentes internacionales
    assert o['anios_experiencia'] == 3
    assert o['application_url'] == 'https://job-boards.greenhouse.io/embed/job_app?for=acme&token=1'
    assert o['url'] == 'https://acme.com/j/1'


def test_lever_salario_modalidad_y_fecha_epoch(monkeypatch):
    datos = [{'id': 'abc', 'text': 'Backend Dev', 'hostedUrl': 'https://jobs.lever.co/x/abc',
              'applyUrl': 'https://jobs.lever.co/x/abc/apply', 'createdAt': 1786469891368,
              'categories': {'location': 'Remote'}, 'workplaceType': 'remote', 'country': 'CO',
              'descriptionPlain': 'Python', 'salaryRange': {'min': 120000, 'max': 180000,
                                                            'currency': 'USD', 'interval': 'per-year-salary'}}]
    falso_get(monkeypatch, [Resp(datos)])
    o = obtener_adapter('lever').buscar({'lever_companies': ['x']}).ofertas[0]
    assert o['modalidad'] == 'remota' and o['moneda'] == 'USD'
    assert o['salario_minimo'] == 10000.0 and o['salario_maximo'] == 15000.0
    assert o['application_url'].endswith('/apply')
    assert o['fecha_publicacion'].startswith('2026')


def test_ashby_omite_no_listadas_y_lee_salario(monkeypatch):
    comp = {'summaryComponents': [{'compensationType': 'Salary', 'interval': '1 YEAR',
                                   'currencyCode': 'EUR', 'minValue': 60000, 'maxValue': 90000}]}
    datos = {'jobs': [
        {'id': '1', 'title': 'PM', 'isListed': True, 'location': 'Madrid', 'jobUrl': 'https://j/1',
         'compensation': comp, 'descriptionPlain': 'x', 'isRemote': False, 'workplaceType': 'Hybrid',
         'address': {'postalAddress': {'addressCountry': 'Spain'}}},
        {'id': '2', 'title': 'Oculta', 'isListed': False, 'jobUrl': 'https://j/2'}]}
    falso_get(monkeypatch, [Resp(datos)])
    r = obtener_adapter('ashby').buscar({'ashby_boards': ['x']})
    assert [o['titulo'] for o in r.ofertas] == ['PM']
    o = r.ofertas[0]
    assert o['salario_minimo'] == 5000.0 and o['moneda'] == 'EUR' and o['modalidad'] == 'hibrida'


def test_smartrecruiters_solo_pide_detalle_de_cargos_que_coinciden(monkeypatch):
    lista = {'totalFound': 2, 'content': [
        {'id': '10', 'name': 'Data Engineer', 'releasedDate': '2026-10-28T00:00:00Z',
         'company': {'name': 'SR'}, 'location': {'city': 'Bogotá', 'country': 'co', 'remote': False}},
        {'id': '11', 'name': 'Chef', 'company': {'name': 'SR'}, 'location': {}}]}
    detalle = {'postingUrl': 'https://jobs.smartrecruiters.com/sr/10', 'applyUrl': 'https://jobs.smartrecruiters.com/sr/10?apply',
               'jobAd': {'sections': {'jobDescription': {'text': '<p>Construir pipelines</p>'}}}}

    def resp(url, params):
        return Resp(detalle) if url.endswith('/postings/10') else Resp(lista)
    llamadas = falso_get(monkeypatch, resp)
    r = obtener_adapter('smartrecruiters').buscar({'smartrecruiters_companies': ['sr'], 'cargos': ['data engineer']})
    urls = [u for u, _ in llamadas]
    assert any(u.endswith('/postings/10') for u in urls)
    assert not any(u.endswith('/postings/11') for u in urls)      # "Chef" no se consulta
    por_titulo = {o['titulo']: o for o in r.ofertas}
    assert 'pipelines' in por_titulo['Data Engineer']['descripcion']
    assert por_titulo['Chef']['descripcion'] == ''


def test_404_y_slug_invalido_no_tumban_a_los_demas(monkeypatch):
    def resp(url, params):
        return Resp({'jobs': [{'id': 1, 'title': 'Dev', 'absolute_url': 'https://x/1'}]}) \
            if '/boards/bueno/' in url else Resp(status=404)
    llamadas = falso_get(monkeypatch, resp)
    r = obtener_adapter('greenhouse').buscar({'greenhouse_boards': ['malo', '../etc/passwd', 'bueno']})
    assert len(r.ofertas) == 1
    assert len(r.errores) == 2
    assert not any('passwd' in u for u, _ in llamadas)           # el slug inválido nunca llega a la red


def test_reintenta_en_429_y_5xx_y_luego_funciona(monkeypatch):
    falso_get(monkeypatch, [Resp(status=429), Resp(status=503), Resp({'jobs': [{'id': 1, 'title': 'Dev', 'absolute_url': 'https://x/1'}]})])
    assert len(obtener_adapter('greenhouse').buscar({'greenhouse_boards': ['x']}).ofertas) == 1


def test_error_de_red_persistente_se_reporta(monkeypatch):
    falso_get(monkeypatch, [requests.exceptions.ConnectionError()] * 3)
    r = obtener_adapter('lever').buscar({'lever_companies': ['x']})
    assert r.ofertas == [] and 'sin conexión' in r.errores[0]


def test_respuesta_no_json(monkeypatch):
    falso_get(monkeypatch, [Resp(None)])
    r = obtener_adapter('ashby').buscar({'ashby_boards': ['x']})
    assert 'JSON' in r.errores[0]


def test_sin_configuracion_avisa(monkeypatch):
    r = obtener_adapter('lever').buscar({})
    assert r.ofertas == [] and r.advertencias


def test_duplicados_dentro_de_la_fuente(monkeypatch):
    j = {'id': 1, 'title': 'Dev', 'absolute_url': 'https://x/1'}
    falso_get(monkeypatch, [Resp({'jobs': [j, dict(j)]})])
    assert len(obtener_adapter('greenhouse').buscar({'greenhouse_boards': ['x']}).ofertas) == 1


def test_utilidades():
    assert a_iso('2026-09-03T13:30:34-04:00') == '2026-09-03' and a_iso('basura') is None and a_iso(None) is None
    assert a_mensual(120000, '1 YEAR') == 10000.0 and a_mensual(5000, 'month') == 5000.0
    assert a_mensual(50, 'hour') is None and a_mensual('x', 'year') is None
    assert html_a_texto('&lt;p&gt;Hola&lt;/p&gt;') == 'Hola'
