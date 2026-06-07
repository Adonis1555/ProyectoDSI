const scriptSwal = document.createElement('script');
scriptSwal.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
document.head.appendChild(scriptSwal);

document.addEventListener('DOMContentLoaded', ()=>{
    const inputFechaNac = document.getElementById('inputFechaNac');
    if (inputFechaNac) {
        const hoy = new Date();
        const anioLimite = hoy.getFullYear() - 4;
        const anioMaximo = hoy.getFullYear() - 100
        const mes = String(hoy.getMonth() + 1).padStart(2, '0');
        const dia = String(hoy.getDate()).padStart(2, '0');
        const fechaMinima = `${anioLimite}-${mes}-${dia}`;
        const fechaMaxima=`${anioMaximo}-${mes}-${dia}`;
        inputFechaNac.setAttribute('max', fechaMinima);
        inputFechaNac.setAttribute('min',fechaMaxima)
    }

    const formAlumnos = document.getElementById("formRegistroAlumno")

    if(formAlumnos){
        
        formAlumnos.addEventListener('submit', async (e) =>{
            e.preventDefault();

            const formData=new FormData(e.target);
            const urlEnvio = formAlumnos.getAttribute('data-url');
            const urlRedireccion = formAlumnos.getAttribute('data-redirect');

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
                        text: 'El Alumno se ingreso con éxito.',
                        confirmButtonColor: '#2b6cb0',
                        timer: 2500,
                        timerProgressBar: true
                    }).then(() => {
                        e.target.reset();
                        window.location.href = urlRedireccion; 

                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'No se pudo registrar',
                        text: data.error,
                        confirmButtonColor: '#2b6cb0'
                    }).then( () =>{
                        e.target.reset();
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