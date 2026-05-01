#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SELENIUM SCRAPER - Login real en portales de empleo
Usa credenciales reales para evitar bloqueos y acceder a todas las ofertas
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SeleniumScraper:
    """Clase base para scraping con Selenium (login real)"""
    
    def __init__(self, credentials=None, headless=True):
        """
        Inicializar scraper con Selenium
        
        Args:
            credentials (dict): {'email': str, 'password': str}
            headless (bool): Ejecutar sin interfaz gráfica
        """
        self.credentials = credentials
        self.headless = headless
        self.driver = None
        self.logged_in = False
    
    def _setup_driver(self):
        """Configurar Chrome con Selenium"""
        try:
            options = Options()
            
            if self.headless:
                options.add_argument('--headless')
            
            # Opciones para evitar detección
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User agent realista
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Detectar ChromeDriver automáticamente
            # Railway/Nixpacks lo pone en /nix/store/.../bin/chromedriver
            import shutil
            chromedriver_path = shutil.which('chromedriver')
            
            if chromedriver_path:
                logger.info(f"✅ ChromeDriver encontrado en: {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                logger.info("✅ Usando ChromeDriver del PATH")
                driver = webdriver.Chrome(options=options)
            
            # Ocultar webdriver
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("✅ Chrome driver configurado")
            return driver
        
        except Exception as e:
            logger.error(f"❌ Error configurando driver: {str(e)}")
            return None
    
    def start(self):
        """Iniciar navegador"""
        if not self.driver:
            self.driver = self._setup_driver()
        return self.driver is not None
    
    def stop(self):
        """Cerrar navegador"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ Navegador cerrado")
            except:
                pass
            finally:
                self.driver = None
                self.logged_in = False
    
    def login(self):
        """Hacer login - debe ser implementado por cada portal"""
        raise NotImplementedError("Cada portal debe implementar su propio login")
    
    def buscar_ofertas(self, titulo, ubicacion):
        """Buscar ofertas - debe ser implementado por cada portal"""
        raise NotImplementedError("Cada portal debe implementar su propia búsqueda")
    
    def wait_for_element(self, by, value, timeout=10):
        """Esperar a que un elemento esté presente"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"⚠️ Timeout esperando elemento: {value}")
            return None
    
    def click_element(self, by, value, timeout=10):
        """Click en un elemento con espera"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            element.click()
            return True
        except TimeoutException:
            logger.warning(f"⚠️ No se pudo hacer click en: {value}")
            return False
    
    def take_screenshot(self, filename):
        """Tomar captura de pantalla (útil para debugging)"""
        try:
            if self.driver:
                self.driver.save_screenshot(filename)
                logger.info(f"📸 Screenshot guardado: {filename}")
                return True
        except:
            pass
        return False


class ElEmpleoBot(SeleniumScraper):
    """Bot para ElEmpleo.com con login real"""
    
    def __init__(self, credentials, headless=True):
        super().__init__(credentials, headless)
        self.portal_name = "ElEmpleo"
        self.base_url = "https://www.elempleo.com"
    
    def login(self):
        """Hacer login en ElEmpleo"""
        try:
            logger.info(f"🔐 Iniciando sesión en {self.portal_name}...")
            
            # Ir a página de login
            self.driver.get(f"{self.base_url}/co/signin")
            time.sleep(2)
            
            # Ingresar email
            email_input = self.wait_for_element(By.ID, "email", timeout=15)
            if not email_input:
                logger.error("❌ No se encontró campo de email")
                return False
            
            email_input.clear()
            email_input.send_keys(self.credentials['email'])
            time.sleep(1)
            
            # Ingresar password
            pwd_input = self.driver.find_element(By.ID, "password")
            pwd_input.clear()
            pwd_input.send_keys(self.credentials['password'])
            time.sleep(1)
            
            # Click en botón login
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            # Esperar redirección
            time.sleep(5)
            
            # Verificar si login fue exitoso
            current_url = self.driver.current_url
            if "signin" not in current_url.lower():
                logger.info(f"✅ Login exitoso en {self.portal_name}")
                self.logged_in = True
                return True
            else:
                logger.error(f"❌ Login fallido en {self.portal_name}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error en login de {self.portal_name}: {str(e)}")
            return False
    
    def buscar_ofertas(self, titulo, ubicacion, max_ofertas=20):
        """Buscar ofertas en ElEmpleo con scroll y filtrado por relevancia"""
        try:
            logger.info(f"🔍 Buscando en {self.portal_name}: {titulo} - {ubicacion}")
            
            # Verificar login
            if not self.logged_in:
                logger.warning("⚠️ No hay sesión activa, intentando login...")
                if not self.login():
                    return []
            
            # Construir URL de búsqueda
            from urllib.parse import quote_plus
            query = quote_plus(titulo)  # Solo el título, sin ubicación
            url = f"{self.base_url}/co/ofertas-empleo/?q={query}"
            
            logger.info(f"📍 URL: {url}")
            self.driver.get(url)
            time.sleep(4)
            
            # SCROLL para cargar más ofertas
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            
            # Extraer ofertas con MÚLTIPLES estrategias
            ofertas = []
            
            # Estrategia 1: Selectores específicos de ElEmpleo 2025
            selectors = [
                "article[data-offer]",
                "div[data-id-oferta]",
                "a.js-o-link",
                "div.offer-item",
                "article.offer",
                "div[class*='offer']",
                "article[class*='job']",
                "div.resultado"
            ]
            
            offer_elements = []
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(elements) >= 5:  # Al menos 5 ofertas
                        offer_elements = elements
                        logger.info(f"✅ {len(elements)} elementos con: {selector}")
                        break
                except:
                    continue
            
            # Estrategia 2: Buscar por links si no funcionó
            if len(offer_elements) < 5:
                logger.warning("⚠️ Pocos resultados, buscando por links...")
                offer_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "a[href*='/oferta/'], a[href*='/empleo/'], a[href*='vacante']")
            
            logger.info(f"📊 Total elementos encontrados: {len(offer_elements)}")
            
            # Tomar screenshot para debugging
            try:
                self.driver.save_screenshot('/tmp/elempleo_debug.png')
                logger.info("📸 Screenshot guardado en /tmp/elempleo_debug.png")
            except:
                pass
            
            # Palabras clave del título para filtrado
            titulo_keywords = set(titulo.lower().split())
            
            # Procesar ofertas
            ofertas_procesadas = set()  # Evitar duplicados
            
            for i, element in enumerate(offer_elements[:max_ofertas * 3]):
                try:
                    # Extraer TEXTO COMPLETO del elemento
                    texto_completo = element.text.strip()
                    
                    if not texto_completo or len(texto_completo) < 10:
                        continue
                    
                    # Extraer título (primera línea o texto más prominente)
                    lineas = texto_completo.split('\n')
                    titulo_oferta = lineas[0].strip() if lineas else texto_completo[:100]
                    
                    # FILTRO DE RELEVANCIA
                    titulo_lower = titulo_oferta.lower()
                    palabras_titulo = set(titulo_lower.split())
                    coincidencias = len(titulo_keywords & palabras_titulo)
                    
                    # Si no hay coincidencias, verificar si al menos contiene alguna palabra clave
                    if coincidencias == 0:
                        tiene_keyword = any(kw in titulo_lower for kw in titulo_keywords)
                        if not tiene_keyword:
                            logger.debug(f"❌ Rechazada (no relevante): {titulo_oferta[:50]}")
                            continue
                    
                    # Extraer link
                    try:
                        link = element.get_attribute('href')
                        if not link:
                            link = element.find_element(By.TAG_NAME, 'a').get_attribute('href')
                    except:
                        continue
                    
                    if not link or link in ofertas_procesadas:
                        continue
                    
                    ofertas_procesadas.add(link)
                    
                    # Extraer empresa (segunda línea típicamente)
                    empresa = lineas[1].strip() if len(lineas) > 1 else "No especificada"
                    
                    # Extraer ubicación (buscar en texto)
                    ubicacion_oferta = ubicacion
                    for linea in lineas:
                        if any(city in linea.lower() for city in ['bogotá', 'medellín', 'cali', 'barranquilla']):
                            ubicacion_oferta = linea.strip()
                            break
                    
                    # Calcular score basado en relevancia
                    score = 50 + (coincidencias * 10)
                    if titulo.lower() in titulo_lower:
                        score += 20
                    
                    # Crear oferta
                    oferta_data = {
                        'titulo': titulo_oferta[:150],
                        'empresa': empresa[:100],
                        'ubicacion': ubicacion_oferta,
                        'link': link,
                        'portal': self.portal_name,
                        'fecha_publicacion': datetime.now().strftime('%Y-%m-%d'),
                        'fecha_busqueda': datetime.now().strftime('%Y-%m-%d'),
                        'descripcion': texto_completo[:300],
                        'score': min(score, 100)
                    }
                    
                    ofertas.append(oferta_data)
                    logger.info(f"✅ Agregada (score={score}): {titulo_oferta[:50]}")
                    
                    # Limitar cantidad
                    if len(ofertas) >= max_ofertas:
                        break
                
                except Exception as e:
                    logger.debug(f"Error procesando elemento {i}: {str(e)}")
                    continue
            
            # Ordenar por score (más relevantes primero)
            ofertas.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info(f"✅ {len(ofertas)} ofertas relevantes encontradas en {self.portal_name}")
            return ofertas
        
        except Exception as e:
            logger.error(f"❌ Error buscando en {self.portal_name}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
