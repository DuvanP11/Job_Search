#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generación de documentos por vacante: CV a la medida, carta y respuestas.

Regla de oro: se reorganiza y se redacta con datos del perfil; NUNCA se agregan
hechos. La IA solo redacta (resumen, carta) y su salida se valida contra el
perfil y la oferta; si inventa una cifra o un nombre propio, se usa la
plantilla determinística. La hoja de vida original no se toca.
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple

from .ai import AIError, get_router
from .jobs import sin_acentos
from .profile import estado_campos
from .security import es_pregunta_sensible

MAX_LOGROS = 5
MAX_EXPERIENCIAS = 6

# Palabras capitalizadas que son saludos/cortesía y no nombres propios.
_CORTESIA = {s.lower() for s in (
    'Estimado', 'Estimados', 'Estimada', 'Equipo', 'Cordial', 'Cordialmente', 'Atentamente', 'Saludos', 'Hola',
    'Gracias', 'Reciban', 'Señores', 'Señor', 'Señora', 'Dear', 'Hiring', 'Team', 'Manager', 'Regards', 'Sincerely',
    'Best', 'Thank', 'Thanks', 'Respetados', 'Respetado', 'Talento', 'Humano', 'Recursos', 'Humanos', 'Selección')}


# ------------------------------------------------------------ utilidades

def _tokens(texto: str) -> set:
    return {t for t in re.findall(r'[a-z0-9+#.]{3,}', sin_acentos(texto))}


def _relevancia(texto: str, job_tokens: set) -> int:
    return len(_tokens(texto) & job_tokens)


def idioma_de(texto: str) -> str:
    t = f' {sin_acentos(texto)} '
    en = sum(t.count(p) for p in (' the ', ' and ', ' with ', ' you ', ' our ', ' will ', ' experience '))
    es = sum(t.count(p) for p in (' el ', ' la ', ' de ', ' y ', ' con ', ' para ', ' los ', ' experiencia '))
    return 'en' if en > es else 'es'


def validar_texto_generado(texto: str, corpus: str) -> List[str]:
    """Devuelve lo que el texto afirma y no está en el perfil ni en la oferta."""
    # Marcadores sin rellenar ([Nombre del destinatario], {empresa}, <fecha>, XXX): nunca deben salir.
    marcadores = re.findall(r'\[[^\]\n]{2,60}\]|\{[^}\n]{2,40}\}|<[A-Za-z][^>\n]{2,40}>|\bX{3,}\b|\.{3}\s*\]', texto)
    base = sin_acentos(corpus)
    base_digitos = re.sub(r'[^0-9]', ' ', base)
    sospechosos: List[str] = list(marcadores)
    for num in re.findall(r'\d[\d.,]*', texto):
        limpio = re.sub(r'[.,]+$', '', num)
        if limpio and limpio not in base_digitos and limpio not in base:
            sospechosos.append(limpio)
    for m in re.finditer(r'(?<![.!?\n])\s([A-ZÁÉÍÓÚÑ][\wáéíóúñü&-]{2,})', texto):
        palabra = m.group(1)
        if sin_acentos(palabra) in base or palabra.lower() in _CORTESIA or sin_acentos(palabra) in _CORTESIA:
            continue
        sospechosos.append(palabra)
    return sorted(set(sospechosos))


# ------------------------------------------------------------ CV a la medida

def _anios_texto(c: Dict[str, Any]) -> str:
    try:
        a = float(c.get('anios_experiencia') or 0)
    except (TypeError, ValueError):
        return ''
    return f'{a:g}' if a > 0 else ''


def _resumen_plantilla(c: Dict[str, Any], habilidades: List[str]) -> str:
    cargo = ''
    if c.get('experiencia'):
        cargo = (c['experiencia'][0].get('cargo') or '').strip()
    cargo = cargo or (c.get('titular') or '').split('|')[0].strip()
    anios, top = _anios_texto(c), ', '.join(habilidades[:4])
    partes = []
    if cargo:
        partes.append(cargo)
    if anios:
        partes.append(f'con {anios} años de experiencia')
    if top:
        partes.append(f'en {top}')
    return (' '.join(partes) + '.') if partes else ''


