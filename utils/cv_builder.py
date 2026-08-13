#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONSTRUCTOR DE CV OPTIMIZADO PARA ATS

Toma el texto plano de un CV, lo reestructura con ayuda de Ollama y lo
reconstruye en un DOCX que cumple las reglas de formato que exigen los
sistemas ATS (Applicant Tracking Systems) y que además se lee bien cuando
un reclutador lo revisa a mano.
"""

import io
import json
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ==================== REGLAS DE FORMATO ATS ====================
# Estas constantes son la "hoja de estilo" del CV generado. Los ATS parsean
# mal las fuentes decorativas, las tablas, las columnas y todo lo que viva en
# encabezados o pies de página, así que el documento se arma sin nada de eso.

FUENTE = 'Calibri'          # Fuente sans-serif estándar, legible por cualquier parser
TAM_NOMBRE = 20             # pt - el nombre es lo único grande del documento
TAM_TITULAR = 12            # pt - el cargo objetivo, debajo del nombre
TAM_CONTACTO = 10           # pt
TAM_SECCION = 12            # pt - títulos de sección, en mayúscula y negrita
TAM_CUERPO = 11             # pt - texto normal; por debajo de 10 se vuelve ilegible impreso
MARGEN_CM = 1.9             # cm en los cuatro lados
INTERLINEADO = 1.15
COLOR_TEXTO = (0x1a, 0x1a, 0x1a)

SECCIONES_ORDEN = [
    ('resumen', 'PERFIL PROFESIONAL'),
    ('experiencia', 'EXPERIENCIA PROFESIONAL'),
    ('educacion', 'EDUCACIÓN'),
    ('habilidades_tecnicas', 'HABILIDADES TÉCNICAS'),
    ('habilidades_blandas', 'HABILIDADES BLANDAS'),
    ('certificaciones', 'CERTIFICACIONES'),
    ('idiomas', 'IDIOMAS'),
]

# Estructura vacía: todo lo que el resto del módulo espera encontrar.
ESQUEMA_VACIO = {
    'nombre': '',
    'titular': '',
    'contacto': {'email': '', 'telefono': '', 'ciudad': '', 'linkedin': ''},
    'resumen': '',
    'experiencia': [],
    'educacion': [],
    'habilidades_tecnicas': [],
    'habilidades_blandas': [],
    'certificaciones': [],
    'idiomas': [],
}


PROMPT_REESTRUCTURA = """Eres un experto en reclutamiento y en optimización de CVs para sistemas ATS.

Recibes el texto crudo de un CV. Tu tarea es reescribirlo y devolverlo estructurado en JSON.

REGLAS OBLIGATORIAS:
1. NO inventes datos. Si un dato no está en el CV original, deja el campo vacío ("" o []).
   Nunca inventes cifras, empresas, fechas, títulos ni certificaciones.
2. Reescribe cada logro empezando con un VERBO DE ACCIÓN en pasado
   (Lideré, Desarrollé, Implementé, Reduje, Automaticé, Coordiné...).
3. Cuantifica SOLO con números que ya aparezcan en el texto original.
4. Cada logro es una línea de máximo 2 renglones, sin punto final innecesario.
5. Escribe los nombres de tecnologías tal como los busca un ATS
   (ejemplo: "Python", "SQL", "Power BI", "Excel avanzado").
6. El resumen tiene entre 2 y 4 líneas y menciona años de experiencia y área.
7. Todo en español, salvo nombres propios de tecnologías.
{contexto_cargo}
Devuelve ÚNICAMENTE este JSON, sin texto adicional:
{{
  "nombre": "",
  "titular": "cargo o perfil profesional en una línea",
  "contacto": {{"email": "", "telefono": "", "ciudad": "", "linkedin": ""}},
  "resumen": "",
  "experiencia": [
    {{"cargo": "", "empresa": "", "ubicacion": "", "inicio": "", "fin": "", "logros": ["", ""]}}
  ],
  "educacion": [{{"titulo": "", "institucion": "", "anio": ""}}],
  "habilidades_tecnicas": [],
  "habilidades_blandas": [],
  "certificaciones": [],
  "idiomas": []
}}

