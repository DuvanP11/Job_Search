#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de formularios de postulación con Playwright (genérico, parametrizable por ATS).

Principios de seguridad:
- Solo se usan datos VERIFICADOS del perfil para los campos de contacto.
- Preguntas sensibles (legales, médicas, demográficas, migratorias, declaraciones) y casillas de
  consentimiento/términos NUNCA se responden: se detiene y pasa al usuario.
- CAPTCHA, MFA, inicio de sesión: se detiene. No se intenta evadir ni resolver nada.
- Un campo obligatorio desconocido no se inventa: se detiene.
- 'confirmado' solo con señal positiva del portal (URL de confirmación o texto + formulario ausente).
- Sin `enviar_real` nunca se pulsa el botón de enviar (dry-run).
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..profile import estado_campos
from ..security import es_pregunta_sensible, validar_url_aplicacion
from .base import (CONFIRMADO, DRY_RUN, ENVIADO_SIN_CONFIRMACION, ERROR, REQUIERE_USUARIO, Aplicador,
                   ResultadoAplicacion, SolicitudAplicacion)

TIMEOUT_MS = 25000

# --------------------------------------------------------------- JS de lectura
_JS_CAMPOS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = n => (n && (n.innerText || n.textContent) || '').replace(/\s+/g, ' ').trim();
  const out = []; let idx = 0;
  const els = document.querySelectorAll('input, textarea, select');
  for (const el of els) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (el.disabled) continue;
    if (type !== 'file' && !vis(el)) continue;
    // Selectores personalizados (react-select) traen un <input> sombra sin tipo ni etiqueta: no es un campo.
    if (!el.getAttribute('type') && el.tagName === 'INPUT' && !el.id && !el.name &&
        !(el.labels && el.labels.length) && /requiredInput|shadow|sr-only/i.test(el.className || '')) continue;
    el.setAttribute('data-aa-idx', String(idx));
    let label = '';
    if (el.labels && el.labels.length) label = [...el.labels].map(txt).join(' ');
    if (!label && el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
    if (!label && el.getAttribute('aria-labelledby'))
      label = el.getAttribute('aria-labelledby').split(/\s+/).map(i => txt(document.getElementById(i))).join(' ');
    let pregunta = '';
    const fs = el.closest('fieldset'); if (fs && fs.querySelector('legend')) pregunta = txt(fs.querySelector('legend'));
    if (!pregunta) { const c = el.closest('.field, .application-question, .question, [class*=question], [class*=field]');
      if (c) { const l = c.querySelector('label, .label, legend'); if (l) pregunta = txt(l); } }
    if (!label) label = pregunta || el.getAttribute('placeholder') || el.name || el.id || '';
    out.push({ idx: idx++, tag: el.tagName.toLowerCase(), type, name: el.name || '', id: el.id || '',
      label: label.slice(0, 300), pregunta: (pregunta || label).slice(0, 300),
      required: !!(el.required || el.getAttribute('aria-required') === 'true' || /\*\s*$/.test(label)),
      options: el.tagName === 'SELECT' ? [...el.options].map(o => ({ value: o.value, text: txt(o) })) : [],
      opcion: (type === 'radio' || type === 'checkbox') ? (txt(el.closest('label')) || label) : '',
      combobox: el.getAttribute('role') === 'combobox' || el.getAttribute('aria-haspopup') === 'listbox',
      value: el.value || '' });
  }
  return out;
}
"""

_JS_BLOQUEOS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 8 && r.height > 8 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const h = [];
  for (const el of document.querySelectorAll('iframe')) {
    const src = (el.src || '') + ' ' + (el.title || '');
    if (/recaptcha|hcaptcha|turnstile|arkoselabs|funcaptcha|captcha/i.test(src) && vis(el)
        && !/badge|invisible/i.test(src)) h.push('captcha');
  }
  for (const el of document.querySelectorAll('.g-recaptcha, .h-captcha, .cf-turnstile, [data-sitekey]'))
    if (vis(el)) h.push('captcha');
  if (document.querySelector('input[type=password]') && [...document.querySelectorAll('input[type=password]')].some(vis)) h.push('login');
  const t = (document.body.innerText || '').toLowerCase();
  if (/verify you are human|i'?m not a robot|no soy un robot|verifica que eres humano|complete the security check/.test(t)) h.push('captcha');
  if (/verification code|enter the code|código de verificación|two-factor|autenticación de dos factores|2fa|one-time (pass)?code/.test(t)) h.push('mfa');
  return [...new Set(h)];
}
"""

