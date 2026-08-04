const API_BASE = window.location.origin === 'null' ? 'http://127.0.0.1:8000' : '';
let chartInstance = null;
let compChartInstance = null;
let currentView = 'horas';
let compView = 'dias';

// Elementos DOM - Dashboard
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const loadingOverlay = document.getElementById('loadingOverlay');
const btnHoras = document.getElementById('btnHoras');
const btnDias = document.getElementById('btnDias');
const btnAplicarRango = document.getElementById('btnAplicarRango');
const btnPDF = document.getElementById('btnPDF');
const fechaInicio = document.getElementById('fechaInicio');
const fechaFin = document.getElementById('fechaFin');
const kpiTotal = document.getElementById('kpiTotal');
const kpiPromedio = document.getElementById('kpiPromedio');
const kpiHoraPico = document.getElementById('kpiHoraPico');
const kpiHoraPicoUnit = document.getElementById('kpiHoraPicoUnit');
const ctx = document.getElementById('consumoChart').getContext('2d');

// Elementos DOM - Comparativa
const btnCompHoras = document.getElementById('btnCompHoras');
const btnCompDias = document.getElementById('btnCompDias');
const btnComparar = document.getElementById('btnComparar');
const compFecha1Inicio = document.getElementById('compFecha1Inicio');
const compFecha1Fin = document.getElementById('compFecha1Fin');
const compFecha2Inicio = document.getElementById('compFecha2Inicio');
const compFecha2Fin = document.getElementById('compFecha2Fin');
const compResultados = document.getElementById('comparativaResultados');
const compTotal1 = document.getElementById('compTotal1');
const compDias1 = document.getElementById('compDias1');
const compTotal2 = document.getElementById('compTotal2');
const compDias2 = document.getElementById('compDias2');
const compDiferencia = document.getElementById('compDiferencia');
const compDiferenciaPct = document.getElementById('compDiferenciaPct');
const compDiferenciaLabel = document.getElementById('compDiferenciaLabel');
const compCtx = document.getElementById('comparativaChart').getContext('2d');

// Estado de conexión
function setStatus(state, text) {
    statusIndicator.className = 'status-indicator ' + state;
    statusText.textContent = text;
}

// Loading
function showLoading(show) {
    loadingOverlay.classList.toggle('active', show);
}

