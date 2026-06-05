const scriptSwal = document.createElement('script');
scriptSwal.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
document.head.appendChild(scriptSwal);

document.addEventListener('DOMContentLoaded', ()=>{
    const inputFechaNac = document.getElementById('inputFechaNac');
    if (inputFechaNac) {
        const hoy = new Date();
        const anioLimite = hoy.getFullYear() - 22;
        const mes = String(hoy.getMonth() + 1).padStart(2, '0');
        const dia = String(hoy.getDate()).padStart(2, '0');
        const fechaMaxima = `${anioLimite}-${mes}-${dia}`;
        inputFechaNac.setAttribute('max', fechaMaxima);
    }

    const inputDui = document.getElementById('inputDui');
    if (inputDui) {
        inputDui.addEventListener('input', (e) => {
            let valor = e.target.value.replace(/\D/g, '');
            if (valor.length > 8) {
                valor = valor.substring(0, 8) + '-' + valor.substring(8, 9);
            }
            e.target.value = valor;
        });
    }

    const inputTelefono = document.getElementById('inputTelefono');
    if (inputTelefono) {
        inputTelefono.addEventListener('input', (e) => {
            let valor = e.target.value.replace(/\D/g, '');
            if (valor.length > 4) {
                valor = valor.substring(0, 4) + '-' + valor.substring(4, 8);
            }
            e.target.value = valor;
        });
    }
    
    
    const formMaestro = document.getElementById('formMaestro');

    if(formMaestro){
        
        formMaestro.addEventListener('submit', async (e) =>{
            e.preventDefault();

            const formData=new FormData(e.target);
            const urlEnvio = formMaestro.getAttribute('data-url');
            const urlRedireccion = formMaestro.getAttribute('data-redirect');

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
            try{
                const response=await fetch(urlEnvio,{
                    method: "POST",
                    body:formData,
                    headers: {
                        "X-CSRFToken": formData.get("csrfmiddlewaretoken")
                    }
                });
                const data = await response.json();

                if (data.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Registro Exitoso!',
                        text: 'El maestro y su usuario han sido creados correctamente.',
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
            }catch(error)
            {
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