CV ORIGINAL:
{cv_text}
"""


def _texto_de_item(valor: Any) -> str:
    """Convierte a texto un elemento de una lista simple.

    Algunos modelos devuelven objetos donde el esquema pide strings
    (por ejemplo {"nombre": "Inglés", "nivel": "Básico"} en idiomas).
    Sin esto, el CV terminaría mostrando el diccionario en crudo.
    """
    if isinstance(valor, dict):
        partes = [str(v).strip() for v in valor.values() if str(v or '').strip()]
        return ' - '.join(partes)
    if isinstance(valor, (list, tuple)):
        return ' '.join(_texto_de_item(v) for v in valor).strip()
    return str(valor or '').strip()


def _normalizar(data: Any) -> Dict[str, Any]:
    """Rellena los campos faltantes y fuerza los tipos que espera el renderizador.

    El modelo a veces devuelve una lista donde se espera un string, o se salta
    campos completos. Sin esto, el renderizado revienta en runtime.
    """
    resultado = json.loads(json.dumps(ESQUEMA_VACIO))  # copia profunda

    if not isinstance(data, dict):
        return resultado

    for campo in ('nombre', 'titular', 'resumen'):
        resultado[campo] = _texto_de_item(data.get(campo, ''))

    contacto = data.get('contacto') or {}
    if isinstance(contacto, dict):
        for campo in resultado['contacto']:
            resultado['contacto'][campo] = str(contacto.get(campo, '') or '').strip()

    for campo in ('habilidades_tecnicas', 'habilidades_blandas', 'certificaciones', 'idiomas'):
        valor = data.get(campo) or []
        if isinstance(valor, str):
            valor = [v.strip() for v in re.split(r'[,;\n]', valor)]
        if isinstance(valor, list):
            resultado[campo] = [t for t in (_texto_de_item(v) for v in valor) if t]

    experiencia = data.get('experiencia') or []
    if isinstance(experiencia, list):
        for item in experiencia:
            if not isinstance(item, dict):
                continue
            logros = item.get('logros') or []
            if isinstance(logros, str):
                logros = [logros]
            resultado['experiencia'].append({
                'cargo': str(item.get('cargo', '') or '').strip(),
                'empresa': str(item.get('empresa', '') or '').strip(),
                'ubicacion': str(item.get('ubicacion', '') or '').strip(),
                'inicio': str(item.get('inicio', '') or '').strip(),
                'fin': str(item.get('fin', '') or '').strip(),
                'logros': [t for t in (_texto_de_item(l) for l in logros) if t],
            })

    educacion = data.get('educacion') or []
    if isinstance(educacion, list):
        for item in educacion:
            if not isinstance(item, dict):
                continue
            resultado['educacion'].append({
                'titulo': str(item.get('titulo', '') or '').strip(),
                'institucion': str(item.get('institucion', '') or '').strip(),
                'anio': str(item.get('anio', '') or '').strip(),
            })

    return resultado


def estructurar_con_ollama(bot, cv_text: str, cargo_objetivo: str = '') -> Dict[str, Any]:
    """Pide a Ollama que reestructure el CV y devuelve el JSON normalizado.

    Lanza excepción si Ollama falla; el que llama decide el fallback.
    """
    contexto_cargo = ''
    if cargo_objetivo:
        contexto_cargo = (
            f'8. El CV apunta al cargo de "{cargo_objetivo}". Prioriza y redacta '
            'las habilidades y logros que sean relevantes para ese cargo, pero sin '
            'inventar experiencia que no exista.\n'
        )

    prompt = PROMPT_REESTRUCTURA.format(
        contexto_cargo=contexto_cargo,
        cv_text=cv_text[:12000],  # límite defensivo: CVs muy largos desbordan el contexto
    )

    respuesta = bot.call_ollama(prompt, fmt='json', options={'num_ctx': 8192, 'temperature': 0.2})

    try:
        return _normalizar(json.loads(respuesta))
    except json.JSONDecodeError:
        # Algunos modelos envuelven el JSON en texto o en un bloque markdown
        match = re.search(r'\{.*\}', respuesta, re.DOTALL)
        if match:
            return _normalizar(json.loads(match.group()))
        raise ValueError('Ollama no devolvió un JSON válido')


# ==================== FALLBACK SIN IA ====================

_RE_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
_RE_TELEFONO = re.compile(r'(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,3}\)[\s-]?)?\d{3}[\s-]?\d{3}[\s-]?\d{2,4}')
_RE_LINKEDIN = re.compile(r'(?:linkedin\.com/in/|linkedin:\s*)([\w-]+)', re.IGNORECASE)

_ENCABEZADOS = {
    'resumen': ('perfil', 'resumen', 'objetivo', 'acerca de', 'sobre mi', 'sobre mí'),
    'experiencia': ('experiencia', 'trayectoria', 'historial laboral'),
    'educacion': ('educacion', 'educación', 'formacion', 'formación', 'estudios', 'academic'),
    'habilidades_tecnicas': ('habilidades', 'competencias', 'skills', 'conocimientos', 'tecnologias', 'tecnologías'),
    'certificaciones': ('certificacion', 'certificación', 'certificaciones', 'cursos', 'diplomados'),
    'idiomas': ('idioma', 'idiomas', 'languages'),
}


def estructurar_sin_ia(cv_text: str) -> Dict[str, Any]:
    """Reestructura el CV troceándolo por encabezados, cuando Ollama no está disponible.

    No reescribe el contenido —eso solo lo hace el LLM— pero sí produce un
    documento con el formato ATS correcto, que ya es la mitad del problema.
    """
    datos = json.loads(json.dumps(ESQUEMA_VACIO))
    lineas = [l.strip() for l in cv_text.splitlines()]

    email = _RE_EMAIL.search(cv_text)
    if email:
        datos['contacto']['email'] = email.group()

    linkedin = _RE_LINKEDIN.search(cv_text)
    if linkedin:
        datos['contacto']['linkedin'] = f'linkedin.com/in/{linkedin.group(1)}'

    # El teléfono se busca solo en la cabecera para no capturar años ni cifras de logros
    telefono = _RE_TELEFONO.search('\n'.join(lineas[:15]))
    if telefono and len(re.sub(r'\D', '', telefono.group())) >= 7:
        datos['contacto']['telefono'] = telefono.group().strip()

    # El nombre suele ser la primera línea con contenido y sin datos de contacto
    for linea in lineas[:8]:
        if linea and not _RE_EMAIL.search(linea) and len(linea.split()) <= 6 and len(linea) > 3:
            datos['nombre'] = linea
            break

    # Trocear el cuerpo por encabezados de sección
    seccion_actual = None
    buffer: Dict[str, List[str]] = {clave: [] for clave in _ENCABEZADOS}

    for linea in lineas:
        if not linea:
            continue
        limpia = re.sub(r'[^\w\sáéíóúñ]', '', linea.lower()).strip()
        detectada = None
        for clave, alias in _ENCABEZADOS.items():
            # Un encabezado es corto y empieza con alguna de sus palabras clave
            if len(limpia) <= 40 and any(limpia.startswith(a) for a in alias):
                detectada = clave
                break
        if detectada:
            seccion_actual = detectada
            continue
        if seccion_actual:
            buffer[seccion_actual].append(linea)

    datos['resumen'] = ' '.join(buffer['resumen'])[:600]

    for clave in ('habilidades_tecnicas', 'certificaciones', 'idiomas'):
        items: List[str] = []
        for linea in buffer[clave]:
            items.extend(re.split(r'[,;•·|]|\s{3,}', linea))
        datos[clave] = [i.strip(' -•\t') for i in items if len(i.strip(' -•\t')) > 1][:20]

    # La experiencia se agrupa por bloques: la primera línea es el cargo,
    # las viñetas siguientes son los logros.
    bloque = None
    for linea in buffer['experiencia']:
        es_vineta = bool(re.match(r'^[-•*·▪]', linea))
        if not es_vineta:
            if bloque:
                datos['experiencia'].append(bloque)
            bloque = {'cargo': linea, 'empresa': '', 'ubicacion': '', 'inicio': '', 'fin': '', 'logros': []}
            # Separar "Cargo - Empresa" o "Cargo | Empresa" si viene junto
            partes = re.split(r'\s+[-|–]\s+', linea, maxsplit=1)
            if len(partes) == 2:
                bloque['cargo'], bloque['empresa'] = partes[0].strip(), partes[1].strip()
            # Extraer el rango de fechas si está en la misma línea
            anios = re.findall(r'(?:19|20)\d{2}', linea)
            if anios:
                bloque['inicio'] = anios[0]
                bloque['fin'] = anios[1] if len(anios) > 1 else 'Actual'
                # Quitar el rango del cargo y la empresa: si no, las fechas
                # salen duplicadas en el documento final
                for campo in ('cargo', 'empresa'):
                    limpio = re.sub(
                        r'[|(\[]?\s*(?:19|20)\d{2}\s*[-–—/]?\s*'
                        r'(?:(?:19|20)\d{2}|actual|presente|present)?\s*[)\]]?\s*$',
                        '', bloque[campo], flags=re.IGNORECASE)
                    bloque[campo] = limpio.strip(' -–—|,')
        elif bloque:
            bloque['logros'].append(linea.lstrip(' -•*·▪\t'))
    if bloque:
        datos['experiencia'].append(bloque)

    for linea in buffer['educacion']:
        if len(linea) < 3:
            continue
        anio = re.search(r'(?:19|20)\d{2}', linea)
        datos['educacion'].append({
            'titulo': linea.strip(' -•\t'),
            'institucion': '',
            'anio': anio.group() if anio else '',
        })

    return datos


# ==================== RENDERIZADO DOCX ====================

def construir_docx(datos: Dict[str, Any]) -> bytes:
    """Arma el DOCX aplicando las reglas de formato ATS. Devuelve los bytes."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()

    # Fuente base de todo el documento
    normal = doc.styles['Normal']
    normal.font.name = FUENTE
    normal.font.size = Pt(TAM_CUERPO)
    normal.font.color.rgb = RGBColor(*COLOR_TEXTO)
    normal.paragraph_format.line_spacing = INTERLINEADO
    normal.paragraph_format.space_after = Pt(4)

    for seccion in doc.sections:
        seccion.top_margin = Cm(MARGEN_CM)
        seccion.bottom_margin = Cm(MARGEN_CM)
        seccion.left_margin = Cm(MARGEN_CM)
        seccion.right_margin = Cm(MARGEN_CM)

    def parrafo(texto='', tam=TAM_CUERPO, negrita=False, alineacion=None, espacio_antes=0, espacio_despues=4):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(espacio_antes)
        p.paragraph_format.space_after = Pt(espacio_despues)
        p.paragraph_format.line_spacing = INTERLINEADO
        if alineacion is not None:
            p.alignment = alineacion
        if texto:
            run = p.add_run(texto)
            run.font.name = FUENTE
            run.font.size = Pt(tam)
            run.font.bold = negrita
            run.font.color.rgb = RGBColor(*COLOR_TEXTO)
        return p

    def titulo_seccion(texto):
        # Título en mayúscula + línea inferior. La línea es un borde de párrafo,
        # no una tabla ni una imagen, así que el ATS simplemente la ignora.
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        p = parrafo(texto.upper(), tam=TAM_SECCION, negrita=True, espacio_antes=12, espacio_despues=4)
        borde = OxmlElement('w:pBdr')
        linea = OxmlElement('w:bottom')
        linea.set(qn('w:val'), 'single')
        linea.set(qn('w:sz'), '6')
        linea.set(qn('w:space'), '2')
        linea.set(qn('w:color'), '999999')
        borde.append(linea)
        p._p.get_or_add_pPr().append(borde)
        return p

    def vineta(texto):
        # 'List Bullet' es una lista nativa de Word: los parsers la leen como
        # viñeta real, a diferencia de un guion escrito a mano.
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = INTERLINEADO
        run = p.add_run(texto)
        run.font.name = FUENTE
        run.font.size = Pt(TAM_CUERPO)
        run.font.color.rgb = RGBColor(*COLOR_TEXTO)
        return p

    # --- Encabezado: nombre, titular y contacto en líneas de texto plano ---
    if datos.get('nombre'):
        parrafo(datos['nombre'], tam=TAM_NOMBRE, negrita=True,
                alineacion=WD_ALIGN_PARAGRAPH.CENTER, espacio_despues=2)

    if datos.get('titular'):
        parrafo(datos['titular'], tam=TAM_TITULAR,
                alineacion=WD_ALIGN_PARAGRAPH.CENTER, espacio_despues=2)

    contacto = datos.get('contacto', {})
    partes_contacto = [contacto.get(c) for c in ('email', 'telefono', 'ciudad', 'linkedin')]
    partes_contacto = [p for p in partes_contacto if p]
    if partes_contacto:
        parrafo(' | '.join(partes_contacto), tam=TAM_CONTACTO,
                alineacion=WD_ALIGN_PARAGRAPH.CENTER, espacio_despues=6)

    # --- Cuerpo ---
    if datos.get('resumen'):
        titulo_seccion('Perfil profesional')
        parrafo(datos['resumen'])

    if datos.get('experiencia'):
        titulo_seccion('Experiencia profesional')
        for exp in datos['experiencia']:
            encabezado = exp.get('cargo', '')
            if exp.get('empresa'):
                encabezado = f"{encabezado} — {exp['empresa']}" if encabezado else exp['empresa']
            if encabezado:
                parrafo(encabezado, negrita=True, espacio_antes=6, espacio_despues=0)

            meta = [x for x in (exp.get('ubicacion'), _rango_fechas(exp)) if x]
            if meta:
                parrafo(' | '.join(meta), tam=TAM_CONTACTO, espacio_despues=2)

            for logro in exp.get('logros', []):
                vineta(logro)

    if datos.get('educacion'):
        titulo_seccion('Educación')
        for edu in datos['educacion']:
            linea = edu.get('titulo', '')
            if edu.get('institucion'):
                linea = f"{linea} — {edu['institucion']}" if linea else edu['institucion']
            if edu.get('anio'):
                linea = f"{linea} ({edu['anio']})" if linea else edu['anio']
            if linea:
                parrafo(linea, espacio_despues=2)

    # Las habilidades van en una línea separada por comas: es el formato que
    # mejor indexan los ATS al extraer palabras clave.
    for clave, titulo in (('habilidades_tecnicas', 'Habilidades técnicas'),
                          ('habilidades_blandas', 'Habilidades blandas')):
        if datos.get(clave):
            titulo_seccion(titulo)
            parrafo(', '.join(datos[clave]))

    if datos.get('certificaciones'):
        titulo_seccion('Certificaciones')
        for cert in datos['certificaciones']:
            vineta(cert)

    if datos.get('idiomas'):
        titulo_seccion('Idiomas')
        parrafo(', '.join(datos['idiomas']))

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _rango_fechas(exp: Dict[str, Any]) -> str:
    """Devuelve 'inicio - fin' con lo que haya disponible."""
    inicio, fin = exp.get('inicio', ''), exp.get('fin', '')
    if inicio and fin:
        return f'{inicio} - {fin}'
    return inicio or fin or ''


