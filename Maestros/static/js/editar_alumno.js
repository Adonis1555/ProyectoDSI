const scriptSwal = document.createElement('script');
scriptSwal.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
document.head.appendChild(scriptSwal);

document.addEventListener('DOMContentLoaded', () => {
    const inputGrado = document.getElementById('inputGrado');
    const inputSeccion = document.getElementById('inputSeccion');
    const demeritosSecciones = window.seccionesPorGrado || {};
    
    const formEditar = document.getElementById('formEditarAlumno');
    const currentGrado = formEditar.getAttribute('data-current-grado');
    const currentSeccion = formEditar.getAttribute('data-current-seccion');

    const populateSecciones = (grado, selectedSeccion = '') => {
        inputSeccion.innerHTML = '<option value="" disabled>Seleccione...</option>';
        if (grado && demeritosSecciones[grado]) {
            demeritosSecciones[grado].forEach(seccion => {
                const option = document.createElement('option');
                option.value = seccion;
                option.textContent = `Sección ${seccion}`;
                if (seccion === selectedSeccion) {
                    option.selected = true;
                }
                inputSeccion.appendChild(option);
            });
            inputSeccion.disabled = false;
        } else {
            inputSeccion.innerHTML = '<option value="" disabled selected>Seleccione grado primero...</option>';
            inputSeccion.disabled = true;
        }
    };

    if (inputGrado && inputSeccion) {
        // Pre-populado inicial
        if (currentGrado) {
            populateSecciones(currentGrado, currentSeccion);
        }

        inputGrado.addEventListener('change', (e) => {
            populateSecciones(e.target.value);
        });
    }

    const inputFechaNac = document.getElementById('inputFechaNac');
    if (inputFechaNac) {
        const hoy = new Date();
        const anioLimite = hoy.getFullYear() - 4;
        const anioMaximo = hoy.getFullYear() - 100;
        const mes = String(hoy.getMonth() + 1).padStart(2, '0');
        const dia = String(hoy.getDate()).padStart(2, '0');
        inputFechaNac.setAttribute('max', `${anioLimite}-${mes}-${dia}`);
        inputFechaNac.setAttribute('min', `${anioMaximo}-${mes}-${dia}`);
    }

    if (formEditar) {
        formEditar.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const urlEnvio = formEditar.getAttribute('data-url');
            const urlRedireccion = formEditar.getAttribute('data-redirect');

            Swal.fire({
                title: 'Procesando cambios',
                text: 'Por favor, espera un momento.',
                allowOutsideClick: false,
                allowEscapeKey: false,
                showConfirmButton: false,
                didOpen: () => {
                    Swal.showLoading(); 
                }
            });

            try {
                const response = await fetch(urlEnvio, {
                    method: "POST",
                    body: formData,
                    headers: {
                        "X-CSRFToken": formData.get("csrfmiddlewaretoken")
                    }
                });
                const data = await response.json();

                if (data.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Cambios Guardados!',
                        text: 'El alumno se ha actualizado con éxito.',
                        confirmButtonColor: '#2b6cb0',
                        timer: 2500,
                        timerProgressBar: true
                    }).then(() => {
                        window.location.href = urlRedireccion; 
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo guardar',
                        text: data.error,
                        confirmButtonColor: '#2b6cb0'
                    });
                }
            } catch (error) {
                console.error("Error en el servidor:", error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error de conexión',
                    text: 'Hubo un problema al conectar con el servidor. Inténtalo de nuevo más tarde.',
                    confirmButtonColor: '#2b6cb0'
                });
            }
        });
    }
});
