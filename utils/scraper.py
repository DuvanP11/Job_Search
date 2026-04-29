#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER DE PORTALES DE EMPLEO
Módulo para scraping de ofertas laborales con filtros avanzados
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BuscadorEmpleos:
    """Clase principal para búsqueda de empleos en múltiples portales"""
    
    def __init__(self, config_busqueda, keywords, portales):
        """
        Inicializar buscador
        
        Args:
            config_busqueda: Diccionario con configuración de búsqueda
            keywords: Diccionario con keywords (incluir, excluir, bonus)
            portales: Diccionario con portales activos
        """
        self.config = config_busqueda
        self.keywords = keywords
        self.portales = portales
        self.ofertas_encontradas = []
        
        # Configurar sesión HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def buscar_computrabajo(self, titulo, ubicacion):
        """Buscar ofertas en Computrabajo.com.co - Versión mejorada"""
        logger.info(f"🔍 Buscando en Computrabajo: {titulo} - {ubicacion}")
        
        try:
            # Construir URL - probar con y sin ubicación
            titulo_limpio = titulo.replace(' ', '-').lower()
            
            # Intentar primero con título solo
            url = f"https://www.computrabajo.com.co/trabajo-de-{titulo_limpio}"
            logger.info(f"📍 URL: {url}")
            
            response = self.session.get(url, timeout=7)
            logger.info(f"📡 Status: {response.status_code}")
            
            # Si falla, intentar URL alternativa
            if response.status_code != 200:
                # Intentar con búsqueda genérica
                url = f"https://www.computrabajo.com.co/ofertas-de-trabajo/"
                logger.info(f"📍 URL alternativa: {url}")
                response = self.session.get(url, timeout=7)
                
                if response.status_code != 200:
                    logger.warning(f"❌ Error {response.status_code}")
                    return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar con MÚLTIPLES selectores
            ofertas = []
            
            # Selector 1: Articles con data-test
            ofertas.extend(soup.find_all('article', attrs={'data-test': 'offer-card'}))
            
            # Selector 2: Articles con clase
            ofertas.extend(soup.find_all('article', class_=re.compile('oferta|offer|job', re.I)))
            
            # Selector 3: Divs que parezcan ofertas
            ofertas.extend(soup.find_all('div', class_=re.compile('bRS|box_offer|oferta', re.I)))
            
            # Selector 4: Links que contengan "oferta" en href
            todos_links = soup.find_all('a', href=re.compile(r'/ofertas-de-trabajo/', re.I))
            
            logger.info(f"📊 Elementos encontrados - Articles: {len(ofertas)}, Links: {len(todos_links)}")
            
            ofertas_agregadas = 0
            elementos_procesados = set()  # Evitar duplicados
            
            # Procesar articles/divs
            for oferta in ofertas[:30]:  # Balanceado
                try:
                    # Buscar título con múltiples selectores
                    titulo_elem = (
                        oferta.find('a', class_=re.compile('js-o-link|title|titulo', re.I)) or
                        oferta.find('h2') or
                        oferta.find('h3') or
                        oferta.find('a', href=True)
                    )
                    
                    if not titulo_elem:
                        continue
                    
                    texto_titulo = titulo_elem.text.strip()
                    href = titulo_elem.get('href', '')
                    
                    # Evitar duplicados
                    if texto_titulo in elementos_procesados or len(texto_titulo) < 10:
                        continue
                    
                    elementos_procesados.add(texto_titulo)
                    
                    # Construir link
                    if href:
                        link = href if href.startswith('http') else f'https://www.computrabajo.com.co{href}'
                    else:
                        continue
                    
                    # Buscar empresa
                    empresa_elem = (
                        oferta.find('p', class_=re.compile('empresa|company', re.I)) or
                        oferta.find('span', class_=re.compile('empresa|company', re.I))
                    )
                    
                    # Buscar ubicación REAL
                    ubicacion_elem = (
                        oferta.find('p', class_=re.compile('ubicacion|location|lugar', re.I)) or
                        oferta.find('span', class_=re.compile('ubicacion|location|lugar', re.I)) or
                        oferta.find(text=re.compile(r'Bogotá|Medellín|Cali|Barranquilla|Cartagena|Bucaramanga', re.I))
                    )
                    
                    # Extraer texto de ubicación
                    ubicacion_real = ubicacion  # Default: usar la buscada
                    if ubicacion_elem:
                        if hasattr(ubicacion_elem, 'text'):
                            ubicacion_real = ubicacion_elem.text.strip()
                        elif isinstance(ubicacion_elem, str):
                            ubicacion_real = ubicacion_elem.strip()
                    
                    # Filtrar por ubicación si no coincide
                    if ubicacion.lower() not in ubicacion_real.lower() and ubicacion.lower() != 'colombia' and ubicacion.lower() != 'remoto':
                        logger.debug(f"⚠️ Ubicación no coincide: buscada='{ubicacion}', real='{ubicacion_real}'")
                        continue
                    
                    # Crear oferta
                    oferta_data = {
                        'titulo': texto_titulo[:150],
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion_real,  # Usar ubicación REAL
                        'link': link,
                        'portal': 'Computrabajo',
                        'fecha_publicacion': datetime.now().strftime('%Y-%m-%d'),
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': '',
                        'score': 50
                    }
                    
                    self.ofertas_encontradas.append(oferta_data)
                    ofertas_agregadas += 1
                    
                    if ofertas_agregadas >= 10:
                        break
                
                except Exception as e:
                    logger.debug(f"Error en article: {str(e)}")
                    continue
            
            # Si aún no tenemos suficientes, procesar links directos
            if ofertas_agregadas < 10:
                for link in todos_links[:30]:  # Balanceado
                    try:
                        texto = link.text.strip()
                        href = link.get('href', '')
                        
                        if len(texto) < 15 or texto in elementos_procesados:
                            continue
                        
                        elementos_procesados.add(texto)
                        
                        oferta_data = {
                            'titulo': texto[:150],
                            'empresa': 'Computrabajo',
                            'ubicacion': ubicacion,
                            'link': href if href.startswith('http') else f'https://www.computrabajo.com.co{href}',
                            'portal': 'Computrabajo',
                            'fecha_publicacion': datetime.now().strftime('%Y-%m-%d'),
                            'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                            'descripcion': '',
                            'score': 50
                        }
                        
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_agregadas += 1
                        
                        if ofertas_agregadas >= 10:
                            break
                    
                    except Exception as e:
                        continue
            
            logger.info(f"✅ {ofertas_agregadas} ofertas de Computrabajo")
            
        except Exception as e:
            logger.error(f"❌ Error Computrabajo: {str(e)}")
    
    def buscar_elempleo(self, titulo, ubicacion):
        """Buscar ofertas en ElEmpleo.com"""
        logger.info(f"🔍 Buscando en ElEmpleo: {titulo} - {ubicacion}")
        
        try:
            query = f"{titulo} {ubicacion}"
            url = f"https://www.elempleo.com/co/ofertas-empleo/?buscar={quote_plus(query)}"
            
            response = self.session.get(url, timeout=7)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en ElEmpleo")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='resultado') or soup.find_all('article', class_='job-card')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:10]:
                try:
                    titulo_elem = oferta.find('a', class_='js-offer-title') or oferta.find('h2')
                    empresa_elem = oferta.find('p', class_='company') or oferta.find('span', class_='company-name')
                    fecha_elem = oferta.find('time') or oferta.find('span', class_='date')
                    
                    if not titulo_elem:
                        continue
                    
                    link = titulo_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://www.elempleo.com' + link
                    
                    fecha_publicacion = self._parsear_fecha(fecha_elem.text.strip() if fecha_elem else '')
                    
                    oferta_data = {
                        'titulo': titulo_elem.text.strip(),
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion,
                        'link': link,
                        'portal': 'ElEmpleo',
                        'fecha_publicacion': fecha_publicacion,
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': ''
                    }
                    
                    if self.aplicar_filtros(oferta_data):
                        oferta_data['score'] = self.calcular_score(oferta_data)
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_procesadas += 1
                
                except Exception as e:
                    logger.debug(f"Error procesando oferta: {str(e)}")
                    continue
            
            logger.info(f"✅ {ofertas_procesadas} ofertas válidas de ElEmpleo")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Error en ElEmpleo: {str(e)}")
    
    def buscar_magneto(self, titulo, ubicacion):
        """Buscar ofertas en Magneto365.com"""
        logger.info(f"🔍 Buscando en Magneto365: {titulo} - {ubicacion}")
        
        try:
            query = f"{titulo} {ubicacion}"
            url = f"https://www.magneto365.com/co/ofertas?q={quote_plus(query)}"
            
            response = self.session.get(url, timeout=7)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Magneto365")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='offer-card') or soup.find_all('article', class_='job-listing')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:10]:
                try:
                    titulo_elem = oferta.find('h3') or oferta.find('a', class_='offer-title')
                    empresa_elem = oferta.find('span', class_='company') or oferta.find('p', class_='empresa')
                    link_elem = oferta.find('a')
                    fecha_elem = oferta.find('time') or oferta.find('span', class_='date')
                    
                    if not titulo_elem:
                        continue
                    
                    link = link_elem.get('href', '') if link_elem else ''
                    if link and not link.startswith('http'):
                        link = 'https://www.magneto365.com' + link
                    
                    fecha_publicacion = self._parsear_fecha(fecha_elem.text.strip() if fecha_elem else '')
                    
                    oferta_data = {
                        'titulo': titulo_elem.text.strip(),
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion,
                        'link': link,
                        'portal': 'Magneto365',
                        'fecha_publicacion': fecha_publicacion,
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': ''
                    }
                    
                    if self.aplicar_filtros(oferta_data):
                        oferta_data['score'] = self.calcular_score(oferta_data)
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_procesadas += 1
                
                except Exception as e:
                    logger.debug(f"Error procesando oferta: {str(e)}")
                    continue
            
            logger.info(f"✅ {ofertas_procesadas} ofertas válidas de Magneto365")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Error en Magneto365: {str(e)}")
    
    def buscar_indeed(self, titulo, ubicacion):
        """Buscar ofertas en Indeed Colombia"""
        logger.info(f"🔍 Buscando en Indeed: {titulo} - {ubicacion}")
        
        try:
            # Construir URL de búsqueda para Indeed Colombia
            query = quote_plus(titulo)
            loc = quote_plus(ubicacion) if ubicacion != 'Remoto' else ''
            url = f"https://co.indeed.com/jobs?q={query}&l={loc}"
            
            response = self.session.get(url, timeout=7)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Indeed")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas (Indeed usa divs con clase específica)
            ofertas = soup.find_all('div', class_='job_seen_beacon') or soup.find_all('div', class_='jobsearch-SerpJobCard')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:10]:
                try:
                    titulo_elem = oferta.find('h2', class_='jobTitle') or oferta.find('a', class_='jcs-JobTitle')
                    empresa_elem = oferta.find('span', class_='companyName') or oferta.find('span', attrs={'data-testid': 'company-name'})
                    ubicacion_elem = oferta.find('div', class_='companyLocation') or oferta.find('div', attrs={'data-testid': 'text-location'})
                    link_elem = oferta.find('a', class_='jcs-JobTitle') or titulo_elem
                    fecha_elem = oferta.find('span', class_='date')
                    
                    if not titulo_elem:
                        continue
                    
                    link = link_elem.get('href', '') if link_elem else ''
                    if link and not link.startswith('http'):
                        link = 'https://co.indeed.com' + link
                    
                    fecha_publicacion = self._parsear_fecha(fecha_elem.text.strip() if fecha_elem else '')
                    
                    oferta_data = {
                        'titulo': titulo_elem.text.strip(),
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion_elem.text.strip() if ubicacion_elem else ubicacion,
                        'link': link,
                        'portal': 'Indeed',
                        'fecha_publicacion': fecha_publicacion,
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': ''
                    }
                    
                    if self.aplicar_filtros(oferta_data):
                        oferta_data['score'] = self.calcular_score(oferta_data)
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_procesadas += 1
                
                except Exception as e:
                    logger.debug(f"Error procesando oferta: {str(e)}")
                    continue
            
            logger.info(f"✅ {ofertas_procesadas} ofertas válidas de Indeed")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Error en Indeed: {str(e)}")
    
    def buscar_trabajando(self, titulo, ubicacion):
        """Buscar ofertas en Trabajando.com Colombia"""
        logger.info(f"🔍 Buscando en Trabajando.com: {titulo} - {ubicacion}")
        
        try:
            query = quote_plus(titulo)
            url = f"https://www.trabajando.com.co/empleos?q={query}"
            
            response = self.session.get(url, timeout=7)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Trabajando.com")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='job-item') or soup.find_all('article', class_='offer')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:10]:
                try:
                    titulo_elem = oferta.find('h3') or oferta.find('a', class_='job-title')
                    empresa_elem = oferta.find('span', class_='company')
                    ubicacion_elem = oferta.find('span', class_='location')
                    link_elem = oferta.find('a')
                    fecha_elem = oferta.find('time') or oferta.find('span', class_='date')
                    
                    if not titulo_elem:
                        continue
                    
                    link = link_elem.get('href', '') if link_elem else ''
                    if link and not link.startswith('http'):
                        link = 'https://www.trabajando.com.co' + link
                    
                    fecha_publicacion = self._parsear_fecha(fecha_elem.text.strip() if fecha_elem else '')
                    
                    oferta_data = {
                        'titulo': titulo_elem.text.strip(),
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion_elem.text.strip() if ubicacion_elem else ubicacion,
                        'link': link,
                        'portal': 'Trabajando.com',
                        'fecha_publicacion': fecha_publicacion,
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': ''
                    }
                    
                    if self.aplicar_filtros(oferta_data):
                        oferta_data['score'] = self.calcular_score(oferta_data)
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_procesadas += 1
                
                except Exception as e:
                    logger.debug(f"Error procesando oferta: {str(e)}")
                    continue
            
            logger.info(f"✅ {ofertas_procesadas} ofertas válidas de Trabajando.com")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Error en Trabajando.com: {str(e)}")
    
    def buscar_linkedin(self, titulo, ubicacion):
        """Buscar ofertas en LinkedIn Jobs - DUMMY por ahora"""
        logger.info(f"🔍 LinkedIn: {titulo} - {ubicacion} (SKIP - en desarrollo)")
        # No hacer nada por ahora para evitar crashes
        return
    
    def buscar_serviciodeempleo(self, titulo, ubicacion):
        """Buscar en Servicio de Empleo - DUMMY por ahora"""
        logger.info(f"🔍 Servicio de Empleo: {titulo} - {ubicacion} (SKIP - en desarrollo)")
        # No hacer nada por ahora para evitar crashes
        return
    
    def buscar_talentbox(self, titulo, ubicacion):
        """Buscar en Talentbox - DUMMY por ahora"""
        logger.info(f"🔍 Talentbox: {titulo} - {ubicacion} (SKIP - en desarrollo)")
        # No hacer nada por ahora para evitar crashes
        return
    
    def buscar_colsubsidio(self, titulo, ubicacion):
        """Buscar en Colsubsidio - DUMMY por ahora"""
        logger.info(f"🔍 Colsubsidio: {titulo} - {ubicacion} (SKIP - en desarrollo)")
        # No hacer nada por ahora para evitar crashes
        return
    
    def buscar_unmejorempleo(self, titulo, ubicacion):
        """Buscar en UnMejorEmpleo - DUMMY por ahora"""
        logger.info(f"🔍 UnMejorEmpleo: {titulo} - {ubicacion} (SKIP - en desarrollo)")
        # No hacer nada por ahora para evitar crashes
        return
    
    def _parsear_fecha(self, texto_fecha):
        """
        Parsear texto de fecha a formato YYYY-MM-DD
        
        Args:
            texto_fecha: Texto con fecha relativa o absoluta
            
        Returns:
            str: Fecha en formato YYYY-MM-DD
        """
        if not texto_fecha:
            return datetime.now().strftime('%Y-%m-%d')
        
        texto_fecha = texto_fecha.lower().strip()
        hoy = datetime.now()
        
        # Hoy
        if 'hoy' in texto_fecha or 'today' in texto_fecha:
            return hoy.strftime('%Y-%m-%d')
        
        # Ayer
        if 'ayer' in texto_fecha or 'yesterday' in texto_fecha:
            return (hoy - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Hace X días/horas
        match_dias = re.search(r'hace\s+(\d+)\s+día', texto_fecha)
        if match_dias:
            dias = int(match_dias.group(1))
            return (hoy - timedelta(days=dias)).strftime('%Y-%m-%d')
        
        match_horas = re.search(r'hace\s+(\d+)\s+hora', texto_fecha)
        if match_horas:
            return hoy.strftime('%Y-%m-%d')
        
        # Fecha absoluta DD/MM/YYYY o similar
        match_fecha = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', texto_fecha)
        if match_fecha:
            dia, mes, año = match_fecha.groups()
            if len(año) == 2:
                año = '20' + año
            try:
                fecha = datetime(int(año), int(mes), int(dia))
                return fecha.strftime('%Y-%m-%d')
            except:
                pass
        
        # Por defecto, retornar fecha actual
        return hoy.strftime('%Y-%m-%d')
    
    def aplicar_filtros(self, oferta):
        """Aplicar filtros de keywords, escolaridad y nivel de inglés a una oferta"""
        texto_completo = f"{oferta['titulo']} {oferta.get('descripcion', '')}".lower()
        
        # Filtro de escolaridad (si está configurado y no es "todos")
        escolaridad_requerida = self.config.get('escolaridad', 'todos')
        if escolaridad_requerida and escolaridad_requerida != 'todos':
            # Mapeo de términos de búsqueda por nivel educativo
            terminos_escolaridad = {
                'profesional': ['profesional', 'universitario', 'university', 'degree', 'pregrado'],
                'tecnologo': ['tecnólogo', 'tecnologo', 'tecnológica'],
                'tecnico': ['técnico', 'tecnico', 'technical'],
                'bachiller': ['bachiller', 'secundaria', 'high school'],
                'posgrado': ['posgrado', 'postgrado', 'postgraduate', 'especialización'],
                'maestria': ['maestría', 'maestria', 'master', 'msc', 'm.sc'],
                'doctorado': ['doctorado', 'phd', 'ph.d', 'doctor']
            }
            
            # Buscar si menciona la escolaridad requerida
            if escolaridad_requerida in terminos_escolaridad:
                terminos = terminos_escolaridad[escolaridad_requerida]
                tiene_escolaridad = any(termino in texto_completo for termino in terminos)
                
                if not tiene_escolaridad:
                    logger.debug(f"⚠️ Sin escolaridad requerida ({escolaridad_requerida}): {oferta['titulo'][:40]}...")
                    return False
        
        # Filtro de nivel de inglés (si está configurado y no es "todos")
        nivel_ingles_requerido = self.config.get('nivel_ingles', 'todos')
        if nivel_ingles_requerido and nivel_ingles_requerido != 'todos':
            # Mapeo de términos por nivel de inglés
            terminos_ingles = {
                'sin_nivel': [],  # Si selecciona "sin nivel", NO debe mencionar inglés
                'basico': ['básico', 'basico', 'basic', 'a1', 'a2', 'elemental'],
                'intermedio': ['intermedio', 'intermediate', 'b1', 'b2', 'conversacional'],
                'avanzado': ['avanzado', 'advanced', 'c1', 'c2', 'fluent', 'fluido'],
                'nativo': ['nativo', 'native', 'bilingüe', 'bilingual', 'bilingue']
            }
            
            # Caso especial: "sin_nivel" significa que NO debe mencionar inglés
            if nivel_ingles_requerido == 'sin_nivel':
                menciona_ingles = any(palabra in texto_completo for palabra in ['inglés', 'ingles', 'english'])
                if menciona_ingles:
                    logger.debug(f"⚠️ Requiere inglés pero filtro es 'sin nivel': {oferta['titulo'][:40]}...")
                    return False
            else:
                # Para otros niveles, debe mencionar el nivel específico
                if nivel_ingles_requerido in terminos_ingles:
                    terminos = terminos_ingles[nivel_ingles_requerido]
                    tiene_nivel = any(termino in texto_completo for termino in terminos)
                    
                    if not tiene_nivel:
                        logger.debug(f"⚠️ Sin nivel de inglés requerido ({nivel_ingles_requerido}): {oferta['titulo'][:40]}...")
                        return False
        
        # Filtro de exclusión (si está configurado)
        if self.keywords.get('excluir'):
            for keyword_excluir in self.keywords['excluir']:
                if keyword_excluir.lower() in texto_completo:
                    logger.debug(f"❌ Excluida: {oferta['titulo'][:40]}... (contiene '{keyword_excluir}')")
                    return False
        
        # Filtro de inclusión (si está configurado)
        # Si NO hay keywords de inclusión, aceptar todas
        if self.keywords.get('incluir') and len(self.keywords['incluir']) > 0:
            tiene_keyword = False
            for keyword_incluir in self.keywords['incluir']:
                if keyword_incluir.lower() in texto_completo:
                    tiene_keyword = True
                    break
            
            if not tiene_keyword:
                logger.debug(f"⚠️ Sin keywords relevantes: {oferta['titulo'][:40]}...")
                return False
        
        return True
    
    def calcular_score(self, oferta):
        """Calcular score de relevancia (0-100)"""
        score = 50  # Base
        
        texto_completo = f"{oferta['titulo']} {oferta.get('descripcion', '')}".lower()
        
        # Bonus por keywords
        if self.keywords.get('bonus'):
            for keyword_bonus in self.keywords['bonus']:
                if keyword_bonus.lower() in texto_completo:
                    score += 5
        
        # Bonus por ubicación remoto
        if 'remoto' in texto_completo or 'remote' in texto_completo:
            score += 10
        
        # Bonus por tipo de empresa
        if any(word in texto_completo for word in ['startup', 'tech', 'fintech', 'tecnología']):
            score += 10
        
        # Bonus por fecha reciente
        if oferta.get('fecha_publicacion'):
            try:
                fecha_pub = datetime.strptime(oferta['fecha_publicacion'], '%Y-%m-%d')
                dias_antigüedad = (datetime.now() - fecha_pub).days
                if dias_antigüedad <= 3:
                    score += 15
                elif dias_antigüedad <= 7:
                    score += 10
                elif dias_antigüedad <= 14:
                    score += 5
            except:
                pass
        
        return min(score, 100)
    
    def filtrar_por_fechas(self, fecha_desde=None, fecha_hasta=None):
        """
        Filtrar ofertas por rango de fechas de publicación
        
        Args:
            fecha_desde: Fecha mínima en formato YYYY-MM-DD
            fecha_hasta: Fecha máxima en formato YYYY-MM-DD
        """
        if not fecha_desde and not fecha_hasta:
            return
        
        ofertas_filtradas = []
        
        for oferta in self.ofertas_encontradas:
            try:
                fecha_pub = datetime.strptime(oferta.get('fecha_publicacion', ''), '%Y-%m-%d')
                
                # Verificar rango
                valida = True
                if fecha_desde:
                    fecha_min = datetime.strptime(fecha_desde, '%Y-%m-%d')
                    if fecha_pub < fecha_min:
                        valida = False
                
                if fecha_hasta:
                    fecha_max = datetime.strptime(fecha_hasta, '%Y-%m-%d')
                    if fecha_pub > fecha_max:
                        valida = False
                
                if valida:
                    ofertas_filtradas.append(oferta)
            
            except:
                # Si hay error parseando fecha, mantener la oferta
                ofertas_filtradas.append(oferta)
        
        antes = len(self.ofertas_encontradas)
        self.ofertas_encontradas = ofertas_filtradas
        logger.info(f"📅 Filtro de fechas: {antes} → {len(ofertas_filtradas)} ofertas")
    
    def ejecutar_busqueda(self):
        """Ejecutar búsqueda en todos los portales configurados"""
        logger.info("=" * 60)
        logger.info("🚀 INICIANDO BÚSQUEDA AUTOMÁTICA DE EMPLEOS")
        logger.info("=" * 60)
        
        # OPTIMIZACIÓN: Solo usar primer título y primera ubicación para evitar timeout
        # Esto reduce de 3×2×10 = 60 búsquedas a 1×1×10 = 10 búsquedas
        titulo = self.config['titulos'][0] if self.config['titulos'] else 'Analista'
        ubicacion = self.config['ubicaciones'][0] if self.config['ubicaciones'] else 'Colombia'
        
        logger.info(f"📍 Buscando: {titulo} en {ubicacion}")
        logger.info(f"ℹ️  NOTA: Solo se usa el primer cargo y ubicación para evitar timeout")
        
        if self.portales.get('computrabajo', False):
            self.buscar_computrabajo(titulo, ubicacion)
        
        if self.portales.get('elempleo', False):
            self.buscar_elempleo(titulo, ubicacion)
        
        if self.portales.get('magneto', False):
            self.buscar_magneto(titulo, ubicacion)
        
        if self.portales.get('indeed', False):
            self.buscar_indeed(titulo, ubicacion)
        
        if self.portales.get('trabajando', False):
            self.buscar_trabajando(titulo, ubicacion)
        
        # NUEVOS PORTALES
        if self.portales.get('linkedin', False):
            self.buscar_linkedin(titulo, ubicacion)
        
        if self.portales.get('serviciodeempleo', False):
            self.buscar_serviciodeempleo(titulo, ubicacion)
        
        if self.portales.get('talentbox', False):
            self.buscar_talentbox(titulo, ubicacion)
        
        if self.portales.get('colsubsidio', False):
            self.buscar_colsubsidio(titulo, ubicacion)
        
        if self.portales.get('unmejorempleo', False):
            self.buscar_unmejorempleo(titulo, ubicacion)
        
        time.sleep(1)  # Pausa entre búsquedas
        
        logger.info("=" * 60)
        logger.info(f"✅ BÚSQUEDA COMPLETADA: {len(self.ofertas_encontradas)} ofertas encontradas")
        logger.info("=" * 60)
    
    def eliminar_duplicados(self):
        """Eliminar ofertas duplicadas basándose en título + empresa"""
        logger.info("🔄 Eliminando duplicados...")
        
        ofertas_unicas = []
        vistos = set()
        
        for oferta in self.ofertas_encontradas:
            clave = f"{oferta['titulo']}_{oferta['empresa']}".lower()
            if clave not in vistos:
                vistos.add(clave)
                ofertas_unicas.append(oferta)
        
        duplicados = len(self.ofertas_encontradas) - len(ofertas_unicas)
        self.ofertas_encontradas = ofertas_unicas
        
        logger.info(f"✅ {duplicados} duplicados eliminados. Ofertas únicas: {len(ofertas_unicas)}")
    
    def ordenar_por_score(self):
        """Ordenar ofertas por score descendente"""
        self.ofertas_encontradas.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    def obtener_estadisticas_portales(self):
        """Obtener conteo de ofertas por portal"""
        stats = {}
        for oferta in self.ofertas_encontradas:
            portal = oferta['portal']
            stats[portal] = stats.get(portal, 0) + 1
        return stats
    
    def obtener_estadisticas_ubicacion(self):
        """Obtener conteo de ofertas por ubicación"""
        stats = {}
        for oferta in self.ofertas_encontradas:
            ubicacion = oferta['ubicacion']
            stats[ubicacion] = stats.get(ubicacion, 0) + 1
        return stats
    
    def obtener_score_promedio(self):
        """Obtener score promedio de las ofertas"""
        if not self.ofertas_encontradas:
            return 0
        scores = [o.get('score', 0) for o in self.ofertas_encontradas]
        return round(sum(scores) / len(scores), 2)
