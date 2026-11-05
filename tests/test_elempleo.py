import json

import pytest
import requests

from autoapply.adapters import elempleo
from autoapply.adapters.elempleo import (ElEmpleoAdapter, parsear_detalle, parsear_pagina,
                                         parsear_salario)
from autoapply.jobs import aplicar_filtros


def tarjeta(i, titulo, empresa='ACME', ciudad='Bogotá', salario='$3 a $3,5 millones',
            contrato='Por obra o labor', modalidad='Remoto'):
    d = json.dumps({'id': i, 'title': titulo, 'company': empresa, 'location': ciudad, 'salary': salario})
    return f'''<div class="col-md-12 result-item mb-3">
      <div class="js-area-bind" data-ga4-offerdata='{d}' data-url="/co/ofertas-trabajo/{titulo.lower().replace(' ', '-')}-{i}">
        <h2><a class="js-offer-title" href="/x">{titulo}</a></h2>
        <span class="info-publish-date js-offer-date">Hace 2 días</span>
        <div class="small"><div>{salario}</div><div class="small-text">Salario</div></div>
        <div class="small"><div>{contrato}</div><div class="small-text">Tipo de contrato</div></div>
        <div class="small"><div>{modalidad}</div><div class="small-text">Modalidad laboral</div></div>
      </div></div>'''


PAGINA = '<html><body>' + tarjeta(1, 'Analista de datos') + tarjeta(
    2, 'Analista BI', empresa='', salario='A convenir', contrato='Término indefinido', modalidad='Presencial') + \
    '<div class="result-item">sin json</div></body></html>'


def test_parsear_pagina():
    of = parsear_pagina(PAGINA)
    assert len(of) == 2                      # la tarjeta sin JSON se ignora
    a, b = of
    assert a['titulo'] == 'Analista de datos' and a['empresa'] == 'ACME' and a['ciudad'] == 'Bogotá'
    assert (a['salario_minimo'], a['salario_maximo']) == (3_000_000, 3_500_000)
    assert a['tipo_contrato'] == 'obra_labor' and a['modalidad'] == 'remota'
    assert a['url'] == 'https://www.elempleo.com/co/ofertas-trabajo/analista-de-datos-1'
    assert a['fecha_publicacion'] == 'Hace 2 días'
    assert b['empresa'] == 'Empresa confidencial' and b['salario_minimo'] is None
    assert b['tipo_contrato'] == 'indefinido' and b['modalidad'] == 'presencial'


@pytest.mark.parametrize('texto,esperado', [
    ('$3 a $3,5 millones', (3_000_000, 3_500_000)),
    ('$1.500.000 a $2.000.000', (1_500_000, 2_000_000)),
    ('$4 millones', (4_000_000, 4_000_000)),
    ('A convenir', (None, None)),
    ('', (None, None)),
    ('Hasta 50', (None, None)),
])
def test_parsear_salario(texto, esperado):
    assert parsear_salario(texto) == esperado


def test_parsear_detalle_json_ld():
    html = '''<script type="application/ld+json">{"@type":"JobPosting","description":"<p>Pedimos 2 años de experiencia en SQL</p>",
      "datePosted":"2026-9-30","validThrough":"2026-11-29","jobLocationType":"TELECOMMUTE"}</script>'''
    d = parsear_detalle(html)
    assert d['descripcion'] == 'Pedimos 2 años de experiencia en SQL'
    assert d['vigente_hasta'] == '2026-11-29' and d['fecha_publicacion'] == '2026-09-30'
    assert d['modalidad'] == 'remota'
    assert parsear_detalle('<html></html>') == {}
    assert parsear_detalle('<script type="application/ld+json">{roto</script>') == {}


def test_url_filtra_por_ciudad_y_cargo():
    a = ElEmpleoAdapter()
    assert a._url('Analista de datos', 'Bogotá', 1).endswith('/bogota/trabajo-analista-de-datos')
    assert a._url('Analista de datos', '', 2).endswith('/trabajo-analista-de-datos?page=2')


@pytest.fixture
def sin_pausas(monkeypatch):
    monkeypatch.setattr(elempleo.time, 'sleep', lambda *_: None)


def _resp(texto='', status=200):
    r = requests.Response()
    r.status_code = status
    r._content = texto.encode()
    return r


def test_buscar_trae_detalle_solo_de_titulos_que_coinciden(monkeypatch, sin_pausas):
    detalle = ('<script type="application/ld+json">{"@type":"JobPosting","description":"Requiere 3 años de experiencia",'
               '"validThrough":"2099-01-01"}</script>')
    pedidas = []

    def get(url, **kw):
        pedidas.append(url)
        if '/co/ofertas-trabajo/' in url:
            return _resp(detalle)
        return _resp(PAGINA) if 'page=' not in url else _resp('<html></html>')
    monkeypatch.setattr(elempleo.requests, 'get', get)
    r = ElEmpleoAdapter().buscar({'cargos': ['analista de datos'], 'ciudad': 'Bogotá'})
    assert len(r.ofertas) == 2
    detalles = [u for u in pedidas if '/co/ofertas-trabajo/' in u]
    assert len(detalles) == 1 and 'analista-de-datos-1' in detalles[0]   # "Analista BI" no coincide
    o = r.ofertas[0]
    assert o['anios_experiencia'] == 3 and o['vigente_hasta'] == '2099-01-01'


def test_bloqueo_403_se_reporta_y_no_reintenta(monkeypatch, sin_pausas):
    llamadas = []
    monkeypatch.setattr(elempleo.requests, 'get', lambda u, **k: (llamadas.append(u), _resp(status=403))[1])
    r = ElEmpleoAdapter().buscar({'cargos': ['a b', 'c d']})
    assert r.ofertas == [] and 'bloque' in r.errores[0]
    assert len(llamadas) == 2                     # una por cargo, sin reintentos


def test_cero_resultados_es_advertencia_no_silencio(monkeypatch, sin_pausas):
    monkeypatch.setattr(elempleo.requests, 'get', lambda u, **k: _resp('<html></html>'))
    r = ElEmpleoAdapter().buscar({'cargos': ['xyz']})
    assert r.ofertas == [] and r.errores == [] and '0 resultados' in r.advertencias[0]


def test_oferta_vencida_se_descarta():
    perfil = {'config': {'portales': ['elempleo']}}
    base = {'portal': 'elempleo', 'titulo': 'Analista', 'empresa': 'X', 'descripcion': 'd'}
    assert aplicar_filtros({**base, 'vigente_hasta': '2020-01-01'}, perfil, {})['pasa'] is False
    assert aplicar_filtros({**base, 'vigente_hasta': '2099-01-01'}, perfil, {})['pasa'] is True