def construir_datos_cv(c: Dict[str, Any], job: Dict[str, Any], router=None,
                       usar_ia: bool = True) -> Dict[str, Any]:
    """CV en el esquema de utils.cv_builder, adaptado a la vacante sin añadir hechos."""
    job_tokens = _tokens(f"{job.get('titulo', '')} {job.get('descripcion', '')}")
    estados = estado_campos(c)
    advertencias: List[str] = []

    habs = [h.get('nombre') if isinstance(h, dict) else h for h in c.get('habilidades') or []]
    habs = [str(h) for h in habs if h]
    habs.sort(key=lambda h: -_relevancia(h, job_tokens))      # las que pide la oferta, primero
    coinciden = [h for h in habs if _relevancia(h, job_tokens)]

    experiencia = []
    for x in (c.get('experiencia') or [])[:MAX_EXPERIENCIAS]:
        logros = [*(x.get('logros') or []), *(x.get('responsabilidades') or [])]
        logros = sorted(dict.fromkeys(l for l in logros if l),
                        key=lambda l: -_relevancia(l, job_tokens))[:MAX_LOGROS]
        experiencia.append({'cargo': x.get('cargo', ''), 'empresa': x.get('empresa', ''), 'ubicacion': '',
                            'inicio': x.get('desde', ''), 'fin': x.get('hasta', ''), 'logros': logros})

    resumen, generado_con = c.get('resumen') or '', 'perfil'
    if not resumen:
        resumen, generado_con = _resumen_plantilla(c, habs), 'plantilla'
    if usar_ia and (c.get('resumen') or experiencia):
        try:
            router = router or get_router()
            hechos = (f"Cargo/titular: {c.get('titular', '')}. Años de experiencia: {_anios_texto(c)}. "
                      f"Habilidades: {', '.join(habs[:10])}. Resumen actual: {c.get('resumen', '')}. "
                      f"Experiencia: " + '; '.join(f"{e['cargo']} en {e['empresa']}" for e in experiencia))
            r = router.generar('documentos',
                               f"Reescribe el resumen profesional (máx. 3 frases) destacando lo más afín al cargo "
                               f"'{job.get('titulo', '')}'. Usa SOLO estos hechos, sin añadir cifras, empresas, "
                               f"títulos ni habilidades nuevas:\n{hechos}",
                               sistema='Redactas resúmenes de CV veraces en el idioma de los hechos. Sin inventar.',
                               max_tokens=300, temperatura=0.3)
            texto = re.sub(r'\s+', ' ', r['texto']).strip()
            sospechoso = validar_texto_generado(texto, hechos + ' ' + str(c.get('resumen', '')))
            if texto and not sospechoso:
                resumen, generado_con = texto, f"ia:{r['proveedor']}/{r['modelo']}"
            else:
                advertencias.append('La IA añadió datos que no están en tu perfil '
                                    f'({", ".join(sospechoso[:4])}); se usó tu resumen original.')
        except AIError:
            pass   # sin IA: se queda el resumen del perfil o la plantilla

    usados = ['nombre_completo', 'email', 'telefono', 'ciudad', 'linkedin', 'titular', 'resumen',
              'habilidades', 'experiencia', 'educacion', 'idiomas', 'certificaciones']
    no_verificados = [k for k in usados if c.get(k) and estados.get(k) != 'verificado']
    if no_verificados:
        advertencias.append('Datos sin confirmar usados en el documento: ' + ', '.join(no_verificados) +
                            '. Revísalos en tu perfil antes de enviar.')

    datos = {
        'nombre': c.get('nombre_completo', ''),
        'titular': c.get('titular', ''),
        'contacto': {'email': c.get('email', ''), 'telefono': c.get('telefono', ''),
                     'ciudad': c.get('ciudad', ''), 'linkedin': c.get('linkedin', '')},
        'resumen': resumen,
        'experiencia': experiencia,
        'educacion': [{'titulo': e.get('titulo', ''), 'institucion': e.get('institucion', ''),
                       'anio': e.get('anio', '')} for e in c.get('educacion') or []],
        'habilidades_tecnicas': habs,
        'habilidades_blandas': [str(h) for h in c.get('habilidades_blandas') or []],
        'certificaciones': [str(x) for x in c.get('certificaciones') or []],
        'idiomas': [f"{i.get('idioma', '')} ({i.get('nivel', '')})" if i.get('nivel') else i.get('idioma', '')
                    for i in c.get('idiomas') or [] if isinstance(i, dict)],
        'referencias': [],
    }
    return {'datos': datos, 'generado_con': generado_con, 'advertencias': advertencias,
            'habilidades_coincidentes': coinciden}


