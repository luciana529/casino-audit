function extraerYEnviarDatos() {
    const operador = document.getElementById('nombre')?.value || "Sin Nombre";
    const fecha = document.getElementById('fecha')?.value || new Date().toISOString().slice(0, 10);
    const hora = document.getElementById('hora')?.value || new Date().toLocaleTimeString();

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

    const totalCaja = parseFloat(document.getElementById('totalFichasCierre')?.value) || 0;

    const paqueteAuditoria = {
        operador: operador,
        fecha: fecha,
        hora: hora,
        saldos_inicio: saldosInicio,
        ingresos: ingresos,
        egresos: egresos,
        total_caja: totalCaja
    };

    // Enviar por HTTP POST a FastAPI
    return fetch("http://127.0.0.1:8000/api/v1/cierre", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(paqueteAuditoria)
    })
    .then(res => res.json())
    .then(data => console.log("Transacción enviada a la API de auditoría:", data))
    .catch(err => {
        console.error("Error enviando auditoría:", err);
        alert("No se pudo enviar el cierre a la API. Verifica que FastAPI esté ejecutándose.");
    });
}