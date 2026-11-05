from datetime import datetime, timedelta, timezone

import pytest

from autoapply.cola import ColaTrabajo
from autoapply.storage import Store


@pytest.fixture
def cola(tmp_path):
    return ColaTrabajo(Store(data_dir=str(tmp_path), database_url=''))


def test_no_duplica_tareas_activas(cola):
    a, nueva = cola.encolar('u', 'j1', 'enviar')
    b, nueva2 = cola.encolar('u', 'j1', 'enviar')
    assert nueva and not nueva2 and a['id'] == b['id']
    assert cola.encolar('u', 'j1', 'preparar')[1] is True       # otra acción sí
    with pytest.raises(ValueError):
        cola.encolar('u', 'j1', 'inventada')


def test_reclamar_una_sola_vez(cola):
    cola.encolar('u', 'j1', 'enviar')
    owner, t = cola.reclamar('w1')
    assert owner == 'u' and t['estado'] == 'en_curso' and t['intentos'] == 1 and t['worker'] == 'w1'
    assert cola.reclamar('w2') is None                           # nadie más la toma mientras dura el lease


def test_recupera_tarea_de_worker_caido(cola):
    cola.encolar('u', 'j1', 'enviar')
    ahora = datetime.now(timezone.utc)
    cola.reclamar('w1', ahora=ahora, lease_seg=60)
    assert cola.reclamar('w2', ahora=ahora + timedelta(seconds=30)) is None
    owner, t = cola.reclamar('w2', ahora=ahora + timedelta(seconds=61))
    assert t['worker'] == 'w2' and t['intentos'] == 2 and 'interrupción' in t['ultimo_error']


def test_tarea_que_mata_al_worker_siempre_termina_fallida(cola):
    cola.encolar('u', 'j1', 'enviar')
    ahora = datetime.now(timezone.utc)
    for i in range(8):
        cola.reclamar(f'w{i}', ahora=ahora + timedelta(hours=i), lease_seg=60)
    assert cola.listar('u')[0]['estado'] == 'fallida'


def test_reintento_con_espera_exponencial_y_limite(cola):
    cola.encolar('u', 'j1', 'enviar')
    base = datetime.now(timezone.utc)
    esperas = []
    for _ in range(3):
        owner, t = cola.reclamar('w', ahora=base + timedelta(days=1))
        cola.fallar(owner, t['id'], 'timeout', ahora=base)
        t = cola.listar('u')[0]
        if t['estado'] == 'pendiente':
            esperas.append((datetime.fromisoformat(t['no_antes_de']) - base).total_seconds())
    assert esperas == [60, 120]                                  # 3er fallo = agotó intentos
    assert t['estado'] == 'fallida' and t['ultimo_error'] == 'timeout'


def test_no_reclama_antes_de_tiempo(cola):
    cola.encolar('u', 'j1', 'enviar')
    owner, t = cola.reclamar('w')
    cola.fallar(owner, t['id'], 'x')
    assert cola.reclamar('w') is None                            # aún en espera


def test_completar_cancelar_y_requiere_usuario(cola):
    cola.encolar('u', 'j1', 'enviar')
    cola.encolar('u', 'j2', 'enviar')
    owner, t = cola.reclamar('w')
    cola.requiere_usuario(owner, t['id'], 'CAPTCHA')
    assert cola.listar('u', 'requiere_usuario')[0]['resultado']['motivo'] == 'CAPTCHA'
    pendiente = cola.listar('u', 'pendiente')[0]
    cola.cancelar('u', pendiente['id'])
    assert cola.reclamar('w') is None
    # una tarea terminada se puede volver a encolar
    assert cola.encolar('u', 'j1', 'enviar')[1] is True
