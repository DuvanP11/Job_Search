#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proveedores concretos. Las claves se leen SIEMPRE de variables de entorno."""

from __future__ import annotations

import os
from typing import Optional

import requests

from .base import AIError, AIProvider


def _post(url: str, **kw):
    try:
        resp = requests.post(url, timeout=kw.pop('timeout', 120), **kw)
    except requests.exceptions.RequestException as exc:
        raise AIError(f'No se pudo conectar ({type(exc).__name__})') from exc
    if resp.status_code == 429:
        raise AIError('Cuota o límite de peticiones agotado (429)')
    if resp.status_code >= 400:
        raise AIError(f'HTTP {resp.status_code}: {resp.text[:200]}')
    try:
        return resp.json()
    except ValueError as exc:
        raise AIError('Respuesta no JSON del proveedor') from exc


class OllamaProvider(AIProvider):
    clave = 'ollama'
    nombre = 'Ollama (local)'
    gratuito = True

    def __init__(self, modelo: Optional[str] = None, url: Optional[str] = None,
                 token: Optional[str] = None):
        self.url = (url or os.getenv('OLLAMA_URL', 'http://localhost:11434')).rstrip('/')
        self.token = token if token is not None else os.getenv('OLLAMA_TOKEN', '')
        super().__init__(modelo or os.getenv('OLLAMA_MODEL'))

    def _cabeceras(self):
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    def configurado(self) -> bool:
        return bool(self.url)

    def _modelos(self):
        try:
            r = requests.get(f'{self.url}/api/tags', headers=self._cabeceras(), timeout=5)
            r.raise_for_status()
            return [m.get('name') for m in r.json().get('models', []) if m.get('name')]
        except (requests.exceptions.RequestException, ValueError):
            return []

    def disponible(self) -> bool:
        modelos = self._modelos()
        if not modelos:
            return False
        if self.modelo and self.modelo not in modelos:
            return False
        return True

    def generar(self, prompt, sistema='', json_mode=False, max_tokens=1500, temperatura=0.2):
        modelo = self.modelo
        if not modelo:
            modelos = self._modelos()
            if not modelos:
                raise AIError('Ollama no tiene modelos disponibles')
            modelo = modelos[0]
        payload = {'model': modelo, 'prompt': prompt, 'system': sistema, 'stream': False,
                   'think': False,
                   'options': {'temperature': temperatura, 'num_predict': max_tokens}}
        if json_mode:
            payload['format'] = 'json'
        data = _post(f'{self.url}/api/generate', json=payload, headers=self._cabeceras(), timeout=180)
        return data.get('response', '')


class OpenAICompatProvider(AIProvider):
    """OpenAI y cualquier API compatible (OpenRouter, LM Studio, Groq...)."""
    clave = 'openai'
    nombre = 'OpenAI'
    _url = 'https://api.openai.com/v1'
    _env_clave = 'OPENAI_API_KEY'
    _env_modelo = 'OPENAI_MODEL'
    _defecto = 'gpt-4o-mini'

    def __init__(self, modelo=None, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv(self._env_clave, '')
        self.base_url = (base_url or os.getenv(self._env_clave.replace('API_KEY', 'BASE_URL'), '')
                         or self._url).rstrip('/')
        super().__init__(modelo or os.getenv(self._env_modelo) or self._defecto)

    def modelo_por_defecto(self):
        return self._defecto

    def configurado(self):
        return bool(self.api_key)

    def generar(self, prompt, sistema='', json_mode=False, max_tokens=1500, temperatura=0.2):
        if not self.api_key:
            raise AIError(f'Falta {self._env_clave}')
        mensajes = ([{'role': 'system', 'content': sistema}] if sistema else []) + \
                   [{'role': 'user', 'content': prompt}]
        payload = {'model': self.modelo, 'messages': mensajes,
                   'max_tokens': max_tokens, 'temperature': temperatura}
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        data = _post(f'{self.base_url}/chat/completions', json=payload,
                     headers={'Authorization': f'Bearer {self.api_key}'})
        try:
            return data['choices'][0]['message']['content'] or ''
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError('Formato de respuesta inesperado') from exc


class OpenRouterProvider(OpenAICompatProvider):
    clave = 'openrouter'
    nombre = 'OpenRouter'
    gratuito = True  # existen modelos ":free", sujetos a cuota
    _url = 'https://openrouter.ai/api/v1'
    _env_clave = 'OPENROUTER_API_KEY'
    _env_modelo = 'OPENROUTER_MODEL'
    _defecto = 'meta-llama/llama-3.3-70b-instruct:free'


class AnthropicProvider(AIProvider):
    clave = 'anthropic'
    nombre = 'Anthropic'

    def __init__(self, modelo=None, api_key=None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
        super().__init__(modelo or os.getenv('ANTHROPIC_MODEL'))

    def modelo_por_defecto(self):
        return 'claude-haiku-5-5'

    def configurado(self):
        return bool(self.api_key)

    def generar(self, prompt, sistema='', json_mode=False, max_tokens=1500, temperatura=0.2):
        if not self.api_key:
            raise AIError('Falta ANTHROPIC_API_KEY')
        payload = {'model': self.modelo, 'max_tokens': max_tokens, 'temperature': temperatura,
                   'messages': [{'role': 'user', 'content': prompt}]}
        if sistema:
            payload['system'] = sistema
        data = _post('https://api.anthropic.com/v1/messages', json=payload,
                     headers={'x-api-key': self.api_key, 'anthropic-version': '2023-06-01'})
        try:
            return ''.join(b.get('text', '') for b in data['content'] if b.get('type') == 'text')
        except (KeyError, TypeError) as exc:
            raise AIError('Formato de respuesta inesperado') from exc


REGISTRO = {
    'ollama': OllamaProvider,
    'openrouter': OpenRouterProvider,
    'openai': OpenAICompatProvider,
    'anthropic': AnthropicProvider,
}
