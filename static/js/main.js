// main.js - Lógica principal del portal de búsqueda de empleos

document.addEventListener('DOMContentLoaded', function() {
    console.log('Portal de búsqueda de empleos cargado');
    
    // Elementos del DOM
    const formulario = document.getElementById('formulario-busqueda');
    const btnBuscar = document.getElementById('btn-buscar');
    const btnLimpiar = document.getElementById('btn-limpiar');
    const btnExportar = document.getElementById('btn-exportar');
    const loadingSection = document.getElementById('loading-section');
    const resultadosSection = document.getElementById('resultados-section');
    
    // Establecer fecha máxima en los campos de fecha (hoy)
    const hoy = new Date().toISOString().split('T')[0];
    document.getElementById('fecha_hasta').value = hoy;
    document.getElementById('fecha_hasta').max = hoy;
    document.getElementById('fecha_desde').max = hoy;
    
    // Establecer fecha desde por defecto (últimos 30 días)
    const hace30dias = new Date();
    hace30dias.setDate(hace30dias.getDate() - 30);
    document.getElementById('fecha_desde').value = hace30dias.toISOString().split('T')[0];
    
    // Event Listeners
    formulario.addEventListener('submit', handleBusqueda);
    btnLimpiar.addEventListener('click', limpiarFormulario);
    btnExportar.addEventListener('click', exportarExcel);
    
    // Botones de selección masiva de portales
    document.getElementById('btn-seleccionar-todos-portales').addEventListener('click', function() {
        const checkboxes = [
            'portal_computrabajo', 'portal_elempleo', 'portal_magneto', 
            'portal_indeed', 'portal_trabajando', 'portal_linkedin',
            'portal_serviciodeempleo', 'portal_talentbox', 'portal_colsubsidio', 
            'portal_unmejorempleo'
        ];
        checkboxes.forEach(id => {
            document.getElementById(id).checked = true;
        });
        mostrarNotificacion('Todos los portales seleccionados', 'info');
    });
    
    document.getElementById('btn-deseleccionar-todos-portales').addEventListener('click', function() {
        const checkboxes = [
            'portal_computrabajo', 'portal_elempleo', 'portal_magneto', 
            'portal_indeed', 'portal_trabajando', 'portal_linkedin',
            'portal_serviciodeempleo', 'portal_talentbox', 'portal_colsubsidio', 
            'portal_unmejorempleo'
        ];
        checkboxes.forEach(id => {
            document.getElementById(id).checked = false;
        });
        mostrarNotificacion('Todos los portales deseleccionados', 'info');
    });
    
    /**
     * Manejar envío del formulario de búsqueda
     */
    async function handleBusqueda(e) {
        e.preventDefault();
        
        // Validar formulario
        if (!validarFormulario()) {
            return;
        }
        
        // Obtener datos del formulario
        const datos = obtenerDatosFormulario();
        
        // Mostrar loading
        mostrarLoading();
        
        try {
            // Realizar búsqueda
            const response = await fetch('/buscar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(datos)
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Error en la búsqueda');
            }
            
            // Mostrar resultados
            mostrarResultados(result);
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error al realizar la búsqueda: ' + error.message);
            ocultarLoading();
        }
    }
    
    /**
     * Validar formulario antes de enviar
     */
    function validarFormulario() {
        const cargos = document.getElementById('cargos').value.trim();
        const ubicaciones = document.getElementById('ubicaciones').value.trim();
        
        if (!cargos) {
            alert('Debes especificar al menos un cargo');
            return false;
        }
        
        if (!ubicaciones) {
            alert('Debes especificar al menos una ubicación');
            return false;
        }
        
        // Validar que al menos un portal esté seleccionado
        const portales = [
            document.getElementById('portal_computrabajo').checked,
            document.getElementById('portal_elempleo').checked,
            document.getElementById('portal_magneto').checked,
            document.getElementById('portal_indeed').checked,
            document.getElementById('portal_trabajando').checked
        ];
        
        if (!portales.some(p => p)) {
            alert('Debes seleccionar al menos un portal de empleo');
            return false;
        }
        
        return true;
    }
    
    /**
     * Obtener datos del formulario
     */
    function obtenerDatosFormulario() {
        // Procesar cargos y ubicaciones (separados por líneas)
        const cargos = document.getElementById('cargos').value
            .split('\n')
            .map(c => c.trim())
            .filter(c => c.length > 0);
        
        const ubicaciones = document.getElementById('ubicaciones').value
            .split('\n')
            .map(u => u.trim())
            .filter(u => u.length > 0);
        
        // Obtener modalidades seleccionadas
        const modalidades = [];
        if (document.getElementById('mod_remoto').checked) modalidades.push('remoto');
        if (document.getElementById('mod_hibrido').checked) modalidades.push('híbrido');
        if (document.getElementById('mod_presencial').checked) modalidades.push('presencial');
        
        // Obtener keywords
        const keywords_incluir = document.getElementById('keywords_incluir').value
            .split('\n')
            .map(k => k.trim())
            .filter(k => k.length > 0);
        
        const keywords_excluir = document.getElementById('keywords_excluir').value
            .split('\n')
            .map(k => k.trim())
            .filter(k => k.length > 0);
        
        const keywords_bonus = document.getElementById('keywords_bonus').value
            .split('\n')
            .map(k => k.trim())
            .filter(k => k.length > 0);
        
        return {
            titulos: cargos,
            ubicaciones: ubicaciones,
            pais: 'Colombia',
            salario_minimo: parseInt(document.getElementById('salario_minimo').value) || 0,
            tipo_contrato: document.getElementById('tipo_contrato').value,
            escolaridad: document.getElementById('escolaridad').value,
            nivel_ingles: document.getElementById('nivel_ingles').value,
            modalidades: modalidades,
            experiencia_minima: parseInt(document.getElementById('experiencia_min').value) || 0,
            experiencia_maxima: parseInt(document.getElementById('experiencia_max').value) || 15,
            fecha_desde: document.getElementById('fecha_desde').value || null,
            fecha_hasta: document.getElementById('fecha_hasta').value || null,
            resultados_por_portal: parseInt(document.getElementById('resultados_por_portal').value) || 10,
            keywords_incluir: keywords_incluir,
            keywords_excluir: keywords_excluir,
            keywords_bonus: keywords_bonus,
            portal_computrabajo: document.getElementById('portal_computrabajo').checked,
            portal_elempleo: document.getElementById('portal_elempleo').checked,
            portal_magneto: document.getElementById('portal_magneto').checked,
            portal_indeed: document.getElementById('portal_indeed').checked,
            portal_trabajando: document.getElementById('portal_trabajando').checked,
            portal_linkedin: document.getElementById('portal_linkedin').checked,
            portal_serviciodeempleo: document.getElementById('portal_serviciodeempleo').checked,
            portal_talentbox: document.getElementById('portal_talentbox').checked,
            portal_colsubsidio: document.getElementById('portal_colsubsidio').checked,
            portal_unmejorempleo: document.getElementById('portal_unmejorempleo').checked
        };
    }
    
    /**
     * Mostrar loading spinner
     */
    function mostrarLoading() {
        loadingSection.classList.remove('d-none');
        resultadosSection.classList.add('d-none');
        btnBuscar.disabled = true;
        btnBuscar.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Buscando...';
    }
    
    /**
     * Ocultar loading spinner
     */
    function ocultarLoading() {
        loadingSection.classList.add('d-none');
        btnBuscar.disabled = false;
        btnBuscar.innerHTML = '<i class="fas fa-search me-2"></i>Buscar Ofertas';
    }
    
    /**
     * Mostrar resultados en la página
     */
    function mostrarResultados(result) {
        ocultarLoading();
        
        if (!result.success) {
            alert('Error: ' + (result.error || 'Error desconocido'));
            return;
        }
        
        // Mostrar sección de resultados
        resultadosSection.classList.remove('d-none');
        
        // Scroll suave a resultados
        resultadosSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // Actualizar estadísticas
        document.getElementById('total-ofertas').textContent = result.resumen.total_ofertas;
        document.getElementById('score-promedio').textContent = result.resumen.score_promedio.toFixed(1);
        document.getElementById('total-portales').textContent = result.resumen.portales_consultados;
        
        // Llenar tabla de resultados
        llenarTablaResultados(result.ofertas);
        
        // Mostrar notificación de éxito
        mostrarNotificacion(`¡Búsqueda completada! Se encontraron ${result.resumen.total_ofertas} ofertas`, 'success');
    }
    
    /**
     * Llenar tabla con los resultados
     */
    function llenarTablaResultados(ofertas) {
        const tbody = document.querySelector('#tabla-resultados tbody');
        tbody.innerHTML = '';
        
        if (ofertas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5">
                        <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                        <p class="text-muted">No se encontraron ofertas con los criterios especificados</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        ofertas.forEach(oferta => {
            const tr = document.createElement('tr');
            
            // Score con color
            const scoreColor = oferta.score >= 80 ? 'success' : oferta.score >= 60 ? 'warning' : 'secondary';
            
            tr.innerHTML = `
                <td>
                    <span class="badge bg-${scoreColor}" style="font-size: 1rem;">
                        ${oferta.score}
                    </span>
                </td>
                <td><strong>${oferta.titulo}</strong></td>
                <td>${oferta.empresa}</td>
                <td>
                    <i class="fas fa-map-marker-alt text-danger"></i>
                    ${oferta.ubicacion}
                </td>
                <td>
                    <span class="badge bg-info">${oferta.portal}</span>
                </td>
                <td>${oferta.fecha_publicacion || 'N/A'}</td>
                <td>
                    <a href="${oferta.link}" target="_blank" class="btn btn-sm btn-primary">
                        <i class="fas fa-external-link-alt"></i> Ver Oferta
                    </a>
                </td>
            `;
            
            tbody.appendChild(tr);
        });
    }
    
    /**
     * Limpiar formulario y restaurar valores por defecto
     */
    function limpiarFormulario() {
        if (confirm('¿Estás seguro de que quieres limpiar el formulario?')) {
            document.getElementById('cargos').value = 'Data Analyst\nFraud Analyst\nAnalista de Datos';
            document.getElementById('ubicaciones').value = 'Bogotá\nMedellín\nRemoto';
            document.getElementById('salario_minimo').value = '3000000';
            document.getElementById('tipo_contrato').value = 'indefinido';
            document.getElementById('experiencia_min').value = '0';
            document.getElementById('experiencia_max').value = '15';
            
            // Restablecer fechas
            const hoy = new Date().toISOString().split('T')[0];
            document.getElementById('fecha_hasta').value = hoy;
            const hace30dias = new Date();
            hace30dias.setDate(hace30dias.getDate() - 30);
            document.getElementById('fecha_desde').value = hace30dias.toISOString().split('T')[0];
            
            document.getElementById('keywords_incluir').value = '';
            document.getElementById('keywords_excluir').value = '';
            document.getElementById('keywords_bonus').value = 'clickhouse\npower bi\nremoto';
            
            // Checkboxes
            document.getElementById('mod_remoto').checked = true;
            document.getElementById('mod_hibrido').checked = true;
            document.getElementById('mod_presencial').checked = true;
            document.getElementById('portal_computrabajo').checked = true;
            document.getElementById('portal_elempleo').checked = false;
            document.getElementById('portal_magneto').checked = false;
            document.getElementById('portal_indeed').checked = false;
            document.getElementById('portal_trabajando').checked = false;
            document.getElementById('portal_linkedin').checked = false;
            document.getElementById('portal_serviciodeempleo').checked = false;
            document.getElementById('portal_talentbox').checked = false;
            document.getElementById('portal_colsubsidio').checked = false;
            document.getElementById('portal_unmejorempleo').checked = false;
            
            // Ocultar resultados
            resultadosSection.classList.add('d-none');
        }
    }
    
    /**
     * Exportar resultados a Excel
     */
    async function exportarExcel() {
        try {
            btnExportar.disabled = true;
            btnExportar.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Exportando...';
            
            const response = await fetch('/exportar');
            
            if (!response.ok) {
                throw new Error('Error al exportar');
            }
            
            // Descargar archivo
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ofertas_empleo_${new Date().getTime()}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            mostrarNotificacion('¡Archivo Excel descargado exitosamente!', 'success');
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error al exportar: ' + error.message);
        } finally {
            btnExportar.disabled = false;
            btnExportar.innerHTML = '<i class="fas fa-file-excel me-2"></i>Exportar Excel';
        }
    }
    
    /**
     * Mostrar notificación toast
     */
    function mostrarNotificacion(mensaje, tipo = 'info') {
        // Crear elemento de notificación
        const toast = document.createElement('div');
        toast.className = `alert alert-${tipo} alert-dismissible fade show position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
    
    // Agregar validación en tiempo real a los campos de fecha
    document.getElementById('fecha_desde').addEventListener('change', function() {
        const fechaDesde = new Date(this.value);
        const fechaHasta = new Date(document.getElementById('fecha_hasta').value);
        
        if (fechaDesde > fechaHasta) {
            alert('La fecha "Desde" no puede ser mayor que la fecha "Hasta"');
            this.value = '';
        }
    });
    
    document.getElementById('fecha_hasta').addEventListener('change', function() {
        const fechaDesde = new Date(document.getElementById('fecha_desde').value);
        const fechaHasta = new Date(this.value);
        
        if (fechaHasta < fechaDesde) {
            alert('La fecha "Hasta" no puede ser menor que la fecha "Desde"');
            this.value = '';
        }
    });
});
