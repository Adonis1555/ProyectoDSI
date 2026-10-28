import re
from datetime import datetime, date
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from Login.decorators import responsable_required
from Directora.models import ConfiguracionPeriodo, GradoSeccion
from Maestros.models import Alumno
from django.contrib import messages
from django.core.exceptions import ValidationError
from Directora.periodos import periodo_requerido
from .models import Responsable, FichaMatricula, Matricula, RevisionFicha

# Secuencia académica regular entre grados
SECUENCIA_GRADOS = {
    'PK5': 'PK6', 
    'PK6': '1G',   
    '1G': '2G',
    '2G': '3G',
    '3G': '4G',
    '4G': '5G',
    '5G': '6G',
    '6G': '7G',   
    '7G': '8G',
    '8G': '9G',
    '9G': None,   
}

# Edad teórica esperada por nivel educativo para el año lectivo
EDADES_TEORICAS = {
    'PK5': 4,
    'PK6': 5,
    '1G': 6,
    '2G': 7,
    '3G': 8,
    '4G': 9,
    '5G': 10,
    '6G': 11,
    '7G': 12,
    '8G': 13,
    '9G': 14,
}


@responsable_required
@login_required
def responsable_view(request):
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(id_usuario=request.user).first()

    if not responsable:
        return redirect('login')

    periodo = ConfiguracionPeriodo.get_solo()
    anio_activo = periodo.anio_activo
    es_fase_matricula = (periodo.fase_actual == 'MATRICULA')

    # Solicitudes de matrícula tramitadas por este responsable
    solicitudes = FichaMatricula.objects.filter(
        responsable=responsable
    ).select_related('grado_seccion').order_by('-fecha_envio')

    # Alumnos históricos aprobados bajo la cuenta de este responsable
    nies_aprobados = FichaMatricula.objects.filter(
        responsable=responsable,
        estado='APROBADA'
    ).values_list('nie', flat=True).distinct()

    alumnos_base = Alumno.objects.filter(
        NIE__in=nies_aprobados
    ).prefetch_related('matriculas', 'matriculas__grado_seccion').distinct()

    fichas_anio_activo = {
        f.nie: f for f in solicitudes.filter(anio_lectivo=anio_activo)
    }

    alumnos_decorados = []
    for al in alumnos_base:
        ultima_mat = al.matriculas.order_by('-anio_lectivo').first()
        ficha_actual = fichas_anio_activo.get(al.NIE)
        matriculado_actual = al.matriculas.filter(
            anio_lectivo=anio_activo, 
            estado='ACTIVO'
        ).first()

        # Solo se permite matricular si estamos en fase de MATRÍCULA y no tiene ficha o matrícula en este año
        puede_matricular = (
            es_fase_matricula and 
            not ficha_actual and 
            not matriculado_actual
        )

        alumnos_decorados.append({
            'alumno': al,
            'ultima_matricula': ultima_mat,
            'ficha_actual': ficha_actual,
            'matriculado_actual': matriculado_actual,
            'puede_matricular_siguiente': puede_matricular,
        })

    context = {
        'responsable': responsable,
        'solicitudes': solicitudes,
        'alumnos': alumnos_decorados,
        'periodo': periodo,
        'anio_activo': anio_activo,
        'matricula_abierta': es_fase_matricula,
    }
    return render(request, 'dashboard_responsable.html', context)


@responsable_required
@login_required
def comprobante_ficha_view(request, ficha_id):
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(id_usuario=request.user).first()

    if not responsable:
        return redirect('dashboard_responsable')

    ficha = get_object_or_404(FichaMatricula, id=ficha_id, responsable=responsable)
    periodo = ConfiguracionPeriodo.get_solo()

    if ficha.fecha_envio and ficha.anio_lectivo and ficha.fecha_envio.year != ficha.anio_lectivo:
        try:
            nueva_fecha = ficha.fecha_envio.replace(year=ficha.anio_lectivo)
        except ValueError:
            nueva_fecha = ficha.fecha_envio.replace(year=ficha.anio_lectivo, day=28)
        FichaMatricula.objects.filter(pk=ficha.pk).update(fecha_envio=nueva_fecha)
        ficha.refresh_from_db()

    context = {
        'periodo': periodo,
        'responsable': responsable,
        'ficha': ficha,
        'modo_lectura': True,
        'corregir': False,
        'matricula_abierta': periodo.fase_actual == 'MATRICULA',
    }
    return render(request, 'ficha_matricula.html', context)


