# 🤖 Bot Asistente de CV con Ollama

## Características

El bot asistente de CV usa IA local (Ollama) para:

- ✅ **Optimizar CVs para ATS** (Applicant Tracking Systems)
- ✅ **Analizar formato y estructura**
- ✅ **Sugerir palabras clave relevantes**
- ✅ **Revisar gramática y claridad**
- ✅ **Mejorar descripción de logros**
- ✅ **Recomendar mejoras específicas**

## Instalación de Ollama

### 1. Descargar Ollama

**Windows:**
```bash
# Descargar desde: https://ollama.com/download/windows
# O usar winget:
winget install Ollama.Ollama
```

**macOS:**
```bash
# Descargar desde: https://ollama.com/download/mac
# O usar brew:
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Instalar Modelo

Recomendamos usar `llama3.1` (más inteligente) o `mistral` (más rápido):

```bash
# Opción 1: Llama 3.1 (recomendado)
ollama pull llama3.1

# Opción 2: Mistral (más rápido)
ollama pull mistral

# Opción 3: Llama 3.2 (balanceado)
ollama pull llama3.2
```

### 3. Iniciar Ollama

```bash
ollama serve
```

Esto inicia Ollama en `http://localhost:11434`

### 4. Verificar Instalación

```bash
# Listar modelos instalados
ollama list

# Probar modelo
ollama run llama3.1 "Hola, ¿cómo estás?"
```

## Uso del Bot

### En la Aplicación Web

1. **Abrir el bot**: Click en el botón flotante 🤖 (esquina inferior derecha)

2. **Subir CV**:
   - Click en el botón de clip 📎
   - Selecciona tu CV (PDF o DOCX)
   - El bot analizará automáticamente

3. **Chatear**:
   - Escribe preguntas sobre tu CV
   - Pide consejos específicos
   - Solicita mejoras

### Ejemplos de Preguntas

```
"¿Cómo puedo mejorar la sección de experiencia?"
"¿Qué palabras clave me faltan para un puesto de Data Analyst?"
"¿Mi CV está optimizado para ATS?"
"Dame 5 consejos para destacar más"
"¿Cómo puedo cuantificar mejor mis logros?"
```

## Configuración Avanzada

### Cambiar Modelo

Edita `utils/cv_bot.py`:

```python
cv_bot = CVBotOllama(model="mistral")  # Cambiar aquí
```

### Cambiar URL de Ollama

Si Ollama corre en otro puerto:

```python
cv_bot = CVBotOllama(ollama_url="http://localhost:11434")
```

### Modelos Recomendados

| Modelo | Tamaño | Velocidad | Calidad | Uso |
|--------|--------|-----------|---------|-----|
| llama3.1 | ~4.7GB | Media | Alta | Recomendado |
| llama3.2 | ~2GB | Rápida | Buena | Máquinas lentas |
| mistral | ~4.1GB | Rápida | Alta | Alternativa |
| codellama | ~3.8GB | Media | Alta | Enfocado en tech |

## Troubleshooting

### "Ollama no está corriendo"

**Solución:**
```bash
ollama serve
```

### "No se puede conectar a Ollama"

**Verificar:**
1. Ollama está corriendo: `ollama list`
2. Puerto correcto: `http://localhost:11434`
3. Firewall no bloquea puerto 11434

### "Modelo no encontrado"

**Solución:**
```bash
ollama pull llama3.1
```

### CV no se analiza

**Verificar:**
1. Formato soportado (PDF o DOCX)
2. Tamaño < 10MB
3. Archivo no corrupto

## Características del Análisis

### Análisis ATS

- **Puntuación 0-100**: Compatibilidad con sistemas automáticos
- **Palabras clave**: Términos técnicos detectados
- **Formato**: Problemas de estructura
- **Mejoras**: Sugerencias específicas

### Mejoras Sugeridas

El bot analiza:
- Verbos de acción
- Cuantificación de logros
- Estructura y formato
- Gramática y ortografía
- Palabras clave faltantes
- Longitud y densidad de información

## Recursos

- **Ollama Docs**: https://github.com/ollama/ollama
- **Modelos disponibles**: https://ollama.com/library
- **Prompting best practices**: https://docs.anthropic.com/claude/docs/prompt-engineering

## Contacto

¿Problemas o sugerencias? Contacta al equipo de desarrollo.
