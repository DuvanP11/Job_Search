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
        """Buscar ofertas en Computrabajo.com.co"""
        logger.info(f"🔍 Buscando en Computrabajo: {titulo} - {ubicacion}")
        
        try:
            # Construir URL de búsqueda
            query = f"{titulo} {ubicacion}"
            url = f"https://www.computrabajo.com.co/trabajo-de-{quote_plus(query)}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Computrabajo")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas (selectores actualizados)
            ofertas = soup.find_all('article', attrs={'data-test': 'offer-card'})
            if not ofertas:
                ofertas = soup.find_all('article', class_='box_offer')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:30]:  # Limitar a 30 por búsqueda
                try:
                    # Extraer información
                    titulo_elem = oferta.find('a', class_='js-o-link') or oferta.find('h2')
                    empresa_elem = oferta.find('p', class_='fs16') or oferta.find('div', attrs={'data-test': 'company-name'})
                    ubicacion_elem = oferta.find('p', class_='fs13') or oferta.find('div', attrs={'data-test': 'location'})
                    fecha_elem = oferta.find('p', class_='fs13 fc_base') or oferta.find('time')
                    
                    if not titulo_elem:
                        continue
                    
                    # Construir datos de la oferta
                    link = titulo_elem.get('href', '')
                    if link and not link.startswith('http'):
                        link = 'https://www.computrabajo.com.co' + link
                    
                    # Parsear fecha de publicación
                    fecha_publicacion = self._parsear_fecha(fecha_elem.text.strip() if fecha_elem else '')
                    
                    oferta_data = {
                        'titulo': titulo_elem.text.strip(),
                        'empresa': empresa_elem.text.strip() if empresa_elem else 'No especificada',
                        'ubicacion': ubicacion_elem.text.strip() if ubicacion_elem else ubicacion,
                        'link': link,
                        'portal': 'Computrabajo',
                        'fecha_publicacion': fecha_publicacion,
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': ''  # Computrabajo no muestra descripción en listados
                    }
                    
                    # Aplicar filtros
                    if self.aplicar_filtros(oferta_data):
                        oferta_data['score'] = self.calcular_score(oferta_data)
                        self.ofertas_encontradas.append(oferta_data)
                        ofertas_procesadas += 1
                
                except Exception as e:
                    logger.debug(f"Error procesando oferta: {str(e)}")
                    continue
            
            logger.info(f"✅ {ofertas_procesadas} ofertas válidas de Computrabajo")
            time.sleep(2)  # Respetar el servidor
            
        except Exception as e:
            logger.error(f"❌ Error en Computrabajo: {str(e)}")
    
    def buscar_elempleo(self, titulo, ubicacion):
        """Buscar ofertas en ElEmpleo.com"""
        logger.info(f"🔍 Buscando en ElEmpleo: {titulo} - {ubicacion}")
        
        try:
            query = f"{titulo} {ubicacion}"
            url = f"https://www.elempleo.com/co/ofertas-empleo/?buscar={quote_plus(query)}"
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en ElEmpleo")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='resultado') or soup.find_all('article', class_='job-card')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:30]:
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
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Magneto365")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='offer-card') or soup.find_all('article', class_='job-listing')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:30]:
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
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Indeed")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas (Indeed usa divs con clase específica)
            ofertas = soup.find_all('div', class_='job_seen_beacon') or soup.find_all('div', class_='jobsearch-SerpJobCard')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:30]:
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
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"❌ Error {response.status_code} en Trabajando.com")
                return
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar ofertas
            ofertas = soup.find_all('div', class_='job-item') or soup.find_all('article', class_='offer')
            
            ofertas_procesadas = 0
            for oferta in ofertas[:30]:
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
        """Aplicar filtros de keywords a una oferta"""
        texto_completo = f"{oferta['titulo']} {oferta.get('descripcion', '')}".lower()
        
        # Filtro de exclusión
        if self.keywords.get('excluir'):
            for keyword_excluir in self.keywords['excluir']:
                if keyword_excluir.lower() in texto_completo:
                    logger.debug(f"❌ Excluida: {oferta['titulo'][:40]}... (contiene '{keyword_excluir}')")
                    return False
        
        # Filtro de inclusión (al menos una keyword debe estar)
        if self.keywords.get('incluir'):
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
        
        # Iterar sobre combinaciones de título y ubicación
        for titulo in self.config['titulos']:
            for ubicacion in self.config['ubicaciones']:
                
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