@responsable_required
@login_required
@periodo_requerido('MATRICULA')
def ficha_matricula_view(request, ficha_id=None, corregir=False):
    responsable = getattr(request.user, 'perfil_responsable', None)
    if not responsable:
        responsable = Responsable.objects.filter(id_usuario=request.user).first()

    if not responsable:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
            return JsonResponse({'ok': False, 'error': 'No posees un perfil de responsable registrado.'}, status=403)
        messages.error(request, 'No tienes un perfil de responsable asignado.')
        return redirect('dashboard_responsable')

    periodo = ConfiguracionPeriodo.get_solo()
    anio_activo = periodo.anio_activo

    ficha = None
    modo_lectura = False
    alumno_existente = None
    grados_permitidos = []
    aviso_sin_secciones = False

    # 1. Modo Corrección / Lectura
    if ficha_id:
        ficha = get_object_or_404(FichaMatricula, id=ficha_id, responsable=responsable)
        from Directora.archivos import cierre_anual
        if not corregir and cierre_anual(ficha.anio_lectivo):
            return redirect('ficha_archivada', anio=ficha.anio_lectivo, ficha_id=ficha.id)
        if corregir and (ficha.estado != 'RECHAZADA' or ficha.anio_lectivo != anio_activo or periodo.fase_actual != 'MATRICULA'):
            return JsonResponse({'ok': False, 'error': 'Esta ficha no está habilitada para corrección.'}, status=403)
        modo_lectura = not corregir

        alumno_existente = Alumno.objects.filter(NIE=ficha.nie).first()
    else:
        # 2. Precarga de alumno existente vía parámetro ?nie=
        nie_param = request.GET.get('nie', '').strip()
        if nie_param:
            alumno_existente = Alumno.objects.filter(NIE=nie_param).first()
            if alumno_existente:
                ficha_previa = FichaMatricula.objects.filter(nie=nie_param, anio_lectivo=anio_activo).first()
                if ficha_previa:
                    return redirect('comprobante_ficha', ficha_id=ficha_previa.id)

    # 3. Determinar grados permitidos (Actual por reprobación vs. Siguiente por promoción)
    if alumno_existente:
        ultima_mat = alumno_existente.matriculas.order_by('-anio_lectivo').first()
        if ultima_mat:
            g_actual = ultima_mat.grado_seccion.grado
            g_siguiente = SECUENCIA_GRADOS.get(g_actual)
            
            grados_permitidos = [g_actual]
            if g_siguiente:
                grados_permitidos.append(g_siguiente)

    # 4. Obtener catálogo de secciones activas y filtrar grados válidos
    grados_secciones = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')
    
    if grados_permitidos:
        grados_secciones = grados_secciones.filter(grado__in=grados_permitidos)
        if not grados_secciones.exists():
            aviso_sin_secciones = True

    grados_unicos = {}
    for gs in grados_secciones:
        if gs.grado not in grados_unicos:
            grados_unicos[gs.grado] = gs.get_grado_display()

    if not alumno_existente and not grados_secciones.exists():
        aviso_sin_secciones = True

    # 5. Procesamiento del Formulario (POST)
    if request.method == 'POST':
        if modo_lectura:
            return JsonResponse({'ok': False, 'error': 'Este comprobante es de solo lectura y no se puede editar.'}, status=400)

        if periodo.fase_actual != 'MATRICULA':
            return JsonResponse({
                'ok': False,
                'error': f'El periodo de matrícula para el año escolar {anio_activo} se encuentra cerrado.'
            }, status=400)

        nie = request.POST.get('nie', '').strip()
        grado_codigo = request.POST.get('grado_solicitado', '').strip()
        seccion_codigo = request.POST.get('seccion_solicitada', '').strip()
        es_nuevo_ingreso = request.POST.get('es_nuevo_ingreso') in ['on', 'true', 'True', '1']

        if not re.match(r'^\d{7,8}$', nie):
            return JsonResponse({'ok': False, 'error': 'El NIE debe contener entre 7 y 8 dígitos numéricos válidos.'}, status=400)

        # Si el alumno ya existe en el centro escolar
        alumno_db = Alumno.objects.filter(NIE=nie).first()
        if alumno_db:
            nombres = alumno_db.nombre
            apellidos = alumno_db.apellido
            fecha_nacimiento = alumno_db.fecha_nacimiento
            genero = alumno_db.sexo
        else:
            nombres = request.POST.get('nombre', '').strip()
            apellidos = request.POST.get('apellido', '').strip()
            genero = request.POST.get('genero')
            fecha_nac_str = request.POST.get('fecha_nacimiento', '').strip()
            
            if not fecha_nac_str:
                return JsonResponse({'ok': False, 'error': 'Debes ingresar una fecha de nacimiento válida.'}, status=400)
            try:
                fecha_nacimiento = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'ok': False, 'error': 'Formato de fecha de nacimiento incorrecto.'}, status=400)

        fecha_tope_ciclo = date(anio_activo, 12, 31)
        if fecha_nacimiento > fecha_tope_ciclo:
            return JsonResponse({'ok': False, 'error': f'La fecha de nacimiento no puede ser posterior al ciclo {anio_activo}.'}, status=400)

        edad_calculada = anio_activo - fecha_nacimiento.year
        if edad_calculada < 4:
            return JsonResponse({'ok': False, 'error': f'El alumno tiene {edad_calculada} años; la edad mínima es 4 años cumplidos para el ciclo {anio_activo}.'}, status=400)

        edad_teorica = EDADES_TEORICAS.get(grado_codigo)
        if edad_teorica is not None:
            if grado_codigo == 'PK5':
                if edad_calculada != 4:
                    return JsonResponse({'ok': False, 'error': f'Para Kínder 5 el alumno debe tener exactamente 4 años cumplidos en el año {anio_activo}.'}, status=400)
            else:
                if not ((edad_teorica - 1) <= edad_calculada <= (edad_teorica + 1)):
                    nombre_g = dict(GradoSeccion.GRADOS_EL_SALVADOR).get(grado_codigo, grado_codigo)
                    return JsonResponse({'ok': False, 'error': f'Inconsistencia de edad para {nombre_g} (edad calculada: {edad_calculada} años).'}, status=400)

        # Validación de Grados Permitidos para alumno existente (Reprobado vs Promovido)
        if alumno_db and not es_nuevo_ingreso:
            ultima_m = alumno_db.matriculas.order_by('-anio_lectivo').first()
            if ultima_m:
                g_cursado = ultima_m.grado_seccion.grado
                g_promovido = SECUENCIA_GRADOS.get(g_cursado)
                opciones_validas = [g_cursado]
                if g_promovido:
                    opciones_validas.append(g_promovido)

                if grado_codigo not in opciones_validas:
                    nombre_cursado = ultima_m.grado_seccion.get_grado_display()
                    nombre_promovido = dict(GradoSeccion.GRADOS_EL_SALVADOR).get(g_promovido, 'Ninguno')
                    return JsonResponse({
                        'ok': False,
                        'error': f'Grado inválido: Para este alumno las únicas opciones permitidas son repetir {nombre_cursado} o cursar el siguiente nivel ({nombre_promovido}).'
                    }, status=400)

        # Validar existencia de la sección activa
        grado_seccion = GradoSeccion.objects.filter(
            grado=grado_codigo, 
            seccion=seccion_codigo, 
            activo=True
        ).first()

        if not grado_seccion:
            return JsonResponse({
                'ok': False, 
                'error': f'No hay secciones activas disponibles en Dirección para el grado seleccionado en el ciclo {anio_activo}.'
            }, status=400)

        # Validar duplicidad
        otras_fichas = FichaMatricula.objects.filter(nie=nie, anio_lectivo=anio_activo)
        if corregir:
            otras_fichas = otras_fichas.exclude(pk=ficha.pk)
        
        if otras_fichas.exists():
            return JsonResponse({'ok': False, 'error': f'Ya existe una ficha registrada para el NIE {nie} en el ciclo escolar {anio_activo}.'}, status=400)

        if Matricula.objects.filter(alumno_id=nie, anio_lectivo=anio_activo).exists():
            return JsonResponse({'ok': False, 'error': 'El estudiante ya se encuentra matriculado en este ciclo escolar.'}, status=400)

        # Sincronización de fecha con el año lectivo
        ahora = timezone.now()
        try:
            fecha_envio_ciclo = ahora.replace(year=anio_activo)
        except ValueError:
            fecha_envio_ciclo = ahora.replace(year=anio_activo, day=28)

        # Captura de datos del Responsable Titular (Editables para este ciclo)
        nombre_resp = request.POST.get('nombre_resp', '').strip() or responsable.nombre
        apellido_resp = request.POST.get('apellido_resp', '').strip() or responsable.apellido
        dui_resp = request.POST.get('dui_resp', '').strip() or responsable.dui

        datos_ficha = dict(
            anio_lectivo=anio_activo,
            fecha_envio=fecha_envio_ciclo,
            grado_seccion=grado_seccion,
            responsable=responsable,
            nie=nie,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=fecha_nacimiento,
            nacionalidad=request.POST.get('nacionalidad', 'Salvadoreña').strip(),
            genero=genero,
            
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

        if hasattr(FichaMatricula, 'nombre_responsable'):
            datos_ficha['nombre_responsable'] = nombre_resp
        if hasattr(FichaMatricula, 'apellido_responsable'):
            datos_ficha['apellido_responsable'] = apellido_resp
        if hasattr(FichaMatricula, 'dui_responsable'):
            datos_ficha['dui_responsable'] = dui_resp

        if hasattr(FichaMatricula, 'es_nuevo_ingreso'):
            datos_ficha['es_nuevo_ingreso'] = es_nuevo_ingreso

        nueva_ficha = FichaMatricula(**datos_ficha)
        try:
            nueva_ficha.full_clean()
        except ValidationError as error:
            return JsonResponse({'ok': False, 'error': '; '.join(error.messages)}, status=400)

        if corregir:
            RevisionFicha.registrar(ficha, request.user, 'REENVIAR', ficha.observaciones or '')
            for campo, valor in datos_ficha.items():
                setattr(ficha, campo, valor)
            ficha.observaciones = ''
            ficha.save()
            FichaMatricula.objects.filter(pk=ficha.pk).update(fecha_envio=fecha_envio_ciclo)
        else:
            nueva_ficha.save()
            FichaMatricula.objects.filter(pk=nueva_ficha.pk).update(fecha_envio=fecha_envio_ciclo)

        return JsonResponse({
            'ok': True, 
            'mensaje': f'La ficha para el ciclo {anio_activo} fue enviada exitosamente y quedó en espera de revisión docente.'
        })

    # Render GET
    context = {
        'periodo': periodo,
        'responsable': responsable,
        'grados_secciones': grados_secciones,
        'grados_disponibles': grados_unicos.items(),
        'ficha': ficha,
        'alumno_existente': alumno_existente,
        'aviso_sin_secciones': aviso_sin_secciones,
        'modo_lectura': modo_lectura,
        'corregir': corregir,
        'matricula_abierta': periodo.fase_actual == 'MATRICULA',
    }
    return render(request, 'ficha_matricula.html', context)