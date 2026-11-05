import io

import pytest

from autoapply.ai import AIError, AIProvider, AIRouter
from autoapply.documents import (carta_a_docx, carta_a_pdf, construir_datos_cv, cv_a_docx, cv_a_pdf,
                                 generar_carta, idioma_de, responder_pregunta, validar_texto_generado)
from autoapply.security import es_pregunta_sensible

CAND = {
    'nombre_completo': 'Duvan Perilla', 'email': 'duvan@example.com', 'telefono': '3001234567',
    'ciudad': 'Bogotá', 'titular': 'Analista de datos', 'resumen': 'Analista con experiencia en operaciones.',
    'anios_experiencia': 4, 'habilidades': ['Excel', 'SQL', 'Power BI', 'Python'],
    'experiencia': [{'cargo': 'Analista de datos', 'empresa': 'Picap', 'desde': '2022-03', 'hasta': 'actual',
                     'responsabilidades': ['Atención de PQRS', 'Reportes en SQL y Power BI para operaciones'],
                     'logros': ['Automaticé reportes con Python']}],
    'educacion': [{'titulo': 'Ingeniería Industrial', 'institucion': 'Universidad Nacional', 'nivel': 'pregrado'}],
    'idiomas': [{'idioma': 'Inglés', 'nivel': 'intermedio'}], 'campos_confirmados': ['email'],
}
JOB = {'titulo': 'Analista de datos', 'empresa': 'Acme', 'descripcion': 'Buscamos analista con SQL y Power BI para reportes.'}


class IA(AIProvider):
    clave, modelo = 'ollama', 'falso'

    def __init__(self, resp):
        self.resp, self.llamadas = resp, 0

    def configurado(self):
        return True

    def disponible(self):
        return True

    def generar(self, prompt, sistema='', json_mode=False, **kw):
        self.llamadas += 1
        if isinstance(self.resp, Exception):
            raise self.resp
        return self.resp


def router(resp):
    ia = IA(resp)
    return AIRouter(proveedores={'ollama': ia}), ia


def test_cv_prioriza_lo_relevante_y_no_agrega_habilidades():
    r = construir_datos_cv(CAND, JOB, usar_ia=False)
    d = r['datos']
    assert d['habilidades_tecnicas'][:2] == ['SQL', 'Power BI']          # las que pide la oferta, primero
    assert set(d['habilidades_tecnicas']) == set(CAND['habilidades'])    # ninguna añadida ni quitada
    assert d['experiencia'][0]['logros'][0].startswith('Reportes en SQL')
    assert r['habilidades_coincidentes'] == ['SQL', 'Power BI']
    assert d['resumen'] == CAND['resumen'] and r['generado_con'] == 'perfil'


def test_advierte_datos_sin_confirmar():
    r = construir_datos_cv(CAND, JOB, usar_ia=False)
    aviso = next(a for a in r['advertencias'] if 'sin confirmar' in a)
    assert 'email' not in aviso.split(': ', 1)[1] and 'telefono' in aviso   # el email sí está verificado


def test_resumen_ia_valido_se_acepta():
    rt, _ = router('Analista de datos con 4 años de experiencia en SQL y Power BI.')
    r = construir_datos_cv(CAND, JOB, router=rt)
    assert r['generado_con'].startswith('ia:') and '4 años' in r['datos']['resumen']


def test_resumen_ia_que_inventa_se_rechaza():
    rt, _ = router('Director en Google con 15 años liderando equipos de datos.')
    r = construir_datos_cv(CAND, JOB, router=rt)
    assert r['datos']['resumen'] == CAND['resumen']
    assert any('añadió datos' in a for a in r['advertencias'])


def test_sin_ia_usa_plantilla_con_hechos_reales():
    rt, _ = router(AIError('caído'))
    c = construir_datos_cv({**CAND, 'resumen': ''}, JOB, router=rt)
    assert 'Analista de datos' in c['datos']['resumen'] and '4 años' in c['datos']['resumen']
    carta = generar_carta(CAND, JOB, ['SQL', 'Power BI'], router=rt)
    assert carta['generado_con'] == 'plantilla'
    assert 'Acme' in carta['texto'] and 'SQL, Power BI' in carta['texto'] and 'Picap' in carta['texto']
    assert carta['texto'].rstrip().endswith('Duvan Perilla')


def test_carta_ia_que_inventa_cae_a_plantilla():
    rt, _ = router('Trabajé 10 años en Microsoft y dupliqué las ventas.')
    carta = generar_carta(CAND, JOB, ['SQL'], router=rt)
    assert carta['generado_con'] == 'plantilla' and carta['advertencias']
    assert 'Microsoft' not in carta['texto']


