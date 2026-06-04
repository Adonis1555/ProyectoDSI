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
                    alert("¡Maestro y usuario creados con éxito!");
                    window.location.href = urlRedireccion; 
                } else {
                    alert("Error: " + data.error);
                }
            }catch(error)
            {
                console.error("Error en el servidor:", error);
                alert("Hubo un problema al conectar con el servidor."); 
            }
        });
    }

});