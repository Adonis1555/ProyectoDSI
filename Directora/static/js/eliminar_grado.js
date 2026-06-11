const scriptSwal = document.createElement('script');
src="https://cdn.jsdelivr.net/npm/sweetalert2@11"

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.btn-eliminar-seccion').forEach(boton => {
        boton.addEventListener('click', function() {
            const seccionId = this.getAttribute('data-id');
            const nombreCompleto = this.getAttribute('data-nombre');
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            Swal.fire({
                title: '¿Estás seguro?',
                text: `Se eliminará de forma permanente el "${nombreCompleto}". Esta acción no se puede deshacer.`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#ef4444',
                cancelButtonColor: '#cbd5e1',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            }).then((result) => {
                if (result.isConfirmed) {

                    fetch(`/directora/eliminar_grado_seccion/${seccionId}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Content-Type': 'application/json'
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.ok) {
                            Swal.fire({
                                icon: 'success',
                                title: '¡Eliminado!',
                                text: data.mensaje || 'El registro fue borrado correctamente.',
                                confirmButtonColor: '#2E5299'
                            }).then(() => {
                                window.location.reload(); 
                            });
                        } else {
                            Swal.fire({
                                icon: 'error',
                                title: 'Error',
                                text: data.error || 'No se pudo eliminar el registro.',
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
    });
});