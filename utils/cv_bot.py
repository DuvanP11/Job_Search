#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT ASISTENTE DE CV CON OLLAMA
Análisis inteligente de CVs usando IA local
"""

import requests
import json
import PyPDF2
import docx
import io
import re
from typing import Dict, List, Any


class CVBotOllama:
    """Bot asistente para mejorar CVs usando Ollama"""
    
    def __init__(self, ollama_url="http://localhost:11434", model="llama3.1"):
        """
        Inicializar bot CV
        
        Args:
            ollama_url: URL de Ollama API
            model: Modelo a usar (llama3.1, mistral, etc.)
        """
        self.ollama_url = ollama_url
        self.model = model
        self.cv_text = None
        
    def check_ollama_status(self) -> bool:
        """Verificar si Ollama está corriendo"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extraer texto de PDF"""
        try:
            pdf_file = io.BytesIO(file_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de PDF: {str(e)}")
    
    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extraer texto de DOCX"""
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            raise Exception(f"Error extrayendo texto de DOCX: {str(e)}")
    
    def parse_cv(self, file_bytes: bytes, filename: str) -> str:
        """Parsear CV desde archivo"""
        extension = filename.lower().split('.')[-1]
        
        if extension == 'pdf':
            return self.extract_text_from_pdf(file_bytes)
        elif extension in ['doc', 'docx']:
            return self.extract_text_from_docx(file_bytes)
        else:
            raise ValueError("Formato no soportado. Use PDF o DOCX.")
    
    def analyze_cv_ats(self) -> Dict[str, Any]:
        """Analizar CV para compatibilidad con ATS"""
        if not self.cv_text:
            return {"error": "No hay CV cargado"}
        
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
            return {"error": str(e)}
    
    def chat(self, user_message: str, context: str = "") -> str:
        """Chat con el bot sobre el CV"""
        prompt = f"""Eres un asistente experto en optimización de CVs y reclutamiento.

{"CV del usuario:\n" + self.cv_text + "\n\n" if self.cv_text else ""}
{context + "\n\n" if context else ""}
Usuario: {user_message}

Proporciona consejos específicos, prácticos y accionables. Sé conciso pero útil."""
        
        try:
            return self.call_ollama(prompt)
        except Exception as e:
            return f"Error: {str(e)}"
    
    def call_ollama(self, prompt: str) -> str:
        """Llamar a Ollama API"""
        url = f"{self.ollama_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
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
