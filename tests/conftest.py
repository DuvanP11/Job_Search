import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _csrf_off_por_defecto():
    """Las pruebas de rutas no envían token; test_seguridad.py lo activa para verificar el CSRF."""
    import app as modulo
    modulo.app.config['AUTOAPPLY_CSRF_DISABLED'] = True
    yield
    modulo.app.config['AUTOAPPLY_CSRF_DISABLED'] = True