# ----------------------------------------------------------------- carta

def _carta_plantilla(c: Dict[str, Any], job: Dict[str, Any], coincidentes: List[str], idioma: str) -> str:
    empresa = job.get('empresa') if job.get('empresa') not in (None, '', 'No especificada') else ''
    cargo = job.get('titulo', '')
    anios, nombre = _anios_texto(c), c.get('nombre_completo', '')
    ultimo = (c.get('experiencia') or [{}])[0]
    skills = ', '.join(coincidentes[:5])
    if idioma == 'en':
        saludo = f'Dear {empresa} Hiring Team,' if empresa else 'Dear Hiring Team,'
        p1 = f'I am writing to apply for the {cargo} position' + (f' at {empresa}.' if empresa else '.')
        p2 = ''
        if anios or skills:
            p2 = 'I bring ' + (f'{anios} years of experience' if anios else 'relevant experience') + \
                 (f', with hands-on work in {skills}' if skills else '') + '.'
        if ultimo.get('cargo') and ultimo.get('empresa'):
            p2 += f" Most recently I worked as {ultimo['cargo']} at {ultimo['empresa']}."
        cierre = 'I would welcome the chance to discuss how I can contribute. Thank you for your time.'
        despedida = f'Sincerely,\n{nombre}'.strip()
    else:
        saludo = f'Estimado equipo de {empresa},' if empresa else 'Estimado equipo de Talento Humano,'
        p1 = f'Les escribo para postularme al cargo de {cargo}' + (f' en {empresa}.' if empresa else '.')
        p2 = ''
        if anios or skills:
            p2 = 'Cuento con ' + (f'{anios} años de experiencia' if anios else 'experiencia relevante') + \
                 (f', con trabajo práctico en {skills}' if skills else '') + '.'
        if ultimo.get('cargo') and ultimo.get('empresa'):
            p2 += f" Recientemente me desempeñé como {ultimo['cargo']} en {ultimo['empresa']}."
        cierre = 'Quedo atento a conversar sobre cómo puedo aportar al equipo. Gracias por su tiempo.'
        despedida = f'Cordialmente,\n{nombre}'.strip()
    return '\n\n'.join(p for p in (saludo, p1, p2.strip(), cierre, despedida) if p)


