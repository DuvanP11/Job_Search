#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROXY AUTENTICADO PARA OLLAMA

Ollama no tiene autenticación: quien alcance su puerto puede generar texto con
tu equipo, listar tus modelos o borrarlos. Publicarlo tal cual en internet no
es una opción.

Este proxy se pone delante: exige un token en la cabecera Authorization, solo
deja pasar los dos endpoints que la aplicación necesita y reenvía el resto a
Ollama en localhost.

Uso:

    export OLLAMA_TOKEN="una-cadena-larga-y-aleatoria"
    python3 scripts/ollama_proxy.py

Y en otra terminal, para publicarlo:

    cloudflared tunnel --url http://localhost:11435

La URL que imprime cloudflared es la que se configura en OLLAMA_URL.
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger('ollama-proxy')

PUERTO = int(os.getenv('PROXY_PORT', '11435'))
OLLAMA = os.getenv('OLLAMA_URL', 'http://localhost:11434')
TOKEN = os.getenv('OLLAMA_TOKEN', '')

# Solo lo que necesita el asistente de CV. Deja fuera /api/delete, /api/pull,
# /api/create y demás endpoints que modifican el equipo.
RUTAS_PERMITIDAS = {
    'GET': ('/api/tags', '/health'),
    'POST': ('/api/generate', '/api/chat', '/api/embeddings'),
}

TIMEOUT_SEGUNDOS = 300  # generar un CV completo puede tardar minutos


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):  # noqa: A002 - firma de la clase base
        logger.info('%s - %s', self.address_string(), format % args)

    def _responder(self, codigo, cuerpo, tipo='application/json'):
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _autorizado(self):
        """El token viaja en Authorization: Bearer <token>."""
        cabecera = self.headers.get('Authorization', '')
        enviado = cabecera[7:].strip() if cabecera.lower().startswith('bearer ') else ''
        # Comparación de longitud constante: evita filtrar el token por tiempos
        import hmac
        return hmac.compare_digest(enviado, TOKEN)

    def _ruta_permitida(self, metodo):
        ruta = self.path.split('?')[0]
        return ruta in RUTAS_PERMITIDAS.get(metodo, ())

    def _reenviar(self, metodo):
        if not self._autorizado():
            logger.warning('Petición rechazada por token inválido: %s %s', metodo, self.path)
            self._responder(401, {'error': 'Token inválido o ausente'})
            return

        if not self._ruta_permitida(metodo):
            logger.warning('Ruta no permitida: %s %s', metodo, self.path)
            self._responder(403, {'error': f'Ruta no permitida: {self.path}'})
            return

        longitud = int(self.headers.get('Content-Length') or 0)
        cuerpo = self.rfile.read(longitud) if longitud else None

        peticion = urllib.request.Request(
            f'{OLLAMA}{self.path}',
            data=cuerpo,
            method=metodo,
            headers={'Content-Type': 'application/json'},
        )

        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
                self._responder(respuesta.status, respuesta.read())
        except urllib.error.HTTPError as e:
            self._responder(e.code, e.read())
        except urllib.error.URLError as e:
            logger.error('Ollama no responde: %s', e)
            self._responder(502, {'error': f'Ollama no responde: {e.reason}'})
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error('Error inesperado: %s', e)
            self._responder(500, {'error': str(e)})

    def do_GET(self):     # noqa: N802 - nombre exigido por BaseHTTPRequestHandler
        self._reenviar('GET')

    def do_POST(self):    # noqa: N802
        self._reenviar('POST')


def main():
    if not TOKEN:
        print('ERROR: falta OLLAMA_TOKEN.\n')
        print('Genera uno y vuelve a intentarlo:\n')
        print('  export OLLAMA_TOKEN="$(python3 -c \'import secrets; print(secrets.token_hex(32))\')"')
        print('  echo $OLLAMA_TOKEN   # guárdalo: es el mismo que va en Vercel\n')
        return 1

    if len(TOKEN) < 24:
        print('ERROR: OLLAMA_TOKEN es demasiado corto. Usa al menos 24 caracteres.')
        return 1

    servidor = ThreadingHTTPServer(('0.0.0.0', PUERTO), ProxyHandler)
    logger.info('Proxy escuchando en http://localhost:%s -> %s', PUERTO, OLLAMA)
    logger.info('Solo se permiten: %s', RUTAS_PERMITIDAS)
    logger.info('Publícalo con:  cloudflared tunnel --url http://localhost:%s', PUERTO)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        logger.info('Proxy detenido')
        servidor.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