_JS_ESTADO_POST = r"""
() => {
  const t = (document.body.innerText || '').replace(/\s+/g, ' ');
  const errores = [...document.querySelectorAll('[aria-invalid=true], .error, .field-error, [role=alert], .invalid-feedback')]
      .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 8);
  const formularioVisible = [...document.querySelectorAll('form')].some(f => {
      const r = f.getBoundingClientRect(); return r.width > 0 && r.height > 0 &&
        f.querySelector('input[type=email], input[name*=email], input[type=file]'); });
  const invalidos = [...document.querySelectorAll('form :invalid')].map(e =>
      ((e.labels && e.labels[0] && e.labels[0].innerText) || e.name || e.id || e.className || 'campo').trim().slice(0, 60));
  return { texto: t.slice(0, 4000), errores, formularioVisible, invalidos, url: location.href };
}
"""

# ------------------------------------------------------------ clasificación
_CAMPOS = (
    ('empresa_actual', r'current or previous (employer|company)|current (employer|company)|empresa actual|empleador actual'),
    ('cargo_actual', r'current or previous (job )?title|current (job )?title|cargo actual|puesto actual'),
    ('email', r'e-?mail|correo'),
    ('nombre', r'first\s*name|given\s*name|^nombres?\b|primer nombre'),
    ('apellido', r'last\s*name|surname|family\s*name|apellidos?'),
    ('nombre_completo', r'^(full\s*)?name\b|your name|nombre completo|^nombre$|preferred name'),
    ('telefono', r'phone|tel[eé]fono|celular|mobile|whatsapp'),
    ('linkedin', r'linkedin'),
    ('github', r'github'),
    ('web', r'website|portfolio|sitio web|personal (site|url)|^url$'),
    ('ciudad', r'\bcity\b|ciudad|current location|ubicaci[oó]n actual|where are you (based|located)|^location\s*\*?$'),
    ('salario', r'salary|salario|compensation|expectativa salarial|pretensi'),
)
_CONSENTIMIENTO = re.compile(r'consent|acknowledge|i agree|agree to|accept|privacy|terms|gdpr|acepto|autorizo|términos|terminos|'
                             r'pol[ií]tica de|tratamiento de datos|certify|declar', re.I)


def clasificar(campo: Dict[str, Any]) -> str:
    """Devuelve la clave del dato del perfil que corresponde al campo, o ''."""
    if campo['type'] == 'file':
        t = f"{campo['label']} {campo['name']} {campo['id']}".lower()
        if re.search(r'cover|carta|motivaci', t):
            return 'archivo_carta'
        if re.search(r'resume|cv\b|curr[ií]culum|hoja de vida|attach', t) or not t.strip():
            return 'archivo_cv'
        return ''
    t = f"{campo['label']} {campo['name']} {campo['id']}".lower().strip()
    if campo['tag'] == 'textarea' and re.search(r'cover letter|carta de presentaci', t):
        return 'texto_carta'
    for clave, patron in _CAMPOS:
        if re.search(patron, t, re.I):
            return clave
    return ''


