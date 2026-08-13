# 🤖 Bot Asistente de CV con Ollama

## Características

El bot asistente de CV usa IA local (Ollama) para:

- ✅ **Optimizar CVs para ATS** (Applicant Tracking Systems)
- ✅ **Analizar formato y estructura**
- ✅ **Sugerir palabras clave relevantes**
- ✅ **Revisar gramática y claridad**
- ✅ **Mejorar descripción de logros**
- ✅ **Recomendar mejoras específicas**
- ✅ **Reescribir el CV completo y entregarlo en DOCX** con el formato que
  exigen los ATS (botón "✨ Mejorar mi CV")

## ✨ Botón "Mejorar mi CV"

Además de analizar, el bot **reconstruye** el CV: reescribe el contenido con
verbos de acción, lo reordena en secciones estándar y lo entrega en un DOCX
listo para postular.

### Flujo

1. Sube el CV con 📎 (PDF o DOCX)
2. Opcional: escribe el cargo al que aplicas (ej. "Analista de Datos") para
   que el bot priorice las habilidades relevantes
3. Pulsa **✨ Mejorar mi CV**
4. Revisa la vista previa y descarga el DOCX

### Formato que aplica el documento generado

| Regla | Valor |
|-------|-------|
| Fuente | Calibri 11 pt (cuerpo), 20 pt (nombre), 12 pt (secciones) |
| Márgenes | 1.9 cm en los cuatro lados |
| Interlineado | 1.15 |
| Tablas / columnas / imágenes | Ninguna (los ATS no las parsean) |
| Encabezado y pie de página | Vacíos; el contacto va en el cuerpo |
| Títulos de sección | Mayúscula sostenida, nombres estándar |
| Viñetas | Estilo nativo `List Bullet` de Word |
| Habilidades | En línea, separadas por comas |

### Qué NO hace

El prompt le prohíbe al modelo inventar datos: si una cifra, empresa, fecha o
certificación no está en el CV original, el campo queda vacío. Reescribe la
redacción, no los hechos.

### Sin Ollama

Si Ollama no está corriendo, el botón sigue funcionando en **modo básico**:
reorganiza el CV por secciones y aplica todo el formato ATS, pero no reescribe
el texto. La respuesta lo indica con un aviso.

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

Con variables de entorno, sin tocar el código:

```bash
export OLLAMA_MODEL=qwen3:14b
export OLLAMA_URL=http://localhost:11434
```

Si no defines `OLLAMA_MODEL`, el bot consulta `/api/tags` y usa el primer
modelo generalista que encuentre instalado (descarta los de embeddings y
prefiere uno no especializado en código).

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