// API helper
async function fetchAPI(endpoint) {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

// Construir query string con fechas si están disponibles
function getDateQuery() {
    if (fechaInicio.value && fechaFin.value) {
        return `?inicio=${fechaInicio.value}&fin=${fechaFin.value}`;
    }
    return '';
}

// Inicializar fechas disponibles
async function initDateRange() {
    try {
        const data = await fetchAPI('/api/datos/disponibles');
        if (data.min && data.max) {
            // Dashboard
            fechaInicio.value = data.min;
            fechaFin.value = data.max;
            fechaInicio.min = data.min;
            fechaInicio.max = data.max;
            fechaFin.min = data.min;
            fechaFin.max = data.max;
            
            // Comparativa
            const minDate = new Date(data.min);
            const maxDate = new Date(data.max);
            const midDate = new Date(minDate.getTime() + (maxDate.getTime() - minDate.getTime()) / 2);
            
            // Período 1: desde inicio hasta la mitad
            compFecha1Inicio.value = data.min;
            compFecha1Fin.value = midDate.toISOString().split('T')[0];
            compFecha1Inicio.min = data.min;
            compFecha1Inicio.max = data.max;
            compFecha1Fin.min = data.min;
            compFecha1Fin.max = data.max;
            
            // Período 2: desde la mitad hasta el final
            const midPlus1 = new Date(midDate);
            midPlus1.setDate(midPlus1.getDate() + 1);
            compFecha2Inicio.value = midPlus1.toISOString().split('T')[0];
            compFecha2Fin.value = data.max;
            compFecha2Inicio.min = data.min;
            compFecha2Inicio.max = data.max;
            compFecha2Fin.min = data.min;
            compFecha2Fin.max = data.max;
        }
    } catch (e) {
        console.error('Error al obtener fechas:', e);
    }
}

// Cargar KPIs según el filtro actual
async function loadKPIs(dateQuery = '') {
    try {
        const data = await fetchAPI(`/api/resumen${dateQuery}`);
        kpiTotal.textContent = data.total_kwh.toFixed(2);
        kpiPromedio.textContent = data.promedio_diario_kwh.toFixed(2);
        kpiHoraPico.textContent = data.hora_pico;
        kpiHoraPicoUnit.textContent = `${data.hora_pico_kwh.toFixed(3)} kWh promedio`;
    } catch (e) {
        console.error('Error al cargar KPIs:', e);
    }
}

// Cargar datos del gráfico
async function loadChartData(view, inicio = null, fin = null) {
    showLoading(true);
    try {
        let data;
        let label, datasetLabel, color;
        let dateQuery = '';

        if (view === 'rango' && inicio && fin) {
            data = await fetchAPI(`/api/consumo/rango?inicio=${inicio}&fin=${fin}`);
            label = 'fecha';
            datasetLabel = 'Consumo (kWh)';
            color = '#22c55e';
            dateQuery = `?inicio=${inicio}&fin=${fin}`;
        } else if (view === 'dias') {
            dateQuery = getDateQuery();
            data = await fetchAPI(`/api/consumo/dias${dateQuery}`);
            label = 'fecha';
            datasetLabel = 'Consumo Diario (kWh)';
            color = '#3b82f6';
        } else {
            dateQuery = getDateQuery();
            data = await fetchAPI(`/api/consumo/horas${dateQuery}`);
            label = 'hora';
            datasetLabel = 'Consumo Promedio (kWh)';
            color = '#eab308';
        }

        updateChart(data, label, datasetLabel, color);

        // Actualizar KPIs con el mismo filtro
        if (view === 'rango' && inicio && fin) {
            await loadKPIs(`?inicio=${inicio}&fin=${fin}`);
        } else {
            await loadKPIs(dateQuery);
        }
    } catch (e) {
        console.error('Error al cargar datos del gráfico:', e);
    } finally {
        showLoading(false);
    }
}

// Actualizar gráfico principal
function updateChart(data, labelKey, datasetLabel, color) {
    if (chartInstance) {
        chartInstance.destroy();
    }

    const labels = data.map(d => d[labelKey]);
    const values = data.map(d => d.kwh);

    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, color);
    gradient.addColorStop(1, color + '33');

    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: datasetLabel,
                data: values,
                backgroundColor: gradient,
                borderColor: color,
                borderWidth: 2,
                borderRadius: 4,
                hoverBackgroundColor: color,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y.toFixed(3)} kWh`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#33415533', drawBorder: false },
                    ticks: { color: '#94a3b8', maxRotation: 45, font: { size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#33415533', drawBorder: false },
                    ticks: {
                        color: '#94a3b8',
                        font: { size: 11 },
                        callback: function(value) {
                            return value.toFixed(2) + ' kWh';
                        }
                    }
                }
            }
        }
    });
}

// Cambiar vista del dashboard
function setView(view) {
    currentView = view;
    btnHoras.classList.toggle('btn-active', view === 'horas');
    btnDias.classList.toggle('btn-active', view === 'dias');
    loadChartData(view);
}

// Aplicar rango de fechas personalizado
async function aplicarRango() {
    const inicio = fechaInicio.value;
    const fin = fechaFin.value;

    if (!inicio || !fin || inicio > fin) return;

    btnHoras.classList.remove('btn-active');
    btnDias.classList.remove('btn-active');
    currentView = 'rango';

    await loadChartData('rango', inicio, fin);
}

// ============================================
// COMPARATIVA DE PERÍODOS
// ============================================

function setCompView(view) {
    compView = view;
    btnCompHoras.classList.toggle('btn-comp-active', view === 'horas');
    btnCompDias.classList.toggle('btn-comp-active', view === 'dias');
}

async function cargarComparativa() {
    const i1 = compFecha1Inicio.value;
    const f1 = compFecha1Fin.value;
    const i2 = compFecha2Inicio.value;
    const f2 = compFecha2Fin.value;

    if (!i1 || !f1 || !i2 || !f2) return;
    if (i1 > f1 || i2 > f2) return;

    showLoading(true);
    try {
        const data = await fetchAPI(
            `/api/comparativa?inicio1=${i1}&fin1=${f1}&inicio2=${i2}&fin2=${f2}&tipo=${compView}`
        );

        // Mostrar resultados
        compResultados.style.display = 'block';

        // Período 1
        compTotal1.textContent = data.periodo1.total_kwh.toFixed(2);
        compDias1.textContent = `${data.periodo1.dias} días`;

        // Período 2
        compTotal2.textContent = data.periodo2.total_kwh.toFixed(2);
        compDias2.textContent = `${data.periodo2.dias} días`;

        // Diferencia
        const diff = data.diferencia;
        const prefix = diff.tendencia === 'sube' ? '+' : (diff.tendencia === 'baja' ? '' : '');
        compDiferencia.textContent = `${prefix}${diff.total_kwh.toFixed(2)} kWh`;
        compDiferencia.style.color = diff.tendencia === 'sube' ? '#ef4444' : (diff.tendencia === 'baja' ? '#22c55e' : '#94a3b8');
        
        const pctPrefix = diff.tendencia === 'sube' ? '+' : '';
        compDiferenciaPct.textContent = `(${pctPrefix}${diff.porcentaje}%)`;
        compDiferenciaPct.style.color = compDiferencia.style.color;

        compDiferenciaLabel.textContent = diff.tendencia === 'sube' ? '⚠️ AUMENTÓ' : (diff.tendencia === 'baja' ? '✅ DISMINUYÓ' : '➖ SIN CAMBIO');
        compDiferenciaLabel.className = 'comp-diff-label ' + diff.tendencia;

        // Gráfico comparativo
        actualizarGraficoComparativo(data.datos);
    } catch (e) {
        console.error('Error al cargar comparativa:', e);
    } finally {
        showLoading(false);
    }
}

function actualizarGraficoComparativo(datos) {
    if (compChartInstance) {
        compChartInstance.destroy();
    }

    const labels = datos.map(d => d.hora || d.indice);
    const valores1 = datos.map(d => d.periodo1);
    const valores2 = datos.map(d => d.periodo2);

    compChartInstance = new Chart(compCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Período 1',
                    data: valores1,
                    backgroundColor: 'rgba(59, 130, 246, 0.7)',
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    borderRadius: 4,
                },
                {
                    label: 'Período 2',
                    data: valores2,
                    backgroundColor: 'rgba(34, 197, 94, 0.7)',
                    borderColor: '#22c55e',
                    borderWidth: 2,
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: { size: 12 },
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.parsed.y.toFixed(3)} kWh`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#33415533', drawBorder: false },
                    ticks: { color: '#94a3b8', maxRotation: 45, font: { size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#33415533', drawBorder: false },
                    ticks: {
                        color: '#94a3b8',
                        font: { size: 11 },
                        callback: function(value) {
                            return value.toFixed(2) + ' kWh';
                        }
                    }
                }
            }
        }
    });
}

