"""Motor de formularios contra ATS simulados en local (Chromium real)."""
import pytest

from autoapply.browser import CONFIRMADO, DRY_RUN, ENVIADO_SIN_CONFIRMACION, ERROR, REQUIERE_USUARIO
from autoapply.browser.base import SolicitudAplicacion
from autoapply.browser.formulario import GreenhouseAplicador, clasificar, datos_verificados
from tests.servidor_ats import Servidor
from tests.test_documents import CAND

pytest.importorskip('playwright')

VERIFICADO = {**CAND, 'campos_confirmados': ['nombre_completo', 'email', 'telefono', 'ciudad', 'linkedin']}


@pytest.fixture(scope='module')
def servidor():
    with Servidor() as s:
        yield s


@pytest.fixture(autouse=True)
def hay_chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch(headless=True).close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f'Chromium no disponible: {exc}')


@pytest.fixture
def archivos(tmp_path):
    cv, carta = tmp_path / 'cv.pdf', tmp_path / 'carta.pdf'
    cv.write_bytes(b'%PDF-1.4 cv')
    carta.write_bytes(b'%PDF-1.4 carta')
    return {'cv': str(cv), 'carta': str(carta)}


def solicitud(servidor, variante, archivos, tmp_path, real=False, candidato=None, **kw):
    return SolicitudAplicacion(
        job={'portal': 'greenhouse', 'application_url': f'{servidor.base}/form/{variante}'},
        candidato=candidato or VERIFICADO, archivos=archivos, carta_texto='Mi carta de prueba',
        enviar_real=real, carpeta_evidencia=str(tmp_path / 'ev'), **kw)


def aplicar(s):
    return GreenhouseAplicador(permitir_local=True).aplicar(s)


def test_dry_run_rellena_y_valida_sin_enviar(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'ok', archivos, tmp_path))
    assert r.estado == DRY_RUN and len(servidor.posts) == n                     # NO se envió nada
    assert {'CV adjunto', 'email', 'telefono'} <= set(r.evidencia['campos_llenados'])
    import os
    assert all(os.path.exists(c) for c in r.evidencia['capturas'] if c)


def test_envio_real_confirmado_por_url_y_texto(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'ok', archivos, tmp_path, real=True))
    assert r.estado == CONFIRMADO and 'confirmación' in r.evidencia['senal']
    assert len(servidor.posts) == n + 1
    cuerpo = servidor.posts[-1][1]
    assert b'duvan@example.com' in cuerpo and b'filename="cv.pdf"' in cuerpo and b'Mi carta de prueba' in cuerpo
    assert b'name="gender"' in cuerpo and b'Male' not in cuerpo and b'Female' not in cuerpo   # EEO opcional: sin responder


def test_sin_senal_de_confirmacion_no_se_marca_confirmado(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'noconfirm', archivos, tmp_path, real=True))
    assert r.estado == ENVIADO_SIN_CONFIRMACION and 'Verifica' in r.motivo


def test_el_portal_rechaza_el_formulario(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'error', archivos, tmp_path, real=True))
    assert r.estado == ERROR and 'Email address is not valid' in r.motivo


