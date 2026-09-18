function extraerYEnviarDatos() {
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
        total_caja: totalCaja
    };

    // Enviar por HTTP POST al FastAPI local
    const controlador = new AbortController();
    const timeout = setTimeout(() => controlador.abort(), 10000);

    return fetch(`${window.API_BASE_URL || 'http://127.0.0.1:8000/api/v1'}/cierre`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${window.API_TOKEN || ''}`
        },
        body: JSON.stringify(paqueteAuditoria),
        signal: controlador.signal
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`La API respondió con HTTP ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        console.log("Transacción enviada a la API de auditoría:", data);
        bloquearPlanilla();
        return data;
    })
    .catch(err => {
        console.error("Error enviando auditoría:", err);
        alert("No se pudo enviar el cierre a la API. Verifica que FastAPI esté ejecutándose en el puerto 8000.");
        return null;
    })
    .finally(() => {
        clearTimeout(timeout);
    });
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

function configurarTiempoReal() {
    const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${window.API_HOST || '127.0.0.1:8000'}/ws/live?token=${encodeURIComponent(window.API_TOKEN || '')}`;
    asegurarIdsCampos();
    conectarTiempoReal(wsUrl);
}

function conectarTiempoReal(wsUrl) {
    try {
        window.wsTiempoReal = new WebSocket(wsUrl);
        window.wsTiempoReal.onmessage = event => {
            const data = JSON.parse(event.data);
            if (
                window.WATCH_USER_ID !== undefined &&
                Number(data.usuario_id) !== Number(window.WATCH_USER_ID)
            ) return;
            const element = document.getElementById(data.element_id);
            if (element && data.value !== undefined) {
                element.value = data.value;
            }
        };
        window.wsTiempoReal.onopen = () => {
            asegurarIdsCampos();
            window.wsTiempoReal.send(JSON.stringify({
                type: 'presence',
                usuario_id: window.CASINO_USER_ID ?? null,
                nombre: window.CASINO_USER_NAME || 'Usuario',
                rol: window.CASINO_USER_ROLE || 'empleado'
            }));
            Object.entries(window.cambiosPendientes || {}).forEach(([elementId, value]) => {
                window.wsTiempoReal.send(JSON.stringify({
                    usuario_id: window.CASINO_USER_ID ?? null,
                    element_id: elementId,
                    value: value
                }));
            });
            window.cambiosPendientes = {};
            if (window.PLANILLA_READONLY) {
                document.querySelectorAll('input, button').forEach(element => {
                    element.disabled = true;
                });
            }
        };
        window.wsTiempoReal.onclose = () => {
            window.wsTiempoReal = null;
            setTimeout(() => conectarTiempoReal(wsUrl), 1000);
        };
    } catch (error) {
        console.log('WebSocket no disponible localmente.');
        setTimeout(() => conectarTiempoReal(wsUrl), 1000);
    }
}

window.addEventListener('beforeunload', () => {
    if (window.wsTiempoReal?.readyState === WebSocket.OPEN) {
        window.wsTiempoReal.close();
    }
});

function asegurarIdsCampos() {
    document.querySelectorAll('input').forEach((input, index) => {
        if (!input.id) input.id = `campo-${index}`;
    });
}

document.addEventListener('input', event => {
    const input = event.target;
    if (input instanceof HTMLInputElement) {
        asegurarIdsCampos();
    }
    if (
        input instanceof HTMLInputElement &&
        input.id &&
        !window.PLANILLA_READONLY
    ) {
        const cambio = {
            usuario_id: window.CASINO_USER_ID ?? null,
            element_id: input.id,
            value: input.value
        };
        if (window.wsTiempoReal?.readyState === WebSocket.OPEN) {
            window.wsTiempoReal.send(JSON.stringify(cambio));
        } else {
            window.cambiosPendientes = window.cambiosPendientes || {};
            window.cambiosPendientes[input.id] = input.value;
        }
    }
});

window.addEventListener('load', configurarTiempoReal);