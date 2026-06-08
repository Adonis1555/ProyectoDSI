document.addEventListener('DOMContentLoaded', () => {
    const btnAgregar = document.getElementById('btnAgregarIncidencia');

    if (btnAgregar) {
        btnAgregar.addEventListener('click', function() {
            Swal.fire({
                title: 'Registrar Nueva Incidencia',
                html: `
                    <div style="display: flex; flex-direction: column; gap: 12px; text-align: left; font-family: 'Inter', sans-serif;">
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <label style="font-size: 13px; color: #64748b; font-weight: 500;">Fecha del Incidente:</label>
                            <input type="date" id="swal-fecha" class="swal2-input" style="margin: 0; width: 100%; height: 38px; font-size: 14px;" value="${new Date().toISOString().split('T')[0]}">
                        </div>
                        
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <label style="font-size: 13px; color: #64748b; font-weight: 500;">Tipo de Registro:</label>
                            <select id="swal-tipo" class="swal2-input" style="margin: 0; width: 100%; height: 38px; font-size: 14px; padding: 0 10px;">
                                <option value="D">Demérito</option>
                                <option value="R">Redención</option>
                                <option value="RC">Reconocimiento</option>
                            </select>
                        </div>

                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <label style="font-size: 13px; color: #64748b; font-weight: 500;">Clasificación / Sub-letra (A, B, C, D):</label>
                            <select id="swal-letra" class="swal2-input" style="margin: 0; width: 100%; height: 38px; font-size: 14px; padding: 0 10px;">
                                <option value="A">A (Leve / Inicial / Estímulo A)</option>
                                <option value="B">B (Grave / Intermedia / Estímulo B)</option>
                                <option value="C">C (Muy Grave / Avanzada)</option>
                                <option value="D">D (Reiterada / Máxima)</option>
                            </select>
                        </div>

                    </div>
                `,
                focusConfirm: false,
                showCancelButton: true,
                confirmButtonText: 'Guardar Registro',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#2E5299',
                cancelButtonColor: '#cbd5e1',
                preConfirm: () => {
                    const fecha = document.getElementById('swal-fecha').value;
                    const tipo = document.getElementById('swal-tipo').value;
                    const sub_letra = document.getElementById('swal-letra').value;
                    return {
                        fecha: fecha,
                        tipo_registro: tipo,
                        escala: sub_letra,
                    }
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    const alumnoNie = window.alumnoNie; 
                    const csrfToken = window.csrfToken;

                    fetch(`/maestros/registrar_demerito/${alumnoNie}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify(result.value)
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.ok) {
                            Swal.fire({
                                icon: 'success',
                                title: '¡Registrado!',
                                text: 'La incidencia se agregó correctamente a la tarjeta.',
                                confirmButtonColor: '#2E5299'
                            }).then(() => {
                                window.location.reload(); 
                            });
                        } else {
                            Swal.fire({
                                icon: 'error',
                                title: 'Error',
                                text: data.error || 'No se pudo guardar el registro.',
                                confirmButtonColor: '#2E5299'
                            });
                        }
                    })
                    .catch(error => {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error de red',
                            text: 'Hubo un fallo de comunicación con el servidor.',
                            confirmButtonColor: '#2E5299'
                        });
                    });
                }
            });
        });
    }
});