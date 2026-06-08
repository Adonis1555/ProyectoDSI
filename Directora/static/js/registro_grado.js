const scriptSwal = document.createElement('script');
scriptSwal.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
document.head.appendChild(scriptSwal);

document.addEventListener('DOMContentLoaded', () => {
    const formGrado = document.getElementById('formGrado');

    if (formGrado) {
        formGrado.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const urlEnvio = formGrado.getAttribute('data-url') || formGrado.getAttribute('action');
            const urlRedireccion = formGrado.getAttribute('data-redirect');

            Swal.fire({
                title: 'Procesando registro',
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
                        title: '¡Registro Exitoso!',
                        text: data.mensaje || 'El grado y sección han sido creados correctamente.',
                        confirmButtonColor: '#2b6cb0',
                        timer: 2500,
                        timerProgressBar: true
                    }).then(() => {
                        window.location.href = urlRedireccion; 
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo registrar',
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