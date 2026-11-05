from autoapply.matching import evaluar_compatibilidad

PERFIL = {'config': {'cargos': ['Analista de datos'], 'portales': ['computrabajo'],
                     'modalidades': ['remota', 'hibrida', 'presencial'], 'salario_minimo': 3000000,
                     'moneda': 'COP', 'fecha_publicacion_dias': 0}}
CAND = {'anios_experiencia': 4, 'habilidades': ['SQL', 'Python', 'Power BI'],
        'educacion': [{'titulo': 'Ingeniería Industrial', 'nivel': 'pregrado'}]}


def job(**kw):
    base = {'portal': 'computrabajo', 'titulo': 'Analista de datos', 'empresa': 'Acme',
            'descripcion': 'Buscamos analista con SQL, Python y Power BI.', 'modalidad': 'remota'}
    base.update(kw)
    return base


def estados(r):
    return {x['categoria']: x['estado'] for x in r['requisitos']}


def test_titulo_obligatorio_distinto_excluye_aunque_el_puntaje_sea_alto():
    r = evaluar_compatibilidad(job(descripcion='Analista con SQL, Python y Power BI. '
                                   'Título profesional en Medicina.'), PERFIL, CAND)
    assert r['score'] >= 70
    assert r['apto'] is False
    assert any(g['categoria'] == 'titulo' for g in r['excluyentes'])


def test_titulo_con_afines_no_excluye():
    r = evaluar_compatibilidad(job(descripcion='Analista con SQL, Python y Power BI. '
                                   'Título profesional en Medicina o afines.'), PERFIL, CAND)
    assert estados(r)['titulo'] == 'parcial'
    assert r['apto'] is True


def test_titulo_relacionado_cumple():
    r = evaluar_compatibilidad(job(descripcion='SQL y Python. Profesional en Ingeniería Industrial.'),
                               PERFIL, CAND)
    assert estados(r)['titulo'] == 'cumplido'


def test_experiencia_insuficiente_es_excluyente():
    r = evaluar_compatibilidad(job(anios_experiencia=8), PERFIL, CAND)
    assert estados(r)['experiencia'] == 'no_cumplido'
    assert r['apto'] is False


def test_datos_desconocidos_no_penalizan_pero_bajan_confianza():
    r = evaluar_compatibilidad(job(), PERFIL, CAND)
    assert estados(r)['salario'] == 'desconocido'
    assert r['confianza'] < 100
    assert r['apto'] is True


def test_explicacion_presente_y_sin_promesa_de_contratacion():
    r = evaluar_compatibilidad(job(), PERFIL, CAND)
    assert r['explicacion'][-1].endswith('no es una probabilidad de contratación.') or 'indicador' in r['explicacion'][-1]
