# 🔍 Portal de Búsqueda de Empleos Colombia

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

Portal web automatizado para búsqueda de ofertas laborales en múltiples portales de empleo colombianos con filtros personalizables.

## 🌟 Características

- ✅ **Búsqueda Automática** en múltiples portales (Computrabajo, ElEmpleo, Magneto365)
- ✅ **Filtros Avanzados**: ubicación, salario, experiencia, modalidad, tipo de contrato
- ✅ **Filtro por Rango de Fechas**: Filtra ofertas por fecha de publicación
- ✅ **Keywords Personalizables**: incluir, excluir y bonus
- ✅ **Sistema de Scoring**: Prioriza ofertas más relevantes (0-100)
- ✅ **Exportación a Excel**: Descarga resultados con un clic
- ✅ **Interfaz Responsiva**: Funciona en desktop, tablet y móvil
- ✅ **Tiempo Real**: Resultados actualizados al momento

## 🖼️ Capturas de Pantalla

### Formulario de Búsqueda
![Formulario](https://via.placeholder.com/800x400?text=Formulario+de+B%C3%BAsqueda)

### Resultados
![Resultados](https://via.placeholder.com/800x400?text=Tabla+de+Resultados)

## 🚀 Tecnologías Utilizadas

### Backend
- **Flask 3.0.0**: Framework web
- **Beautiful Soup 4**: Web scraping
- **Pandas**: Manipulación de datos
- **Requests**: HTTP requests
- **OpenPyXL**: Generación de archivos Excel

### Frontend
- **HTML5 + CSS3**
- **JavaScript (ES6+)**
- **Bootstrap 5.3**: Framework CSS
- **Font Awesome 6**: Iconos

### Deploy
- **Gunicorn**: WSGI HTTP Server
- **Render**: Plataforma de hosting

## 📋 Requisitos Previos

- Python 3.11 o superior
- Git
- Cuenta en GitHub
- Cuenta en Render (para deploy)

## 🔧 Instalación Local

### 1. Clonar el repositorio

```bash
git clone https://github.com/DuvanP11/Job_Search.git
cd Job_Search
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```bash
python app.py
```

La aplicación estará disponible en: `http://localhost:5000`

## 🌐 Deploy en Render

### Opción 1: Desde GitHub (Recomendado)

1. **Hacer push a GitHub**:
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

2. **Configurar en Render**:
   - Ir a [render.com](https://render.com)
   - Crear nuevo "Web Service"
   - Conectar con tu repositorio de GitHub
   - Configuración:
     - **Name**: `job-search-portal`
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
   - Hacer clic en "Create Web Service"

3. **Esperar el deploy** (2-5 minutos)

4. **Acceder a tu app**: `https://job-search-portal.onrender.com`

### Opción 2: Deploy Manual

```bash
# Asegúrate de tener render-cli instalado
npm install -g render-cli

# Login a Render
render login

# Deploy
render deploy
```

## 📖 Uso del Portal

### 1. Configurar Búsqueda

**Información Básica:**
- **Cargos**: Escribe los títulos que buscas (uno por línea)
- **Ubicaciones**: Ciudades o "Remoto" (una por línea)

**Filtros Económicos:**
- **Salario Mínimo**: En pesos colombianos (COP)
- **Tipo de Contrato**: Indefinido, Temporal, etc.
- **Modalidades**: Remoto, Híbrido, Presencial

**Experiencia y Fechas:**
- **Experiencia**: Rango en años
- **Fecha Desde/Hasta**: Filtra ofertas por fecha de publicación

**Keywords (Opcional):**
- **Incluir**: La oferta debe tener al menos una
- **Excluir**: Si la tiene, se descalifica
- **Bonus**: Aumentan el score de relevancia

**Portales:**
- Selecciona los portales donde buscar

### 2. Ejecutar Búsqueda

Clic en **"Buscar Ofertas"**. La búsqueda puede tardar 1-3 minutos.

### 3. Ver Resultados

- **Tabla ordenada por score** (mayor = más relevante)
- **Estadísticas**: Total ofertas, score promedio, portales consultados
- **Link directo** a cada oferta

### 4. Exportar

Clic en **"Exportar Excel"** para descargar los resultados.

## 🎯 Sistema de Scoring

El score (0-100) se calcula así:

**Base**: 50 puntos

**Bonificaciones:**
- +5 puntos por cada keyword bonus encontrada
- +10 puntos si es remoto
- +10 puntos si es startup/tech/fintech
- +15 puntos si fue publicada hace ≤3 días
- +10 puntos si fue publicada hace ≤7 días
- +5 puntos si fue publicada hace ≤14 días

**Máximo**: 100 puntos

**Recomendación**: Aplica primero a ofertas con score ≥ 80

## 📊 Estructura del Proyecto

```
Job_Search/
│
├── app.py                  # Aplicación Flask principal
├── requirements.txt        # Dependencias Python
├── Procfile               # Configuración Render
├── runtime.txt            # Versión Python
├── README.md              # Documentación
├── .gitignore            # Archivos ignorados
│
├── utils/
│   ├── __init__.py
│   └── scraper.py         # Lógica de scraping
│
├── templates/
│   └── index.html         # Página principal
│
└── static/
    ├── css/
    │   └── style.css      # Estilos personalizados
    └── js/
        └── main.js        # Lógica frontend
```

## ⚙️ Variables de Entorno (Opcional)

```bash
# .env (crear si necesitas configuración personalizada)
FLASK_ENV=production
PORT=5000
SECRET_KEY=tu-clave-secreta-aqui
```

## 🐛 Solución de Problemas

### Error: "Module not found"
```bash
pip install -r requirements.txt --upgrade
```

### Error: "Port already in use"
```bash
# Cambiar puerto en app.py
port = int(os.environ.get('PORT', 5001))  # Cambiar a 5001
```

### No encuentra ofertas
- Verifica conexión a internet
- Los portales pueden haber cambiado su estructura HTML
- Prueba con filtros menos restrictivos

### Error 403/Blocked
- Los portales detectan bots
- Espera 1-2 horas antes de volver a ejecutar
- Considera agregar delays más largos en scraper.py

## 🔒 Limitaciones y Consideraciones

- **Rate Limiting**: No ejecutar muy seguido (max 2-3 veces al día)
- **Selectores HTML**: Los portales pueden cambiar su estructura
- **LinkedIn**: No incluido (requiere autenticación)
- **Salarios**: Muchas ofertas no publican salario
- **Descripciones**: Algunos portales no las muestran en listados

## 🤝 Contribuir

¡Las contribuciones son bienvenidas!

1. Fork el proyecto
2. Crea tu rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Roadmap

- [ ] Agregar LinkedIn (con autenticación)
- [ ] Notificaciones por email
- [ ] Guardar búsquedas favoritas
- [ ] API REST pública
- [ ] Sistema de usuarios
- [ ] Estadísticas históricas
- [ ] Más portales (Indeed, Glassdoor)
- [ ] Análisis de salarios con ML

## 📧 Contacto

**Duvan Perilla**
- 📧 Email: duvanesneider11@gmail.com
- 💼 GitHub: [@DuvanP11](https://github.com/DuvanP11)
- 🔗 LinkedIn: [Duvan Perilla](https://linkedin.com/in/duvanperilla)

## ⚖️ Licencia

Este proyecto es para uso personal y educativo. Respeta los términos de servicio de cada portal de empleo.

**MIT License** - Ver [LICENSE](LICENSE) para más detalles.

## ⚠️ Disclaimer

Este proyecto es una herramienta de agregación de ofertas laborales públicas. El autor no se hace responsable del uso indebido o de violaciones a los términos de servicio de los portales consultados. Úsalo de manera responsable y ética.

---

**¡Buena suerte en tu búsqueda laboral!** 🚀

Si te ha sido útil, considera darle una ⭐ al proyecto.

---

Desarrollado con ❤️ por [Duvan Perilla](https://github.com/DuvanP11) | 2025