def test_carta_en_ingles_si_la_oferta_esta_en_ingles():
    job = {'titulo': 'Data Analyst', 'empresa': 'Globex', 'descripcion': 'We are looking for an analyst with SQL and the ability to work with our team.'}
    assert idioma_de(job['descripcion']) == 'en'
    c = generar_carta(CAND, job, ['SQL'], usar_ia=False)
    assert c['idioma'] == 'en' and c['texto'].startswith('Dear Globex Hiring Team')


def test_empresa_no_especificada_no_se_escribe_en_la_carta():
    c = generar_carta(CAND, {**JOB, 'empresa': 'No especificada'}, usar_ia=False)
    assert 'No especificada' not in c['texto'] and 'Talento Humano' in c['texto']


@pytest.mark.parametrize('pregunta', [
    '¿Tiene antecedentes penales?', 'Do you require visa sponsorship?', 'Indique su género', 'Are you legally authorized to work?',
    '¿Tiene alguna discapacidad?', 'Fecha de nacimiento', 'Declaro bajo juramento que la información es veraz',
    'Estado de salud', 'Número de cédula',
])
def test_preguntas_sensibles_nunca_llegan_a_la_ia(pregunta):
    assert es_pregunta_sensible(pregunta)
    rt, ia = router('respuesta')
    r = responder_pregunta(pregunta, CAND, JOB, router=rt)
    assert r['estado'] == 'requiere_usuario' and r['respuesta'] == '' and ia.llamadas == 0


@pytest.mark.parametrize('pregunta', ['¿Por qué quieres trabajar con nosotros?', 'Describe tu experiencia con SQL'])
def test_preguntas_normales_no_son_sensibles(pregunta):
    assert not es_pregunta_sensible(pregunta)


def test_respuesta_abierta_valida_es_borrador():
    rt, ia = router('He usado SQL y Power BI en Picap para reportes de operaciones.')
    r = responder_pregunta('Describe tu experiencia con SQL', CAND, JOB, router=rt)
    assert r['estado'] == 'borrador' and 'SQL' in r['respuesta'] and ia.llamadas == 1


def test_respuesta_NO_SE_o_inventada_requiere_usuario():
    assert responder_pregunta('¿Experiencia en SAP?', CAND, JOB, router=router('NO_SE')[0])['estado'] == 'requiere_usuario'
    inventada = responder_pregunta('¿Experiencia en SAP?', CAND, JOB, router=router('Fui gerente de SAP en Oracle 8 años.')[0])
    assert inventada['estado'] == 'requiere_usuario' and 'Oracle' in inventada['motivo']
    assert responder_pregunta('¿Experiencia?', CAND, JOB, router=router(AIError('x'))[0])['estado'] == 'requiere_usuario'


def test_validador():
    corpus = 'Picap 4 años SQL Acme'
    assert validar_texto_generado('Trabajé en Picap con SQL durante 4 años.', corpus) == []
    assert validar_texto_generado('Trabajé en Google durante 9 años.', corpus) == ['9', 'Google']
    assert validar_texto_generado('Estimado equipo, gracias.', corpus) == []


def test_exporta_docx_y_pdf_legibles():
    d = construir_datos_cv(CAND, JOB, usar_ia=False)['datos']
    import docx
    assert 'duvan perilla' in '\n'.join(p.text for p in docx.Document(io.BytesIO(cv_a_docx(d))).paragraphs).lower()
    pdf = cv_a_pdf(d)
    assert pdf.startswith(b'%PDF')
    import PyPDF2
    texto = '\n'.join(p.extract_text() for p in PyPDF2.PdfReader(io.BytesIO(pdf)).pages)
    assert 'DUVAN PERILLA' in texto and 'Power BI' in texto and 'Ingeniería Industrial' in texto   # tildes intactas
    carta = generar_carta(CAND, JOB, ['SQL'], usar_ia=False)['texto']
    assert carta_a_pdf(carta).startswith(b'%PDF')
    assert 'Acme' in '\n'.join(p.text for p in docx.Document(io.BytesIO(carta_a_docx(carta))).paragraphs)


def test_pdf_con_caracteres_raros_no_revienta():
    d = construir_datos_cv({**CAND, 'resumen': 'Líder 😀 & <b>negrita</b> – “comillas”'}, JOB, usar_ia=False)['datos']
    assert cv_a_pdf(d).startswith(b'%PDF')


@pytest.mark.parametrize('texto', ['Estimado/a [Nombre del destinatario],', 'Hola {empresa}', 'Fecha: <fecha>', 'Atte. XXX'])
def test_marcadores_sin_rellenar_son_sospechosos(texto):
    assert validar_texto_generado(texto, 'Picap') != []


def test_carta_con_marcador_cae_a_plantilla():
    rt, _ = router('Estimado/a [Nombre del destinatario], me postulo con SQL y Power BI en Picap.')
    c = generar_carta(CAND, JOB, ['SQL'], router=rt)
    assert c['generado_con'] == 'plantilla' and '[' not in c['texto']