# ==================== PREVISUALIZACIÓN HTML ====================

def _escapar(texto: Any) -> str:
    from html import escape
    return escape(str(texto or ''))


def construir_preview_html(datos: Dict[str, Any]) -> str:
    """Genera la vista previa que se muestra en el navegador.

    Replica el formato del DOCX (misma fuente, mismas proporciones) para que
    lo que el usuario ve sea lo que descarga.
    """
    partes = [
        f'<div class="cv-preview" style="font-family: {FUENTE}, Arial, sans-serif; '
        f'color: #1a1a1a; line-height: {INTERLINEADO}; background: #fff; padding: 18px;">'
    ]

    if datos.get('nombre'):
        partes.append(
            f'<div style="text-align:center; font-size:{TAM_NOMBRE}px; font-weight:700;">'
            f'{_escapar(datos["nombre"])}</div>'
        )
    if datos.get('titular'):
        partes.append(
            f'<div style="text-align:center; font-size:{TAM_TITULAR}px;">'
            f'{_escapar(datos["titular"])}</div>'
        )

    contacto = [datos.get('contacto', {}).get(c) for c in ('email', 'telefono', 'ciudad', 'linkedin')]
    contacto = [_escapar(c) for c in contacto if c]
    if contacto:
        partes.append(
            f'<div style="text-align:center; font-size:{TAM_CONTACTO}px; margin-bottom:10px;">'
            f'{" | ".join(contacto)}</div>'
        )

    def titulo(texto):
        return (
            f'<div style="font-size:{TAM_SECCION}px; font-weight:700; text-transform:uppercase; '
            f'border-bottom:1px solid #999; margin:14px 0 6px;">{_escapar(texto)}</div>'
        )

    if datos.get('resumen'):
        partes.append(titulo('Perfil profesional'))
        partes.append(f'<p style="margin:0 0 6px; font-size:{TAM_CUERPO}px;">{_escapar(datos["resumen"])}</p>')

    if datos.get('experiencia'):
        partes.append(titulo('Experiencia profesional'))
        for exp in datos['experiencia']:
            encabezado = exp.get('cargo', '')
            if exp.get('empresa'):
                encabezado = f'{encabezado} — {exp["empresa"]}' if encabezado else exp['empresa']
            if encabezado:
                partes.append(
                    f'<div style="font-weight:700; font-size:{TAM_CUERPO}px; margin-top:8px;">'
                    f'{_escapar(encabezado)}</div>'
                )
            meta = [x for x in (exp.get('ubicacion'), _rango_fechas(exp)) if x]
            if meta:
                partes.append(
                    f'<div style="font-size:{TAM_CONTACTO}px; color:#555;">'
                    f'{_escapar(" | ".join(meta))}</div>'
                )
            if exp.get('logros'):
                items = ''.join(f'<li>{_escapar(l)}</li>' for l in exp['logros'])
                partes.append(
                    f'<ul style="margin:4px 0 0 18px; padding:0; font-size:{TAM_CUERPO}px;">{items}</ul>'
                )

    if datos.get('educacion'):
        partes.append(titulo('Educación'))
        for edu in datos['educacion']:
            linea = edu.get('titulo', '')
            if edu.get('institucion'):
                linea = f'{linea} — {edu["institucion"]}' if linea else edu['institucion']
            if edu.get('anio'):
                linea = f'{linea} ({edu["anio"]})' if linea else edu['anio']
            if linea:
                partes.append(f'<div style="font-size:{TAM_CUERPO}px;">{_escapar(linea)}</div>')

    for clave, nombre in (('habilidades_tecnicas', 'Habilidades técnicas'),
                          ('habilidades_blandas', 'Habilidades blandas'),
                          ('idiomas', 'Idiomas')):
        if datos.get(clave):
            partes.append(titulo(nombre))
            partes.append(
                f'<p style="margin:0; font-size:{TAM_CUERPO}px;">'
                f'{_escapar(", ".join(datos[clave]))}</p>'
            )

    if datos.get('certificaciones'):
        partes.append(titulo('Certificaciones'))
        items = ''.join(f'<li>{_escapar(c)}</li>' for c in datos['certificaciones'])
        partes.append(f'<ul style="margin:4px 0 0 18px; padding:0; font-size:{TAM_CUERPO}px;">{items}</ul>')

    partes.append('</div>')
    return ''.join(partes)