def generar_carta(c: Dict[str, Any], job: Dict[str, Any], coincidentes: Optional[List[str]] = None,
                  router=None, usar_ia: bool = True) -> Dict[str, Any]:
    idioma = idioma_de(f"{job.get('titulo', '')} {job.get('descripcion', '')}")
    coincidentes = coincidentes or []
    texto, generado_con, advertencias = _carta_plantilla(c, job, coincidentes, idioma), 'plantilla', []
    if usar_ia:
        hechos = (f"Candidato: {c.get('nombre_completo', '')}. Años de experiencia: {_anios_texto(c)}. "
                  f"Habilidades afines a la oferta: {', '.join(coincidentes[:6])}. "
                  f"Experiencia: " + '; '.join(f"{e.get('cargo', '')} en {e.get('empresa', '')}"
                                               for e in (c.get('experiencia') or [])[:3]) +
                  f". Resumen: {c.get('resumen', '')}")
        oferta = f"Cargo: {job.get('titulo', '')}. Empresa: {job.get('empresa', '')}."
        empresa_ok = job.get('empresa') if job.get('empresa') not in (None, '', 'No especificada') else ''
        if idioma == 'en':
            saludo, firma = (f'Dear {empresa_ok} Hiring Team,' if empresa_ok else 'Dear Hiring Team,'), \
                f"Sincerely,\n{c.get('nombre_completo', '')}"
        else:
            saludo, firma = (f'Estimado equipo de {empresa_ok},' if empresa_ok else 'Estimado equipo de Talento Humano,'), \
                f"Cordialmente,\n{c.get('nombre_completo', '')}"
        try:
            router = router or get_router()
            r = router.generar(
                'documentos',
                f"Redacta una carta de presentación breve (máx. 150 palabras, 3 párrafos) en "
                f"{'inglés' if idioma == 'en' else 'español'}.\nOFERTA: {oferta}\nHECHOS DEL CANDIDATO "
                f"(usa solo estos, sin inventar cifras, empresas ni logros):\n{hechos}\n"
                f"FORMATO: empieza exactamente con \"{saludo}\" y termina con la firma \"{firma}\". "
                f"Prohibido usar corchetes, llaves o marcadores como [Nombre]; el texto se envía tal cual.",
                sistema='Eres un redactor de cartas de presentación honestas y concretas. Sin inventar nada.',
                max_tokens=500, temperatura=0.4)
            candidata = r['texto'].strip()
            sospechoso = validar_texto_generado(candidata, hechos + ' ' + oferta + ' ' + str(job.get('descripcion', '')[:3000]))
            if candidata and not sospechoso:
                texto, generado_con = candidata, f"ia:{r['proveedor']}/{r['modelo']}"
            else:
                advertencias.append('La IA mencionó datos que no están en tu perfil ni en la oferta '
                                    f'({", ".join(sospechoso[:4])}); se usó la plantilla.')
        except AIError:
            pass
    return {'texto': texto, 'idioma': idioma, 'generado_con': generado_con, 'advertencias': advertencias}


# ---------------------------------------------------- preguntas abiertas

def responder_pregunta(pregunta: str, c: Dict[str, Any], job: Dict[str, Any], router=None) -> Dict[str, Any]:
    """Respuesta redactada o `requiere_usuario`. Lo sensible nunca pasa por la IA."""
    if es_pregunta_sensible(pregunta):
        return {'estado': 'requiere_usuario', 'motivo': 'Pregunta sensible (legal, salud, demográfica o migratoria): '
                'la debes responder tú.', 'respuesta': ''}
    hechos = (f"Experiencia: " + '; '.join(f"{e.get('cargo', '')} en {e.get('empresa', '')}"
                                           for e in (c.get('experiencia') or [])[:4]) +
              f". Habilidades: {', '.join(str(h) for h in (c.get('habilidades') or [])[:12])}. "
              f"Años: {_anios_texto(c)}. Resumen: {c.get('resumen', '')}")
    try:
        r = (router or get_router()).generar(
            'formularios',
            f"Responde en primera persona, máx. 80 palabras, a la pregunta de un formulario de empleo.\n"
            f"PREGUNTA: {pregunta[:500]}\nCARGO: {job.get('titulo', '')}\nHECHOS (usa solo estos):\n{hechos}\n"
            f"Si los hechos no alcanzan para responder con verdad, responde exactamente: NO_SE",
            sistema='Respondes formularios de empleo con veracidad. Si falta información, dices NO_SE.',
            max_tokens=250, temperatura=0.2)
    except AIError as exc:
        return {'estado': 'requiere_usuario', 'motivo': f'Sin IA disponible ({exc})', 'respuesta': ''}
    texto = r['texto'].strip()
    if not texto or 'NO_SE' in texto:
        return {'estado': 'requiere_usuario', 'motivo': 'Tu perfil no tiene datos suficientes para responder.', 'respuesta': ''}
    sospechoso = validar_texto_generado(texto, hechos + ' ' + pregunta + ' ' + job.get('titulo', ''))
    if sospechoso:
        return {'estado': 'requiere_usuario', 'respuesta': '',
                'motivo': f'La IA mencionó datos que no están en tu perfil ({", ".join(sospechoso[:3])}).'}
    return {'estado': 'borrador', 'respuesta': texto, 'generado_con': f"ia:{r['proveedor']}/{r['modelo']}"}


