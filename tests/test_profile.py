import io

import pytest

from autoapply.ai import AIError, AIProvider, AIRouter
from autoapply.profile import (CVError, calcular_anios, construir_perfil, estado_campos,
                               extraer_basico, extraer_texto)

CV = """Duvan Perilla
duvan@example.com | +57 300 123 4567 | linkedin.com/in/duvanperilla
Bogotá, Colombia

Perfil
Analista de datos con experiencia en operaciones.

Experiencia laboral
Analista de datos - Picap
2022-03 a actual
Reportes en SQL y Power BI.

Auxiliar - Tienda Uno
2020-01 a 2022-02

Educación
Ingeniería Industrial - Universidad Nacional (pregrado)

Habilidades
SQL, Python, Power BI

Idiomas
Inglés intermedio
"""


class IAFalsa(AIProvider):
    clave, modelo = 'ollama', 'falso'

    def __init__(self, respuesta):
        self._r = respuesta

    def configurado(self):
        return True

    def disponible(self):
        return True

    def generar(self, prompt, sistema='', json_mode=False, **kw):
        if isinstance(self._r, Exception):
            raise self._r
        return self._r


def router(resp):
    return AIRouter(proveedores={'ollama': IAFalsa(resp)})


def test_basico_lee_contacto_y_secciones():
    c = extraer_basico(CV)
    assert c['email'] == 'duvan@example.com'
    assert '300 123 4567' in c['telefono']
    assert c['nombre_completo'] == 'Duvan Perilla'
    assert c['habilidades'] == ['SQL', 'Python', 'Power BI']
    assert c['idiomas'][0]['idioma'].lower().startswith('ingl')
    assert c['educacion'] and c['educacion'][0]['nivel'] == 'pregrado'


def test_ia_alucinada_se_descarta():
    resp = ('{"nombre_completo":"Duvan Perilla","email":"duvan@example.com","habilidades":["SQL","Kubernetes"],'
            '"experiencia":[{"empresa":"Picap","cargo":"Analista de datos","desde":"2022-03","hasta":"actual"},'
            '{"empresa":"Google","cargo":"Director","desde":"2015-01","hasta":"2019-01"}]}')
    r = construir_perfil(CV, router=router(resp))
    p = r['perfil']
    assert [e['empresa'] for e in p['experiencia']] == ['Picap']
    assert 'Kubernetes' not in p['habilidades']
    assert any('Google' in d for d in r['descartes'])
    assert r['metodo']['tipo'] == 'ia'


def test_sin_ia_cae_a_lectura_basica_con_aviso():
    r = construir_perfil(CV, router=router(AIError('caído')))
    assert r['metodo']['tipo'] == 'basico'
    assert r['avisos'] and r['perfil']['email'] == 'duvan@example.com'


def test_respuesta_sin_json_no_rompe():
    r = construir_perfil(CV, router=router('lo siento no puedo'))
    assert r['metodo']['tipo'] == 'basico' and r['avisos']


def test_dato_inyectado_que_no_esta_en_el_cv_se_descarta():
    resp = '{"nombre_completo":"Duvan Perilla","email":"atacante@x.com","experiencia":[]}'
    r = construir_perfil(CV, router=router(resp))
    # el correo "atacante@x.com" no aparece en el documento: se descarta y
    # se usa el que sí se lee literalmente.
    assert r['perfil']['email'] == 'duvan@example.com'
    assert any('atacante' in d for d in r['descartes'])


def test_campos_verificados_no_se_pisan():
    previo = {'email': 'correo.confirmado@x.com', 'campos_confirmados': ['email']}
    r = construir_perfil(CV, existente=previo, usar_ia=False)
    assert r['perfil']['email'] == 'correo.confirmado@x.com'
    assert r['estado_campos']['email'] == 'verificado'


def test_estado_campos():
    e = estado_campos({'email': 'a@b.com', 'telefono': '', 'campos_confirmados': ['email']})
    assert e['email'] == 'verificado' and e['telefono'] == 'pendiente'
    assert estado_campos({'ciudad': 'Bogotá'})['ciudad'] == 'inferido'


def test_calcular_anios_une_solapes():
    exp = [{'desde': '2020-01', 'hasta': '2021-12'}, {'desde': '2021-06', 'hasta': '2022-12'}]
    assert calcular_anios(exp) == 3.0
    assert calcular_anios([{'desde': 'nunca', 'hasta': '?'}]) is None


def test_extraer_texto_txt_y_errores():
    assert 'Picap' in extraer_texto(CV.encode(), 'cv.txt')
    with pytest.raises(CVError):
        extraer_texto(b'x', 'cv.exe')
    with pytest.raises(CVError):
        extraer_texto(b'corto', 'cv.txt')
    with pytest.raises(CVError):
        extraer_texto(b'%PDF-1.4 basura' * 20, 'cv.pdf')


def test_extraer_texto_docx():
    import docx
    d = docx.Document()
    for linea in CV.split('\n'):
        d.add_paragraph(linea)
    buf = io.BytesIO()
    d.save(buf)
    assert 'Power BI' in extraer_texto(buf.getvalue(), 'cv.docx')
