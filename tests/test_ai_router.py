import pytest

from autoapply.ai import AIError, AIProvider, AIRouter
from autoapply.ai.base import extraer_json


class Falso(AIProvider):
    def __init__(self, clave, respuesta=None, error=None, conf=True):
        self.clave, self.modelo, self._r, self._e, self._c = clave, 'm', respuesta, error, conf

    def configurado(self):
        return self._c

    def disponible(self):
        return self._c

    def generar(self, prompt, sistema='', json_mode=False, **kw):
        if self._e:
            raise AIError(self._e)
        return self._r


def test_respaldo_cuando_el_primero_falla():
    r = AIRouter(proveedores={'ollama': Falso('ollama', error='caído'),
                              'openrouter': Falso('openrouter', respuesta='hola')})
    out = r.generar('matching', 'x')
    assert out['proveedor'] == 'openrouter' and out['texto'] == 'hola'


def test_sin_proveedores_lanza_error_no_inventa():
    r = AIRouter(proveedores={k: Falso(k, conf=False) for k in ('ollama', 'openrouter', 'openai', 'anthropic')})
    assert r.hay_ia('matching') is False
    with pytest.raises(AIError):
        r.generar('matching', 'x')


def test_tarea_desconocida():
    with pytest.raises(ValueError):
        AIRouter().generar('inexistente', 'x')


def test_config_por_tarea_prioriza_el_elegido():
    r = AIRouter(config={'documentos': [{'proveedor': 'openai'}]},
                 proveedores={'ollama': Falso('ollama', respuesta='local'), 'openai': Falso('openai', respuesta='nube')})
    assert r.generar('documentos', 'x')['proveedor'] == 'openai'
    assert r.generar('matching', 'x')['proveedor'] == 'ollama'


@pytest.mark.parametrize('texto', ['{"a": 1}', '```json\n{"a": 1}\n```', 'Claro: {"a": 1} listo'])
def test_extraer_json(texto):
    assert extraer_json(texto) == {'a': 1}


def test_extraer_json_invalido():
    with pytest.raises(AIError):
        extraer_json('sin json')