def resumen_formato() -> List[str]:
    """Reglas de formato aplicadas, para mostrárselas al usuario."""
    return [
        f'Fuente {FUENTE} {TAM_CUERPO}pt en el cuerpo y {TAM_NOMBRE}pt en el nombre',
        f'Márgenes de {MARGEN_CM} cm e interlineado {INTERLINEADO}',
        'Sin tablas, columnas, imágenes ni cuadros de texto (los ATS no los leen)',
        'Sin encabezado ni pie de página: los datos de contacto van en el cuerpo',
        'Títulos de sección en mayúscula sostenida y con nombres estándar',
        'Viñetas nativas de Word, no guiones escritos a mano',
        'Habilidades en línea separadas por comas para facilitar la extracción de palabras clave',
    ]


def generar_cv_optimizado(bot, cv_text: str, cargo_objetivo: str = '') -> Dict[str, Any]:
    """Punto de entrada: reestructura el CV y devuelve datos + preview.

    Usa Ollama si está disponible; si no, cae al troceo heurístico para que la
    función siga entregando un documento bien formateado.
    """
    if not cv_text or not cv_text.strip():
        raise ValueError('No hay texto de CV para procesar')

    modo = 'ia'
    if bot is not None and bot.check_ollama_status():
        try:
            datos = estructurar_con_ollama(bot, cv_text, cargo_objetivo)
        except Exception as e:
            logger.warning(f'Ollama falló al reestructurar el CV, usando fallback: {e}')
            datos = estructurar_sin_ia(cv_text)
            modo = 'basico'
    else:
        datos = estructurar_sin_ia(cv_text)
        modo = 'basico'

    # Si el modelo devolvió algo vacío, el fallback al menos conserva el contenido
    if not datos.get('experiencia') and not datos.get('resumen') and modo == 'ia':
        logger.warning('Ollama devolvió un CV vacío, usando fallback heurístico')
        datos = estructurar_sin_ia(cv_text)
        modo = 'basico'

    return {
        'datos': datos,
        'preview_html': construir_preview_html(datos),
        'reglas': resumen_formato(),
        'modo': modo,
    }