# ------------------------------------------------------------ exportación

def cv_a_docx(datos: Dict[str, Any]) -> bytes:
    from utils.cv_builder import construir_docx
    return construir_docx(datos)


def carta_a_docx(texto: str) -> bytes:
    from docx import Document
    from docx.shared import Pt
    d = Document()
    d.styles['Normal'].font.name = 'Calibri'
    d.styles['Normal'].font.size = Pt(11)
    for parrafo in texto.split('\n\n'):
        d.add_paragraph(parrafo)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _latin(texto: Any) -> str:
    """Helvetica estándar cubre cp1252 (tildes, ñ, viñetas); lo demás se sustituye."""
    return str(texto or '').replace('•', '•').encode('cp1252', 'replace').decode('cp1252')


def _pdf(flowables, titulo: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title=_latin(titulo), author='').build(flowables)
    return buf.getvalue()


def cv_a_pdf(d: Dict[str, Any]) -> bytes:
    """PDF de una columna con texto real (legible por ATS), sin tablas ni imágenes."""
    from xml.sax.saxutils import escape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import HRFlowable, Paragraph, Spacer
    base = ParagraphStyle('b', fontName='Helvetica', fontSize=10, leading=13)
    h = ParagraphStyle('h', parent=base, fontName='Helvetica-Bold', fontSize=11, spaceBefore=10, spaceAfter=2)
    p = lambda t, s=base: Paragraph(escape(_latin(t)), s)          # noqa: E731
    f = [Paragraph(escape(_latin(d.get('nombre', ''))).upper(),
                   ParagraphStyle('n', parent=base, fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=1))]
    if d.get('titular'):
        f.append(Paragraph(escape(_latin(d['titular'])), ParagraphStyle('t', parent=base, alignment=1, fontSize=11)))
    cont = ' • '.join(v for v in (d.get('contacto') or {}).values() if v)
    if cont:
        f.append(Paragraph(escape(_latin(cont)), ParagraphStyle('c', parent=base, alignment=1, fontSize=9)))
    f.append(HRFlowable(width='100%', thickness=1, spaceBefore=4, spaceAfter=2))
    if d.get('resumen'):
        f += [p('PERFIL', h), p(d['resumen'])]
    if d.get('experiencia'):
        f.append(p('EXPERIENCIA', h))
        for e in d['experiencia']:
            fechas = ' - '.join(x for x in (e.get('inicio'), e.get('fin')) if x)
            f.append(Paragraph(f"<b>{escape(_latin(e.get('cargo', '')))}</b> — {escape(_latin(e.get('empresa', '')))}"
                               + (f" ({escape(_latin(fechas))})" if fechas else ''), base))
            for l in e.get('logros', []):
                f.append(Paragraph('• ' + escape(_latin(l)), ParagraphStyle('l', parent=base, leftIndent=12)))
            f.append(Spacer(1, 4))
    if d.get('educacion'):
        f.append(p('FORMACIÓN', h))
        for e in d['educacion']:
            f.append(p(' — '.join(x for x in (e.get('titulo'), e.get('institucion'), e.get('anio')) if x)))
    for titulo, clave in (('HABILIDADES', 'habilidades_tecnicas'), ('COMPETENCIAS', 'habilidades_blandas'),
                          ('CERTIFICACIONES', 'certificaciones'), ('IDIOMAS', 'idiomas')):
        if d.get(clave):
            f += [p(titulo, h), p(', '.join(d[clave]))]
    return _pdf(f, f"CV {d.get('nombre', '')}")


def carta_a_pdf(texto: str) -> bytes:
    from xml.sax.saxutils import escape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer
    est = ParagraphStyle('c', fontName='Helvetica', fontSize=11, leading=15)
    f = []
    for parrafo in texto.split('\n\n'):
        f += [Paragraph(escape(_latin(parrafo)).replace('\n', '<br/>'), est), Spacer(1, 10)]
    return _pdf(f, 'Carta de presentación')
