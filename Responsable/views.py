from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from Directora.models import GradoSeccion
from django.contrib import messages
from .models import Responsable, FichaMatricula


@responsable_required
@login_required
def responsable_view(request):
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(user=request.user).first()

    if not responsable:
        return redirect('login')

    # Traer las fichas de matrícula enviadas por este responsable, ordenadas de la más reciente a la más antigua
    solicitudes = FichaMatricula.objects.filter(
        responsable=responsable
    ).select_related('grado_seccion').order_by('-fecha_envio')

    # Alumnos que ya han sido aprobados/matriculados formalmente (si existe el modelo Alumno ligado)
    alumnos_matriculados = getattr(responsable, 'alumnos', None)
    alumnos = alumnos_matriculados.all() if alumnos_matriculados else []

    context = {
        'responsable': responsable,
        'solicitudes': solicitudes,
        'alumnos': alumnos,
    }
    return render(request, 'dashboard_responsable.html', context)

@responsable_required
@login_required
def ficha_matricula_view(request, ficha_id=None):
    # 1. Obtener el perfil del responsable autenticado
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(user=request.user).first()

    if not responsable:
        messages.error(request, "No posees un perfil de responsable registrado en el sistema.")
        return redirect('dashboard_responsable')

    ficha = None
    modo_lectura = False

    # 2. Si viene un ID, se activa el modo comprobante protegido
    if ficha_id:
        # Validación de seguridad: solo el dueño de la ficha puede consultarla
        ficha = get_object_or_404(FichaMatricula, id=ficha_id, responsable=responsable)
        modo_lectura = True

    # 3. Procesamiento del envío (POST)
    if request.method == 'POST':
        if modo_lectura:
            messages.warning(request, "Este comprobante es de solo lectura y no puede modificarse.")
            return redirect('comprobante_ficha', ficha_id=ficha_id)

        nie = request.POST.get('nie', '').strip()
        grado_codigo = request.POST.get('grado_solicitado', '').strip()
        seccion_codigo = request.POST.get('seccion_solicitada', '').strip()

        # Validación estricta del NIE salvadoreño (7 a 8 dígitos numéricos)
        if not re.match(r'^\d{7,8}$', nie):
            messages.error(request, "El NIE debe contener entre 7 y 8 dígitos numéricos.")
            return redirect('ficha_matricula')

        # Validar grado y sección seleccionados
        grado_seccion = GradoSeccion.objects.filter(
            grado=grado_codigo, 
            seccion=seccion_codigo, 
            activo=True
        ).first()

        if not grado_seccion:
            messages.error(request, "El grado y sección seleccionados no existen o no están disponibles.")
            return redirect('ficha_matricula')

        # Evitar solicitudes duplicadas pendientes para el mismo NIE
        if FichaMatricula.objects.filter(nie=nie, grado_seccion=grado_seccion, estado='PENDIENTE').exists():
            messages.warning(request, f"Ya existe una ficha de matrícula pendiente para el NIE {nie}.")
            return redirect('dashboard_responsable')

        # Guardar la postulación
        FichaMatricula.objects.create(
            grado_seccion=grado_seccion,
            responsable=responsable,
            nie=nie,
            nombres=request.POST.get('nombre', '').strip(),
            apellidos=request.POST.get('apellido', '').strip(),
            fecha_nacimiento=request.POST.get('fecha_nacimiento'),
            nacionalidad=request.POST.get('nacionalidad', 'Salvadoreña').strip(),
            genero=request.POST.get('genero'),
            
            depto_nacimiento=request.POST.get('depto_nacimiento'),
            municipio_nacimiento=request.POST.get('municipio_nacimiento'),
            distrito_nacimiento=request.POST.get('distrito_nacimiento'),
            
            tiene_discapacidad=(request.POST.get('tiene_discapacidad') == 'Si'),
            tipo_discapacidad=request.POST.get('tipo_discapacidad', '').strip(),
            
            zona_residencia=request.POST.get('zona_residencia', 'Urbana'),
            depto_residencia=request.POST.get('depto_residencia'),
            municipio_residencia=request.POST.get('municipio_residencia'),
            distrito_residencia=request.POST.get('distrito_residencia'),
            direccion_exacta=request.POST.get('direccion_exacta', '').strip(),
            
            tiene_problemas_salud=(request.POST.get('tiene_problemas_salud') == 'Si'),
            detalle_salud=request.POST.get('detalle_salud', '').strip(),
            vacunas_completas=(request.POST.get('vacunas_completas') == 'Si'),
            
            nombre_padre=request.POST.get('nombre_padre', '').strip(),
            dui_padre=request.POST.get('dui_padre', '').strip(),
            estado_padre=request.POST.get('estado_padre', 'Presente'),
            
            nombre_madre=request.POST.get('nombre_madre', '').strip(),
            dui_madre=request.POST.get('dui_madre', '').strip(),
            estado_madre=request.POST.get('estado_madre', 'Presente'),
            
            nombre_tutor_alt=request.POST.get('nombre_tutor_alt', '').strip(),
            dui_tutor_alt=request.POST.get('dui_tutor_alt', '').strip(),
            parentesco_tutor_alt=request.POST.get('parentesco_tutor_alt', '').strip(),
            
            parentesco_responsable=request.POST.get('parentesco_resp', 'Padre'),
            telefono_contacto=request.POST.get('telefono_resp', '').strip(),
            correo_notas=request.POST.get('email_resp', '').strip(),
            direccion_responsable=request.POST.get('direccion_resp', '').strip(),
            estado='PENDIENTE'
        )

        messages.success(request, "¡Ficha enviada con éxito! Ha quedado en estado pendiente de revisión.")
        return redirect('dashboard_responsable')

    # 4. Datos para el método GET
    grados_secciones = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')
    grados_unicos = {}
    for gs in grados_secciones:
        if gs.grado not in grados_unicos:
            grados_unicos[gs.grado] = gs.get_grado_display()

    context = {
        'responsable': responsable,
        'grados_secciones': grados_secciones,
        'grados_disponibles': grados_unicos.items(),
        'ficha': ficha,
        'modo_lectura': modo_lectura,
    }
    return render(request, 'ficha_matricula.html', context)