def test_captcha_antes_de_rellenar_detiene_todo(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'captcha', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'CAPTCHA' in r.motivo and len(servidor.posts) == n


def test_captcha_despues_de_enviar_no_se_da_por_enviado(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'captcha_after', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'NO se completó' in r.motivo


def test_login_requerido(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'login', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'iniciar sesión' in r.motivo


def test_pregunta_legal_obligatoria_nunca_se_responde(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'legal', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'legally authorized' in r.motivo and 'sensible' in r.motivo
    assert len(servidor.posts) == n


def test_consentimiento_lo_acepta_el_usuario(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'consent', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'privacy' in r.motivo


def test_pregunta_abierta_desconocida_se_detiene(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'extra', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'Why do you want' in r.motivo


def test_pregunta_abierta_con_borrador_de_ia_solo_si_esta_permitido(servidor, archivos, tmp_path):
    resp = lambda q: {'estado': 'borrador', 'respuesta': 'Porque me gusta el reto.'}   # noqa: E731
    r = aplicar(solicitud(servidor, 'extra', archivos, tmp_path, responder=resp, permitir_respuestas_ia=False))
    assert r.estado == REQUIERE_USUARIO
    r = aplicar(solicitud(servidor, 'extra', archivos, tmp_path, real=True, responder=resp, permitir_respuestas_ia=True))
    assert r.estado == CONFIRMADO and b'Porque me gusta el reto.' in servidor.posts[-1][1]
    # si la IA no puede responder con verdad, se detiene
    sin = lambda q: {'estado': 'requiere_usuario', 'respuesta': ''}                      # noqa: E731
    r = aplicar(solicitud(servidor, 'extra', archivos, tmp_path, responder=sin, permitir_respuestas_ia=True))
    assert r.estado == REQUIERE_USUARIO


def test_respuesta_guardada_del_usuario(servidor, archivos, tmp_path):
    cand = {**VERIFICADO, 'respuestas_guardadas': {'why do you want': 'Por la misión del equipo.'}}
    r = aplicar(solicitud(servidor, 'extra', archivos, tmp_path, real=True, candidato=cand))
    assert r.estado == CONFIRMADO and b'Por la misi' in servidor.posts[-1][1]


def test_exige_datos_de_contacto_verificados(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'ok', archivos, tmp_path, real=True, candidato={**CAND, 'campos_confirmados': ['email']}))
    assert r.estado == REQUIERE_USUARIO and 'Confirma' in r.motivo and 'teléfono' in r.campos_pendientes
    assert len(servidor.posts) == n


def test_bloquea_urls_locales_si_no_es_modo_prueba(servidor, archivos, tmp_path):
    r = GreenhouseAplicador().aplicar(solicitud(servidor, 'ok', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'no permitida' in r.motivo


def test_url_sin_formulario(servidor, archivos, tmp_path):
    s = solicitud(servidor, 'ok', archivos, tmp_path)
    s.job['application_url'] = f'{servidor.base}/procesado'
    assert aplicar(s).estado == REQUIERE_USUARIO


def test_clasificacion_de_campos():
    c = lambda label, tag='input', t='text', name='': dict(label=label, tag=tag, type=t, name=name, id='')   # noqa: E731
    assert clasificar(c('First Name *')) == 'nombre' and clasificar(c('Last Name')) == 'apellido'
    assert clasificar(c('Correo electrónico')) == 'email' and clasificar(c('Teléfono celular')) == 'telefono'
    assert clasificar(c('Resume/CV', t='file')) == 'archivo_cv' and clasificar(c('Cover letter', t='file')) == 'archivo_carta'
    assert clasificar(c('Cover Letter', 'textarea')) == 'texto_carta'
    assert clasificar(c('Favorite color')) == ''


def test_datos_verificados_solo_incluye_lo_confirmado():
    d = datos_verificados({**CAND, 'campos_confirmados': ['email']})
    assert d == {'email': 'duvan@example.com'}
    d = datos_verificados({**CAND, 'campos_confirmados': ['email', 'experiencia']})
    assert d['empresa_actual'] == 'Picap' and d['cargo_actual'] == 'Analista de datos'


def test_clasifica_empleador_y_cargo_actual():
    c = lambda label: dict(label=label, tag='input', type='text', name='', id='')                  # noqa: E731
    assert clasificar(c('Who is your current or previous employer?*')) == 'empresa_actual'
    assert clasificar(c('What is your current or previous job title?*')) == 'cargo_actual'


def test_pregunta_de_autorizacion_con_la_palabra_location_no_se_contesta_con_la_ciudad(servidor, archivos, tmp_path):
    """Bug real encontrado en un formulario de Greenhouse: se rellenaba la ciudad en una pregunta legal."""
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'authwork', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'authorized to work' in r.motivo and 'sensible' in r.motivo
    assert len(servidor.posts) == n
    assert 'ciudad' not in r.evidencia.get('campos_llenados', [])


def test_combobox_elige_una_opcion_real_y_se_ignora_el_input_sombra(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'combo', archivos, tmp_path, real=True))
    assert r.estado == CONFIRMADO
    assert b'Bogot' in servidor.posts[-1][1] and b'Medell' not in servidor.posts[-1][1]
    assert 'ciudad' in r.evidencia['campos_llenados']


def test_combobox_obligatorio_desconocido_se_detiene(servidor, archivos, tmp_path):
    r = aplicar(solicitud(servidor, 'combo_vacio', archivos, tmp_path, real=True))
    assert r.estado == REQUIERE_USUARIO and 'Country' in r.motivo


def test_combobox_sin_opciones_no_se_da_por_llenado(servidor, archivos, tmp_path):
    cand = {**VERIFICADO, 'ciudad': 'Ciudad Inexistente', 'campos_confirmados': VERIFICADO['campos_confirmados']}
    r = aplicar(solicitud(servidor, 'combo', archivos, tmp_path, real=True, candidato=cand))
    assert r.estado == REQUIERE_USUARIO and 'elige la opción' in r.motivo


def test_si_la_validacion_del_navegador_frena_el_envio_no_se_dice_enviado(servidor, archivos, tmp_path):
    n = len(servidor.posts)
    r = aplicar(solicitud(servidor, 'combo_invalido', archivos, tmp_path, real=True))
    assert r.estado == ERROR and 'no salió' in r.motivo and len(servidor.posts) == n
