import re
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from Directora.models import GradoSeccion
from django.contrib import messages
from .models import Responsable, FichaMatricula,Matricula

SECUENCIA_GRADOS = {
    'PK5': 'PK6', 
    'PK6': '1G',   
    '2G': '3G',
    '3G': '4G',
    '4G': '5G',
    '5G': '6G',
    '6G': '7G',   
    '7G': '8G',
    '8G': '9G',
    '9G': None,   
}

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
    # 1. Obtener el perfil del responsable logueado
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(user=request.user).first()

    if not responsable:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
            return JsonResponse({'ok': False, 'error': 'No posees un perfil de responsable registrado.'}, status=403)
        messages.error(request, 'No tienes un perfil de responsable asignado.')
        return redirect('dashboard_responsable')

    # 2. Obtener estado del ciclo lectivo institucional
    periodo = ConfiguracionPeriodo.get_solo()

    ficha = None
    modo_lectura = False

    # 3. Modo comprobante (solo lectura)
    if ficha_id:
        ficha = get_object_or_404(FichaMatricula, id=ficha_id, responsable=responsable)
        modo_lectura = True

    # 4. Procesamiento del envío (POST)
    if request.method == 'POST':
        if modo_lectura:
            return JsonResponse({'ok': False, 'error': 'Este comprobante es de solo lectura y no se puede editar.'}, status=400)

        # Validación de Fase: Bloquear inscripción si está en Clases
        if periodo.fase_actual == 'CLASES':
            return JsonResponse({
                'ok': False,
                'error': f'El periodo de inscripciones para el año lectivo {periodo.anio_activo} se encuentra cerrado.'
            }, status=400)

        nie = request.POST.get('nie', '').strip()
        grado_codigo = request.POST.get('grado_solicitado', '').strip()
        seccion_codigo = request.POST.get('seccion_solicitada', '').strip()

        # Validación de formato NIE (7 u 8 dígitos numéricos salvadoreños)
        if not re.match(r'^\d{7,8}$', nie):
            return JsonResponse({'ok': False, 'error': 'El NIE debe contener entre 7 y 8 dígitos numéricos válidos.'}, status=400)

        # 5. Validación de progresión académica del estudiante
        alumno_existente = Alumno.objects.filter(NIE=nie).first()
        if alumno_existente:
            # Buscar su última matrícula registrada
            ultima_matricula = Matricula.objects.filter(
                alumno=alumno_existente
            ).select_related('grado_seccion').order_by('-anio_lectivo').first()

            if ultima_matricula:
                grado_anterior = ultima_matricula.grado_seccion.grado
                grado_siguiente = SECUENCIA_GRADOS.get(grado_anterior)

                # Si ya culminó 9° grado
                if grado_anterior == '9G' or grado_siguiente is None:
                    return JsonResponse({
                        'ok': False,
                        'error': f'El estudiante con NIE {nie} ya completó y aprobó el 9° Grado. Se encuentra graduado de este centro escolar.'
                    }, status=400)

                # Si intenta matricularse en un grado que no es el siguiente en orden
                if grado_codigo != grado_siguiente:
                    nombre_grado_esperado = dict(GradoSeccion.GRADOS_EL_SALVADOR).get(grado_siguiente, grado_siguiente)
                    return JsonResponse({
                        'ok': False,
                        'error': f'Inconsistencia académica: El alumno cursó {ultima_matricula.grado_seccion.get_grado_display()} en {ultima_matricula.anio_lectivo}. Le corresponde matricularse únicamente en {nombre_grado_esperado}.'
                    }, status=400)

        # 6. Validar que la sección exista y esté activa
        grado_seccion = GradoSeccion.objects.filter(
            grado=grado_codigo, 
            seccion=seccion_codigo, 
            activo=True
        ).first()

        if not grado_seccion:
            return JsonResponse({'ok': False, 'error': 'El grado y sección seleccionados no existen o no están habilitados.'}, status=400)

        # 7. Validar duplicidad de fichas para el mismo año activo
        ficha_existente = FichaMatricula.objects.filter(
            nie=nie, 
            anio_lectivo=periodo.anio_activo
        ).first()

        if ficha_existente:
            if ficha_existente.estado == 'PENDIENTE':
                return JsonResponse({'ok': False, 'error': f'Ya existe una ficha pendiente de revisión para el NIE {nie} en el ciclo {periodo.anio_activo}.'}, status=400)
            elif ficha_existente.estado == 'APROBADA':
                return JsonResponse({'ok': False, 'error': f'El estudiante con NIE {nie} ya fue formalmente matriculado para el ciclo {periodo.anio_activo}.'}, status=400)

        # 8. Creación de la Ficha ligada al año escolar activo
        FichaMatricula.objects.create(
            anio_lectivo=periodo.anio_activo,
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

        return JsonResponse({
            'ok': True, 
            'mensaje': f'La ficha para el ciclo {periodo.anio_activo} fue enviada exitosamente y quedó en espera de revisión docente.'
        })

    # 9. Petición GET: Cargar catálogo de secciones activas y grados únicos
    grados_secciones = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')
    grados_unicos = {}
    for gs in grados_secciones:
        if gs.grado not in grados_unicos:
            grados_unicos[gs.grado] = gs.get_grado_display()

    context = {
        'periodo': periodo,
        'responsable': responsable,
        'grados_secciones': grados_secciones,
        'grados_disponibles': grados_unicos.items(),
        'ficha': ficha,
        'modo_lectura': modo_lectura,
    }
    return render(request, 'ficha_matricula.html', context)