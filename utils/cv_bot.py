#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT ASISTENTE DE CV CON OLLAMA
Análisis inteligente de CVs usando IA local
"""

import requests
import json
import io
import os
import re
import logging
from typing import Dict, List, Any

# Logger
logger = logging.getLogger(__name__)


class CVBotOllama:
    """Bot asistente para mejorar CVs usando Ollama"""
    
    def __init__(self, ollama_url=None, model=None):
        """
        Inicializar bot CV

        Args:
            ollama_url: URL de Ollama API
            model: Modelo a usar (llama3.1, qwen3, mistral, etc.)
        """
        self.ollama_url = (ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')).rstrip('/')
        self.model = model or os.getenv('OLLAMA_MODEL')
        # Token del proxy autenticado (scripts/ollama_proxy.py). Vacío cuando
        # Ollama corre en la misma máquina y no hace falta protegerlo.
        self.token = os.getenv('OLLAMA_TOKEN', '')
        self.cv_text = None
        self._modelo_resuelto = None

    def _cabeceras(self):
        """Cabeceras de las peticiones, con el token si está configurado."""
        cabeceras = {'Content-Type': 'application/json'}
        if self.token:
            cabeceras['Authorization'] = f'Bearer {self.token}'
        return cabeceras

    def resolve_model(self) -> str:
        """Modelo a usar, detectando uno instalado si no se configuró ninguno.

        Evita fallar con "model not found" cuando la máquina tiene modelos
        distintos al default.
        """
        if self.model:
            return self.model
        if self._modelo_resuelto:
            return self._modelo_resuelto

        try:
            response = requests.get(f"{self.ollama_url}/api/tags",
                                    headers=self._cabeceras(), timeout=6)
            modelos = [m['name'] for m in response.json().get('models', [])]
            # Los modelos de embeddings no sirven para generar texto
            candidatos = [m for m in modelos if 'embed' not in m.lower()]
            if candidatos:
                # Preferir un modelo generalista sobre uno especializado en código
                generalistas = [m for m in candidatos if 'coder' not in m.lower()]
                disponibles = generalistas or candidatos
                # Orden de preferencia; si ninguno está, se usa el primero que haya
                for preferido in ('llama3.1', 'llama3', 'qwen3', 'mistral'):
                    coincide = [m for m in disponibles if m.lower().startswith(preferido)]
                    if coincide:
                        disponibles = coincide
                        break
                self._modelo_resuelto = disponibles[0]
                logger.info(f"Modelo de Ollama detectado: {self._modelo_resuelto}")
                return self._modelo_resuelto
        except Exception as e:
            logger.warning(f"No se pudo detectar el modelo de Ollama: {e}")

        return 'llama3.1'

    def check_ollama_status(self) -> bool:
        """Verificar si Ollama está corriendo"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags",
                                    headers=self._cabeceras(), timeout=6)
            return response.status_code == 200
        except:
            return False
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extraer texto de PDF"""
        try:
            import PyPDF2
            pdf_file = io.BytesIO(file_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            raise Exception("PyPDF2 no está instalado. Instala con: pip install PyPDF2")
        except Exception as e:
            raise Exception(f"Error extrayendo texto de PDF: {str(e)}")
    
    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extraer texto de DOCX"""
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except ImportError:
            raise Exception("python-docx no está instalado. Instala con: pip install python-docx")
        except Exception as e:
            raise Exception(f"Error extrayendo texto de DOCX: {str(e)}")
    
    def parse_cv(self, file_bytes: bytes, filename: str) -> str:
        """Parsear CV desde archivo"""
        extension = filename.lower().split('.')[-1]
        
        try:
            if extension == 'pdf':
                return self.extract_text_from_pdf(file_bytes)
            elif extension in ['doc', 'docx']:
                return self.extract_text_from_docx(file_bytes)
            else:
                raise ValueError(f"Formato no soportado: {extension}. Use PDF o DOCX.")
        except Exception as e:
            # Si falla el parsing, crear texto dummy para que el análisis funcione
            logger.error(f"Error parseando CV: {str(e)}")
            # Retornar mensaje indicando el problema
            return f"[Error parseando archivo: {str(e)}]\n\nArchivo: {filename}\nTamaño: {len(file_bytes)} bytes"
    
    def analyze_cv_ats(self) -> Dict[str, Any]:
        """Analizar CV para compatibilidad con ATS"""
        if not self.cv_text:
            return {"error": "No hay CV cargado"}
        
        # Si Ollama no está disponible, usar análisis básico
        if not self.check_ollama_status():
            return self.analyze_cv_basic()
        
        prompt = f"""Analiza el siguiente CV para compatibilidad con sistemas ATS (Applicant Tracking Systems).

CV:
{self.cv_text}

Proporciona:
1. Puntuación ATS (0-100)
2. Palabras clave detectadas
3. Formato y estructura
4. Áreas de mejora específicas

Responde en formato JSON con esta estructura:
{{
    "ats_score": 85,
    "keywords": ["Python", "SQL", "Data Analysis"],
    "format_issues": ["Lista de problemas de formato"],
    "improvements": ["Lista de mejoras sugeridas"],
    "strong_points": ["Puntos fuertes del CV"]
}}
"""
        
        try:
            response = self.call_ollama(prompt)
            # Intentar parsear JSON de la respuesta
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"error": "No se pudo parsear el análisis", "raw": response}
        except Exception as e:
            # Si falla Ollama, usar análisis básico
            return self.analyze_cv_basic()
    
    def analyze_cv_basic(self) -> Dict[str, Any]:
        """Análisis básico sin IA (cuando Ollama no está disponible)"""
        if not self.cv_text:
            return {"error": "No hay CV cargado"}
        
        text = self.cv_text.lower()
        
        # Palabras clave técnicas comunes
        tech_keywords = {
            'python', 'java', 'javascript', 'sql', 'excel', 'powerbi', 'tableau',
            'data', 'analysis', 'machine learning', 'ai', 'database', 'cloud',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'agile',
            'scrum', 'react', 'node', 'django', 'flask', 'api', 'rest'
        }
        
        # Detectar palabras clave presentes
        found_keywords = [kw for kw in tech_keywords if kw in text]
        
        # Calcular puntuación básica
        score = 50  # Base
        
        # Bonificación por longitud
        word_count = len(self.cv_text.split())
        if 300 <= word_count <= 800:
            score += 10
        elif word_count > 800:
            score += 5
        
        # Bonificación por palabras clave
        score += min(len(found_keywords) * 3, 30)
        
        # Bonificación por secciones comunes
        sections = ['experiencia', 'education', 'habilidades', 'skills', 'proyectos', 'projects']
        sections_found = sum(1 for s in sections if s in text)
        score += sections_found * 3
        
        # Detectar problemas
        format_issues = []
        if word_count < 200:
            format_issues.append("CV muy corto (menos de 200 palabras)")
        if word_count > 1000:
            format_issues.append("CV muy largo (más de 1000 palabras)")
        if len(found_keywords) < 3:
            format_issues.append("Pocas palabras clave técnicas")
        
        # Mejoras sugeridas
        improvements = []
        if 'logré' not in text and 'desarrollé' not in text:
            improvements.append("Usa verbos de acción: logré, desarrollé, lideré")
        if not any(char.isdigit() for char in self.cv_text[:500]):
            improvements.append("Cuantifica tus logros con números y porcentajes")
        if len(found_keywords) < 5:
            improvements.append("Agrega más palabras clave técnicas relevantes")
        
        # Puntos fuertes
        strong_points = []
        if len(found_keywords) >= 5:
            strong_points.append(f"Buena cantidad de palabras clave técnicas ({len(found_keywords)})")
        if 300 <= word_count <= 800:
            strong_points.append("Longitud apropiada del CV")
        if sections_found >= 3:
            strong_points.append("Estructura bien organizada con secciones claras")
        
        return {
            "ats_score": min(score, 100),
            "keywords": found_keywords[:10],  # Top 10
            "format_issues": format_issues if format_issues else ["Ninguno detectado"],
            "improvements": improvements if improvements else ["CV en buen estado general"],
            "strong_points": strong_points if strong_points else ["CV aceptable"],
            "mode": "basic"  # Indicar que es análisis básico
        }
    
    def chat(self, user_message: str, context: str = "") -> str:
        """Chat con el bot sobre el CV"""
        
        # Si Ollama no está disponible, dar respuestas básicas
        if not self.check_ollama_status():
            return self.chat_basic(user_message)
        
        # Construir prompt sin backslash en f-string
        cv_section = f"CV del usuario:\n{self.cv_text}\n\n" if self.cv_text else ""
        context_section = f"{context}\n\n" if context else ""
        
        prompt = f"""Eres un asistente experto en optimización de CVs y reclutamiento.

{cv_section}{context_section}Usuario: {user_message}

Proporciona consejos específicos, prácticos y accionables. Sé conciso pero útil."""
        
        try:
            return self.call_ollama(prompt)
        except Exception as e:
            return self.chat_basic(user_message)
    
    def chat_basic(self, user_message: str) -> str:
        """Respuestas básicas cuando Ollama no está disponible"""
        message_lower = user_message.lower()
        
        # Respuestas basadas en palabras clave
        if any(word in message_lower for word in ['hola', 'hi', 'hello']):
            return "¡Hola! Estoy aquí para ayudarte a mejorar tu CV. Puedes preguntarme sobre formato, palabras clave, o cómo optimizar para ATS."
        
        if 'ats' in message_lower:
            return """Para optimizar tu CV para ATS:
            
1. Usa formato simple (sin tablas complejas o gráficos)
2. Incluye palabras clave del anuncio de trabajo
3. Usa fuentes estándar (Arial, Calibri)
4. Evita headers y footers
5. Guarda como PDF o DOCX
6. Usa secciones claras (Experiencia, Educación, Habilidades)"""
        
        if any(word in message_lower for word in ['mejorar', 'improve', 'mejor']):
            return """Consejos para mejorar tu CV:

✅ Usa verbos de acción (logré, desarrollé, lideré)
✅ Cuantifica logros (aumenté ventas 30%)
✅ Adapta CV a cada posición
✅ Máximo 2 páginas
✅ Revisa ortografía
✅ Incluye palabras clave técnicas
✅ Destaca logros, no solo responsabilidades"""
        
        if any(word in message_lower for word in ['palabra', 'keyword', 'clave']):
            return """Palabras clave importantes:

🔹 Técnicas: Python, SQL, Excel, PowerBI, Cloud, etc.
🔹 Soft skills: Liderazgo, Comunicación, Trabajo en equipo
🔹 Logros: Aumenté, Reduje, Optimicé, Desarrollé
🔹 Certificaciones: Menciona todas relevantes

Consejo: Lee el anuncio de trabajo y usa las mismas palabras."""
        
        if any(word in message_lower for word in ['formato', 'format', 'estructura']):
            return """Estructura recomendada:

1️⃣ Header: Nombre, contacto, LinkedIn
2️⃣ Resumen profesional (2-3 líneas)
3️⃣ Experiencia laboral (más reciente primero)
4️⃣ Educación
5️⃣ Habilidades técnicas
6️⃣ Certificaciones (opcional)
7️⃣ Proyectos (opcional)

Evita: Fotos, gráficos complejos, colores excesivos."""
        
        # Respuesta genérica
        return f"""Gracias por tu pregunta. Aquí algunos consejos generales:

💡 **Análisis Básico**: Sube tu CV para obtener un análisis automático
💡 **Ollama**: Para respuestas más detalladas con IA, conecta Ollama local
💡 **Consejos**: Pregúntame sobre ATS, formato, palabras clave, o mejoras

¿En qué específicamente puedo ayudarte?"""
    
    def call_ollama(self, prompt: str, fmt: str = None, options: dict = None) -> str:
        """Llamar a Ollama API

        Args:
            prompt: Texto del prompt
            fmt: "json" para forzar que el modelo responda JSON válido
            options: Opciones del modelo (num_ctx, temperature, ...)
        """
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.resolve_model(),
            "prompt": prompt,
            "stream": False,
            # Los modelos de razonamiento (qwen3, deepseek-r1) mezclan su
            # cadena de pensamiento con la respuesta y rompen el parseo JSON.
            "think": False
        }
        if fmt:
            payload["format"] = fmt
        if options:
            payload["options"] = options

        try:
            response = requests.post(url, json=payload, headers=self._cabeceras(), timeout=180)
            response.raise_for_status()
            return response.json()['response']
        except requests.exceptions.ConnectionError:
            raise Exception("No se puede conectar a Ollama. ¿Está corriendo?")
        except requests.exceptions.Timeout:
            raise Exception("Timeout al conectar con Ollama")
        except Exception as e:
            raise Exception(f"Error llamando a Ollama: {str(e)}")
    
    def get_quick_tips(self) -> List[str]:
        """Consejos rápidos para mejorar CV"""
        return [
            "Usa verbos de acción al inicio de cada punto (logré, desarrollé, lideré)",
            "Cuantifica tus logros con números y porcentajes",
            "Adapta tu CV a cada posición usando palabras clave del anuncio",
            "Mantén el formato simple y limpio (sin gráficos complejos para ATS)",
            "Usa una fuente profesional (Arial, Calibri, Times New Roman)",
            "Incluye sección de habilidades con tecnologías específicas",
            "Máximo 2 páginas (1 página si tienes menos de 5 años de experiencia)",
            "Revisa ortografía y gramática cuidadosamente",
            "Incluye logros medibles, no solo responsabilidades",
            "Usa formato consistente en todo el documento"
        ]


# Instancia global del bot
cv_bot = None

def get_cv_bot() -> CVBotOllama:
    """Obtener instancia del bot CV"""
    global cv_bot
    if cv_bot is None:
        cv_bot = CVBotOllama()
    return cv_bot