// Verificar conexión con el backend
async function checkConnection() {
    try {
        setStatus('loading', 'Conectando...');
        await fetchAPI('/api/resumen');
        setStatus('online', 'Conectado');
        return true;
    } catch (e) {
        setStatus('offline', 'Desconectado');
        return false;
    }
}

// ============================================
// GENERAR INFORME PDF
// ============================================

function generarPDF() {
    const inicio = fechaInicio.value;
    const fin = fechaFin.value;

    if (!inicio || !fin) {
        return;
    }

    // Abrir el PDF en una nueva pestaña (descarga automática)
    const url = `${API_BASE}/api/informe/pdf?inicio=${inicio}&fin=${fin}&titulo=Informe%20de%20Consumo%20El%C3%A9ctrico`;
    window.open(url, '_blank');
}

// Inicializar todo
async function init() {
    const connected = await checkConnection();

    if (connected) {
        await initDateRange();
        // Cargar vista inicial "Por Horas" con rango completo
        await loadChartData('horas');
        // Auto-cargar comparativa inicial
        await cargarComparativa();
    }

    // Event listeners - Dashboard
    btnHoras.addEventListener('click', () => setView('horas'));
    btnDias.addEventListener('click', () => setView('dias'));
    btnAplicarRango.addEventListener('click', aplicarRango);
    btnPDF.addEventListener('click', generarPDF);

    // Event listeners - Comparativa
    btnCompHoras.addEventListener('click', () => { setCompView('horas'); });
    btnCompDias.addEventListener('click', () => { setCompView('dias'); });
    btnComparar.addEventListener('click', cargarComparativa);

    // Reintentar conexión cada 10 segundos si está desconectado
    if (!connected) {
        setInterval(async () => {
            const reconnected = await checkConnection();
            if (reconnected) {
                await initDateRange();
                await loadChartData('horas');
            }
        }, 10000);
    }
}

// Iniciar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', init);