def datos_verificados(c: Dict[str, Any]) -> Dict[str, str]:
    """Solo valores que el usuario confirmó (campos_confirmados) o que no son de contacto."""
    est = estado_campos(c)
    nombre = (c.get('nombre_completo') or '').strip()
    partes = nombre.split()
    ok = lambda k: est.get(k) == 'verificado'                     # noqa: E731
    d: Dict[str, str] = {}
    if ok('nombre_completo') and nombre:
        d['nombre_completo'] = nombre
        d['nombre'] = partes[0] if len(partes) < 3 else ' '.join(partes[:len(partes) // 2])
        d['apellido'] = ' '.join(partes[1:]) if len(partes) < 3 else ' '.join(partes[len(partes) // 2:])
    for k_perfil, k_dato in (('email', 'email'), ('telefono', 'telefono'), ('ciudad', 'ciudad'),
                             ('linkedin', 'linkedin')):
        if ok(k_perfil) and c.get(k_perfil):
            d[k_dato] = str(c[k_perfil])
    exp = (c.get('experiencia') or [{}])[0]
    if ok('experiencia') and exp.get('empresa'):
        d['empresa_actual'] = exp['empresa']
    if ok('experiencia') and exp.get('cargo'):
        d['cargo_actual'] = exp['cargo']
    if c.get('aspiracion_salarial'):
        d['salario'] = str(int(c['aspiracion_salarial']))
    return d


def _respuesta_guardada(pregunta: str, c: Dict[str, Any]) -> Optional[str]:
    """Banco de respuestas del propio usuario: {'fragmento de la pregunta': 'respuesta'}."""
    p = pregunta.lower()
    for frag, resp in (c.get('respuestas_guardadas') or {}).items():
        if frag and frag.lower() in p and resp:
            return str(resp)
    return None


# ------------------------------------------------------------------- motor
class AplicadorFormulario(Aplicador):
    clave = 'formulario'
    portales: Tuple[str, ...] = ()
    patrones_url_confirmacion = r'/(confirmation|confirmed|thanks?|thank-you|success|submitted|applied|gracias)(/|$|\?)'
    patrones_texto_confirmacion = (
        r'thank you for (applying|your application|submitting)', r'application (has been |was )?(submitted|received)',
        r'we(\'ve| have) received your application', r'gracias por (postularte|aplicar|tu postulaci[oó]n)',
        r'(hemos )?recibido tu (postulaci[oó]n|solicitud)', r'postulaci[oó]n (enviada|recibida)')
    texto_boton_enviar = r'submit|enviar|apply|postular|aplicar'

    def __init__(self, permitir_local: bool = False, headless: bool = True):
        self.permitir_local = permitir_local          # solo para pruebas con servidores locales
        self.headless = headless

    def soporta(self, job: Dict[str, Any]) -> bool:
        return (job.get('portal') or '').lower() in self.portales

    def url_formulario(self, job: Dict[str, Any]) -> str:
        return job.get('application_url') or job.get('url') or ''

    # ---- utilidades de página --------------------------------------------
    def _captura(self, page, carpeta: str, nombre: str) -> str:
        if not carpeta:
            return ''
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f'{int(time.time())}_{nombre}.png')
        try:
            page.screenshot(path=ruta, full_page=True)
            return ruta
        except Exception:  # noqa: BLE001
            return ''

    def _bloqueos(self, page) -> List[str]:
        try:
            return page.evaluate(_JS_BLOQUEOS)
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _mensaje_bloqueo(b: List[str]) -> str:
        textos = {'captcha': 'El portal pide resolver un CAPTCHA', 'mfa': 'El portal pide un código de verificación (MFA)',
                  'login': 'El portal pide iniciar sesión'}
        return '; '.join(textos[x] for x in b if x in textos) + '. Complétalo tú en el portal.'

    def _permitir_ruta(self, route) -> None:
        req = route.request
        if req.resource_type == 'document' or req.is_navigation_request():
            ok, _ = validar_url_aplicacion(req.url) if not self.permitir_local else (True, '')
            if not ok and not req.url.startswith(('about:', 'data:', 'blob:')):
                route.abort()
                return
        route.continue_()

    # ---- flujo principal -------------------------------------------------
    def aplicar(self, s: SolicitudAplicacion) -> ResultadoAplicacion:
        url = self.url_formulario(s.job)
        if not self.permitir_local:
            ok, motivo = validar_url_aplicacion(url)
            if not ok:
                return ResultadoAplicacion(REQUIERE_USUARIO, f'URL de postulación no permitida: {motivo}')
        datos = datos_verificados(s.candidato)
        faltan = [k for k, n in (('nombre_completo', 'nombre'), ('email', 'email'), ('telefono', 'teléfono'))
                  if k not in datos]
        if faltan:
            return ResultadoAplicacion(
                REQUIERE_USUARIO, 'Confirma en tu perfil (marca "es correcto") tu nombre, email y teléfono antes de postular.',
                campos_pendientes=[dict(nombre_completo='nombre', email='email', telefono='teléfono')[k] for k in faltan])
        try:
            from playwright.sync_api import Error as PWError, TimeoutError as PWTimeout, sync_playwright
        except ImportError:
            return ResultadoAplicacion(ERROR, 'Playwright no está instalado (pip install -r requirements-worker.txt; '
                                              'playwright install chromium).')
        with sync_playwright() as pw:
            navegador = pw.chromium.launch(headless=self.headless)
            try:
                ctx = navegador.new_context(locale='es-CO', viewport={'width': 1280, 'height': 1800})
                ctx.set_default_timeout(TIMEOUT_MS)
                ctx.route('**/*', self._permitir_ruta)
                page = ctx.new_page()
                try:
                    return self._flujo(page, s, datos)
                except PWTimeout as exc:
                    return ResultadoAplicacion(ERROR, f'Tiempo de espera agotado: {str(exc)[:120]}', reintentable=True,
                                               evidencia={'capturas': [self._captura(page, s.carpeta_evidencia, 'timeout')]})
                except PWError as exc:
                    return ResultadoAplicacion(ERROR, f'Error del navegador: {str(exc)[:160]}', reintentable=True)
            finally:
                navegador.close()

    def _flujo(self, page, s: SolicitudAplicacion, datos: Dict[str, str]) -> ResultadoAplicacion:
        page.goto(self.url_formulario(s.job), wait_until='domcontentloaded')
        try:
            page.wait_for_load_state('networkidle', timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        evidencia: Dict[str, Any] = {'url_formulario': page.url, 'capturas': []}
        b = self._bloqueos(page)
        if b:
            evidencia['capturas'].append(self._captura(page, s.carpeta_evidencia, 'bloqueo'))
            return ResultadoAplicacion(REQUIERE_USUARIO, self._mensaje_bloqueo(b), evidencia=evidencia)

        campos = page.evaluate(_JS_CAMPOS)
        if not campos:
            evidencia['capturas'].append(self._captura(page, s.carpeta_evidencia, 'sin_formulario'))
            return ResultadoAplicacion(REQUIERE_USUARIO, 'No se encontró un formulario de postulación en la página '
                                       '(¿la oferta cerró o requiere iniciar sesión?).', evidencia=evidencia)

        pendientes, llenados = self._rellenar(page, campos, s, datos)
        evidencia['capturas'].append(self._captura(page, s.carpeta_evidencia, 'formulario_completo'))
        evidencia['campos_llenados'] = llenados
        if pendientes:
            return ResultadoAplicacion(REQUIERE_USUARIO, 'Hay preguntas que debes responder tú: '
                                       + '; '.join(pendientes[:6]), campos_pendientes=pendientes, evidencia=evidencia)
        if not s.enviar_real:
            return ResultadoAplicacion(DRY_RUN, 'Formulario completado y validado; no se envió.', evidencia=evidencia)
        return self._enviar(page, s, evidencia)

    # ---- rellenar ----------------------------------------------------------
    def _rellenar(self, page, campos: List[Dict[str, Any]], s: SolicitudAplicacion,
                  datos: Dict[str, str]) -> Tuple[List[str], List[str]]:
        pendientes: List[str] = []
        llenados: List[str] = []
        grupos: Dict[str, List[Dict[str, Any]]] = {}
        for c in campos:
            if c['type'] in ('radio', 'checkbox') and c['name']:
                grupos.setdefault(c['name'], []).append(c)
        vistos_grupo = set()
        loc = lambda c: page.locator(f"[data-aa-idx='{c['idx']}']")           # noqa: E731

        for c in campos:
            pregunta = c['pregunta'] or c['label']
            if c['type'] in ('radio', 'checkbox') and c['name']:
                if c['name'] in vistos_grupo:
                    continue
                vistos_grupo.add(c['name'])
                requerido = any(x['required'] for x in grupos[c['name']])
                if es_pregunta_sensible(pregunta) or _CONSENTIMIENTO.search(pregunta + ' ' + c['opcion']):
                    if requerido:
                        pendientes.append(f'{pregunta[:90]} (consentimiento/declaración o dato sensible)')
                    continue                                   # opcional: se deja sin responder
                guardada = _respuesta_guardada(pregunta, s.candidato)
                if guardada:
                    for op in grupos[c['name']]:
                        if guardada.lower() in (op['opcion'] or '').lower():
                            loc(op).check()
                            llenados.append(pregunta[:60])
                            break
                    else:
                        if requerido:
                            pendientes.append(pregunta[:90])
                elif requerido:
                    pendientes.append(pregunta[:90])
                continue

            # Lo sensible va ANTES de cualquier clasificación: una pregunta sobre autorización de
            # trabajo que mencione "location" no debe contestarse con tu ciudad.
            if es_pregunta_sensible(pregunta) or es_pregunta_sensible(c['label']):
                if c['required']:
                    pendientes.append(f'{pregunta[:90]} (dato sensible)')
                continue
            clave = clasificar(c)
            if clave == 'archivo_cv' and s.archivos.get('cv'):
                loc(c).set_input_files(s.archivos['cv'])
                llenados.append('CV adjunto')
            elif clave == 'archivo_carta' and s.archivos.get('carta'):
                loc(c).set_input_files(s.archivos['carta'])
                llenados.append('Carta adjunta')
            elif c['type'] == 'file':
                if c['required']:
                    pendientes.append(f'Archivo requerido: {pregunta[:70]}')
            elif clave == 'texto_carta' and s.carta_texto:
                loc(c).fill(s.carta_texto)
                llenados.append('Carta (texto)')
            elif clave and clave in datos and c.get('combobox'):
                if self._combobox(page, loc(c), datos[clave].split(',')[0]):
                    llenados.append(clave)
                else:
                    pendientes.append(f'{pregunta[:90]} (elige la opción en el portal)')
            elif c.get('combobox'):
                guardada = _respuesta_guardada(pregunta, s.candidato)
                if not (guardada and self._combobox(page, loc(c), guardada)) and c['required']:
                    pendientes.append(pregunta[:90])
            elif clave and clave in datos and c['tag'] in ('input', 'textarea'):
                loc(c).fill(datos[clave])
                llenados.append(clave)
            elif c['tag'] == 'select':
                self._select(loc(c), c, pregunta, s, pendientes, llenados)
            elif c['tag'] in ('input', 'textarea'):
                guardada = _respuesta_guardada(pregunta, s.candidato)
                if guardada:
                    loc(c).fill(guardada)
                    llenados.append(pregunta[:60])
                elif c['required'] and c['tag'] == 'textarea' and s.permitir_respuestas_ia and s.responder:
                    r = s.responder(pregunta)
                    if r.get('estado') == 'borrador' and r.get('respuesta'):
                        loc(c).fill(r['respuesta'])
                        llenados.append(f'{pregunta[:50]} (borrador IA)')
                    else:
                        pendientes.append(pregunta[:90])
                elif c['required']:
                    pendientes.append(pregunta[:90])
        return pendientes, llenados

    def _combobox(self, page, locator, valor: str) -> bool:
        """Escribe y elige una opción REAL de la lista; si no aparece ninguna, no se da por llenado."""
        try:
            locator.click()
            locator.fill(valor)
            opcion = page.get_by_role('option').filter(has_text=re.compile(re.escape(valor), re.I)).first
            opcion.wait_for(state='visible', timeout=4000)
            opcion.click()
            return True
        except Exception:  # noqa: BLE001
            try:
                locator.fill('')
            except Exception:  # noqa: BLE001
                pass
            return False

    def _select(self, locator, c, pregunta, s, pendientes, llenados) -> None:
        guardada = _respuesta_guardada(pregunta, s.candidato)
        if guardada:
            for op in c['options']:
                if guardada.lower() in op['text'].lower():
                    locator.select_option(value=op['value'])
                    llenados.append(pregunta[:60])
                    return
        if c['required'] and not es_pregunta_sensible(pregunta):
            pendientes.append(pregunta[:90])
        elif c['required']:
            pendientes.append(f'{pregunta[:90]} (dato sensible)')

    # ---- enviar y verificar --------------------------------------------------
    def _enviar(self, page, s: SolicitudAplicacion, evidencia: Dict[str, Any]) -> ResultadoAplicacion:
        boton = page.get_by_role('button', name=re.compile(self.texto_boton_enviar, re.I))
        if not boton.count():
            boton = page.locator("input[type=submit], button[type=submit]")
        if not boton.count():
            return ResultadoAplicacion(ERROR, 'No se encontró el botón de enviar.', evidencia=evidencia)
        boton.last.click()
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(800)
        evidencia['capturas'].append(self._captura(page, s.carpeta_evidencia, 'despues_de_enviar'))
        evidencia['url_final'] = page.url

        b = self._bloqueos(page)
        if b:
            return ResultadoAplicacion(REQUIERE_USUARIO, self._mensaje_bloqueo(b) + ' El envío NO se completó.',
                                       evidencia=evidencia)
        est = page.evaluate(_JS_ESTADO_POST)
        url_ok = re.search(self.patrones_url_confirmacion, urlparse(est['url']).path + '/', re.I)
        texto_ok = any(re.search(p, est['texto'], re.I) for p in self.patrones_texto_confirmacion)
        if (url_ok or texto_ok) and not est['formularioVisible']:
            evidencia['senal'] = ('URL de confirmación' if url_ok else '') + (' + ' if url_ok and texto_ok else '') + \
                                 ('texto de confirmación' if texto_ok else '')
            return ResultadoAplicacion(CONFIRMADO, 'El portal confirmó la postulación.', evidencia=evidencia)
        if est['errores'] and est['formularioVisible']:
            return ResultadoAplicacion(ERROR, 'El portal rechazó el formulario: ' + ' | '.join(est['errores'][:4]),
                                       evidencia=evidencia)
        if est['formularioVisible'] and est['invalidos'] and not (url_ok or texto_ok):
            # La validación del propio navegador frenó el envío: NO salió nada hacia el portal.
            return ResultadoAplicacion(ERROR, 'El envío no salió: faltan campos válidos en el formulario ('
                                       + ', '.join(est['invalidos'][:5]) + ').', evidencia=evidencia)
        return ResultadoAplicacion(ENVIADO_SIN_CONFIRMACION, 'Se pulsó Enviar pero el portal no mostró una confirmación '
                                   'clara. Verifica en tu correo o en el portal.', evidencia=evidencia)


class GreenhouseAplicador(AplicadorFormulario):
    clave = 'greenhouse'
    portales = ('greenhouse',)


class LeverAplicador(AplicadorFormulario):
    clave = 'lever'
    portales = ('lever',)
