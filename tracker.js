function extraerYEnviarDatos(imagenPlanilla = null) {
    const operador = document.getElementById('nombre')?.value || "Sin Nombre";
    const fecha = document.getElementById('fecha')?.value || new Date().toISOString().slice(0, 10);
    const horaInicio = document.getElementById('horaInicio')?.value || '';
    const horaCierre = document.getElementById('horaCierre')?.value || new Date().toLocaleTimeString();
    const hora = horaCierre;

    // Recopilar saldos iniciales
    const saldosInicio = {
        billetera: parseFloat(document.getElementById('iniBilletera')?.value) || 0,
        celu_apuestas: parseFloat(document.getElementById('iniCeluapuestas')?.value) || 0,
        ganamos: parseFloat(document.getElementById('iniGanamos')?.value) || 0,
        gana_en_casa: parseFloat(document.getElementById('iniGanaEnCasa')?.value) || 0,
        bet30: parseFloat(document.getElementById('iniBet30')?.value) || 0
    };

    // Recopilar filas de la tabla principal
    const filas = document.querySelectorAll('#filasPrincipales tr');
    let ingresos = [];
    let egresos = [];

    filas.forEach(fila => {
        const inputs = fila.querySelectorAll('input');
        if (inputs.length >= 9) {
            const usuarioIngreso = inputs[0].value.trim();
            const monto = parseFloat(inputs[1].value) || 0;
            
            if (usuarioIngreso !== "" || monto > 0) {
                ingresos.push({
                    usuario: usuarioIngreso,
                    monto: monto,
                    descuento: parseFloat(inputs[2].value) || 0,
                    dinamica: parseFloat(inputs[3].value) || 0,
                    fichas_gratis_nombre: inputs[4].value.trim(),
                    fichas_gratis_monto: parseFloat(inputs[5].value) || 0
                });
            }

            const usuarioEgreso = inputs[6].value.trim();
            const retiro = parseFloat(inputs[7].value) || 0;
            if (usuarioEgreso !== "" || retiro > 0) {
                egresos.push({
                    usuario: usuarioEgreso,
                    retiro_pct: retiro,
                    fr: parseFloat(inputs[8].value) || 0
                });
            }
        }
    });

    const totalCaja = parseFloat(
        document.getElementById('totalCaja')?.value
        || document.getElementById('totalFichasCierre')?.value
        || '0'
    ) || 0;

    const paqueteAuditoria = {
        usuario_id: window.CASINO_USER_ID ?? null,
        operador: operador,
        fecha: fecha,
        hora: hora,
        hora_inicio: horaInicio,
        hora_cierre: horaCierre,
        saldos_inicio: saldosInicio,
        ingresos: ingresos,
        egresos: egresos,
        total_caja: totalCaja,
        imagen_planilla: imagenPlanilla,
        estado_planilla: obtenerEstadoPlanilla()
    };

    if (!window.API_TOKEN) {
        console.error('No hay token de autenticación para registrar el cierre.');
        alert('La sesión expiró. Cierra sesión y vuelve a ingresar.');
        return Promise.resolve(null);
    }

    // Enviar por HTTP POST al FastAPI configurado para el entorno actual.
    const controlador = new AbortController();
    const timeout = setTimeout(() => controlador.abort(), 60000);

    return fetch(`${window.API_BASE_URL || 'http://127.0.0.1:8000/api/v1'}/cierre`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${window.API_TOKEN || ''}`
        },
        body: JSON.stringify(paqueteAuditoria),
        signal: controlador.signal
    })
    .then(async res => {
        if (!res.ok) {
            const detalle = await res.text();
            throw new Error(`La API respondió con HTTP ${res.status}: ${detalle}`);
        }
        return res.json();
    })
    .then(data => {
        console.log("Transacción enviada a la API de auditoría:", data);
        return data;
    })
    .catch(err => {
        console.error("Error enviando auditoría:", err);
        alert("No se pudo enviar el cierre. Verifica tu sesión y la conexión con la API.");
        return null;
    })
    .finally(() => {
        clearTimeout(timeout);
    });
}

function clavePlanilla() {
    return `planilla_valores_${window.CASINO_USER_ID ?? 'anonimo'}`;
}

function limpiarPlanilla() {
    localStorage.removeItem(clavePlanilla());
    localStorage.removeItem('planilla_valores');
    document.querySelectorAll('input, select, textarea').forEach(element => {
        element.value = '';
        element.removeAttribute('readonly');
        element.removeAttribute('disabled');
    });
    document.querySelectorAll('#filasPrincipales tr').forEach(fila => fila.remove());
    for (let i = 0; i < 15; i++) {
        if (typeof agregarFilaHTML === 'function') agregarFilaHTML();
    }
    asegurarIdsCampos();
}

function bloquearPlanilla() {
    document.querySelectorAll('input').forEach(input => {
        input.setAttribute('readonly', 'true');
        input.setAttribute('disabled', 'true');
    });
    document.querySelectorAll('button').forEach(button => {
        button.setAttribute('disabled', 'true');
    });
}

function obtenerEstadoPlanilla() {
    asegurarIdsCampos();
    const state = {};
    document.querySelectorAll('input, select, textarea').forEach(element => {
        if (element.id) state[element.id] = element.value;
    });
    return state;
}

function aplicarEstadoPlanilla(state) {
    if (!state) return;
    localStorage.removeItem('planilla_valores');
    document.querySelectorAll('input, select, textarea').forEach(element => {
        element.value = '';
    });
    Object.entries(state).forEach(([elementId, value]) => {
        const element = document.getElementById(elementId);
        if (element) element.value = value;
    });
    guardarTemporal();
}

function iniciarSincronizacionForzada() {
    if (window.WATCH_USER_ID === undefined || !window.API_TOKEN) return;
    const estadoUrl = `${window.API_BASE_URL}/planilla/${window.WATCH_USER_ID}/estado`;
    window.sincronizacionForzada = setInterval(async () => {
        try {
            const response = await fetch(estadoUrl, {
                headers: { Authorization: `Bearer ${window.API_TOKEN}` }
            });
            if (response.ok) aplicarEstadoPlanilla(await response.json());
        } catch (error) {
            console.debug('No se pudo sincronizar el estado de la planilla.');
        }
    }, 1500);
}

function configurarTiempoReal() {
    if (!window.API_TOKEN) {
        console.warn('WebSocket no iniciado: falta el token de autenticación.');
        return;
    }
    const apiUrl = new URL(window.API_BASE_URL || 'http://127.0.0.1:8000/api/v1');
    const wsScheme = apiUrl.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsScheme}://${apiUrl.host}/ws/live?token=${encodeURIComponent(window.API_TOKEN)}`;
    asegurarIdsCampos();
    conectarTiempoReal(wsUrl);
}

function conectarTiempoReal(wsUrl) {
    try {
        window.wsTiempoReal = new WebSocket(wsUrl);
        window.wsTiempoReal.onmessage = event => {
            const data = JSON.parse(event.data);
            if (data.type === 'closure_saved') {
                if (
                    window.WATCH_USER_ID !== undefined &&
                    Number(data.usuario_id) !== Number(window.WATCH_USER_ID)
                ) return;
                aplicarEstadoPlanilla(data.state);
                guardarTemporal();
                setTimeout(() => location.reload(), 300);
                return;
            }
            if (
                window.WATCH_USER_ID !== undefined &&
                Number(data.usuario_id) !== Number(window.WATCH_USER_ID)
            ) return;
            const element = document.getElementById(data.element_id);
            if (element && data.value !== undefined) {
                element.value = data.value;
                guardarTemporal();
            }
        };
        window.wsTiempoReal.onopen = () => {
            asegurarIdsCampos();
            const presencia = {
                type: 'presence',
                usuario_id: window.CASINO_USER_ID ?? null,
                nombre: window.CASINO_USER_NAME || 'Usuario',
                rol: window.CASINO_USER_ROLE || 'empleado'
            };
            window.wsTiempoReal.send(JSON.stringify(presencia));
            clearInterval(window.presenciaInterval);
            window.presenciaInterval = setInterval(() => {
                if (window.wsTiempoReal?.readyState === WebSocket.OPEN) {
                    window.wsTiempoReal.send(JSON.stringify(presencia));
                }
            }, 20000);
            Object.entries(window.cambiosPendientes || {}).forEach(([elementId, value]) => {
                window.wsTiempoReal.send(JSON.stringify({
                    type: 'cell_update',
                    usuario_id: window.CASINO_USER_ID ?? null,
                    element_id: elementId,
                    value: value
                }));
            });
            window.cambiosPendientes = {};
            if (!window.PLANILLA_READONLY) {
                Object.entries(obtenerEstadoPlanilla()).forEach(([elementId, value]) => {
                    window.wsTiempoReal.send(JSON.stringify({
                        type: 'cell_update',
                        usuario_id: window.CASINO_USER_ID ?? null,
                        element_id: elementId,
                        value: value
                    }));
                });
            }
            if (window.PLANILLA_READONLY) {
                document.querySelectorAll('input, button').forEach(element => {
                    element.disabled = true;
                });
            }
        };
        window.wsTiempoReal.onclose = () => {
            clearInterval(window.presenciaInterval);
            window.wsTiempoReal = null;
            setTimeout(() => conectarTiempoReal(wsUrl), 1000);
        };
    } catch (error) {
        console.log('WebSocket no disponible localmente.');
        setTimeout(() => conectarTiempoReal(wsUrl), 1000);
    }
}

window.addEventListener('beforeunload', () => {
    clearInterval(window.presenciaInterval);
    clearInterval(window.sincronizacionForzada);
    if (window.wsTiempoReal?.readyState === WebSocket.OPEN) {
        window.wsTiempoReal.close();
    }
});

function asegurarIdsCampos() {
    document.querySelectorAll('input').forEach((input, index) => {
        if (!input.id) input.id = `campo-${index}`;
        ajustarAnchoCampo(input);
    });
}

function ajustarAnchoCampo(elemento) {
    if (!(elemento instanceof HTMLInputElement)) return;
    if (elemento.classList.contains('hora-campo')) {
        elemento.style.width = '100%';
        elemento.style.minWidth = '62px';
        return;
    }
    const contenido = elemento.value || elemento.placeholder || '';
    const canvas = ajustarAnchoCampo.canvas || (ajustarAnchoCampo.canvas = document.createElement('canvas'));
    const context = canvas.getContext('2d');
    context.font = getComputedStyle(elemento).font;
    const ancho = Math.ceil(context.measureText(contenido).width) + 18;
    const minimo = elemento.classList.contains('editable-texto-largo') ? 120 : 48;
    elemento.style.width = `${Math.min(320, Math.max(minimo, ancho))}px`;
    elemento.title = elemento.value;
}

function transmitirCambioWebSocket(elemento) {
    if (!(elemento instanceof HTMLInputElement || elemento instanceof HTMLSelectElement || elemento instanceof HTMLTextAreaElement)) {
        return;
    }
    asegurarIdsCampos();
    ajustarAnchoCampo(elemento);
    if (!elemento.id || window.PLANILLA_READONLY) return;

    const cambio = {
        type: 'cell_update',
        usuario_id: window.CASINO_USER_ID ?? null,
        element_id: elemento.id,
        value: elemento.value
    };
    if (window.wsTiempoReal?.readyState === WebSocket.OPEN) {
        window.wsTiempoReal.send(JSON.stringify(cambio));
    } else {
        window.cambiosPendientes = window.cambiosPendientes || {};
        window.cambiosPendientes[elemento.id] = elemento.value;
    }
}

// Compatibilidad con los atributos oninput existentes en index.html.
function emitirTiempoReal(elemento) {
    transmitirCambioWebSocket(elemento);
}

document.addEventListener('input', event => {
    transmitirCambioWebSocket(event.target);
});

document.addEventListener('change', event => {
    transmitirCambioWebSocket(event.target);
});

document.addEventListener('DOMNodeInserted', event => {
    if (event.target instanceof HTMLInputElement) {
        asegurarIdsCampos();
    }
});

window.addEventListener('load', () => {
    configurarTiempoReal();
    iniciarSincronizacionForzada();
});