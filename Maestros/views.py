from datetime import date, datetime
import json
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count, Q
from Login.decorators import maestro_required, roles_permitidos
from Directora.models import AsignacionBloqueMaestro,GradoSeccion,Maestro,Materia,normalizar_turno
from Maestros.models import Alumno, RegistroTarjeta
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from .models import obtener_materias_docente,HorarioClase

@login_required
@maestro_required
def maestro_view(request):
    # 1. Identificar al maestro y sus secciones asignadas
    maestro = get_object_or_404(Maestro, id_usuario=request.user)
    secciones_maestro = GradoSeccion.objects.filter(maestro_encargado=maestro)
    
    if not secciones_maestro.exists():
        return render(request, "dashboard_maestro.html", {
            'maestro': maestro,
            'secciones_maestro': [],
            'matrix_mensual': [],
            'totales_anuales': {}
        })

    # 2. Determinar la sección activa (por parámetro GET o la primera disponible)
    seccion_id = request.GET.get('seccion_id')
    if seccion_id:
        seccion_actual = get_object_or_404(GradoSeccion, id=seccion_id, maestro_encargado=maestro)
    else:
        seccion_actual = secciones_maestro.first()

    # 3. Datos de Matrícula de la sección por sexo
    # Nota: Asegúrate de que los valores guardados en el campo 'sexo' coincidan con 'M' y 'F' (o 'H'/'M')
    alumnos_seccion = Alumno.objects.filter(grado_seccion=seccion_actual)
    total_m = alumnos_seccion.filter(sexo='M').count() # Masculino según las cabeceras de tu tabla
    total_f = alumnos_seccion.filter(sexo='F').count() # Femenino
    
    matricula_sexo = {
        'M': total_m,
        'F': total_f,
        'total': total_m + total_f
    }

    # 4. Construcción del Consolidado Mensual
    nombres_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    
    matriz_mensual = []
    
    # Inicializadores para la fila final de Totales Anuales
    totales_anuales = {
        'd_m': 0, 'd_h': 0, 'd_total_sexo': 0,
        'd_a': 0, 'd_b': 0, 'd_c': 0, 'd_d': 0, 'd_total_causal': 0,
        'r_m': 0, 'r_h': 0, 'r_total_sexo': 0,
        'r_a': 0, 'r_b': 0, 'r_c': 0, 'r_total_opcion': 0,
        'rc_m': 0, 'rc_h': 0, 'rc_total': 0,
    }

    # Filtrar registros que pertenecen únicamente a los alumnos de esta sección en el año en curso
    registros_año = RegistroTarjeta.objects.filter(
        alumno__grado_seccion=seccion_actual,
        fecha__year=2026 # Cambiar dinámicamente si se requiere
    )

    for mes_num in range(1, 13):
        # Filtrar registros específicos del mes iterado
        registros_mes = registros_año.filter(fecha__month=mes_num)
        
        # Agregaciones combinadas mediante consultas condicionales (Q)
        conteos = registros_mes.aggregate(
            # Deméritos por Sexo (M = Femenino en tu backend tradicional, H = Masculino en tu tabla)
            # Revisa si en tu base de datos usas 'M'/'F' o 'H'/'M' para Masculino/Femenino
            d_m=Count('id', filter=Q(tipo='D', alumno__sexo='F')), 
            d_h=Count('id', filter=Q(tipo='D', alumno__sexo='M')),
            
            # Deméritos por Escala / Sub-letra
            d_a=Count('id', filter=Q(tipo='D', sub_letra='A')),
            d_b=Count('id', filter=Q(tipo='D', sub_letra='B')),
            d_c=Count('id', filter=Q(tipo='D', sub_letra='C')),
            d_d=Count('id', filter=Q(tipo='D', sub_letra='D')),
            
            # Redenciones por Sexo
            r_m=Count('id', filter=Q(tipo='R', alumno__sexo='F')),
            r_h=Count('id', filter=Q(tipo='R', alumno__sexo='M')),
            
            # Redenciones por Opción
            r_a=Count('id', filter=Q(tipo='R', sub_letra='A')),
            r_b=Count('id', filter=Q(tipo='R', sub_letra='B')),
            r_c=Count('id', filter=Q(tipo='R', sub_letra='C')),
            
            # Reconocimientos por Sexo
            rc_m=Count('id', filter=Q(tipo='RC', alumno__sexo='F')),
            rc_h=Count('id', filter=Q(tipo='RC', alumno__sexo='M')),
        )

        # Totales calculados por fila
        d_total_sexo = conteos['d_m'] + conteos['d_h']
        d_total_causal = conteos['d_a'] + conteos['d_b'] + conteos['d_c'] + conteos['d_d']
        r_total_sexo = conteos['r_m'] + conteos['r_h']
        r_total_opcion = conteos['r_a'] + conteos['r_b'] + conteos['r_c']
        rc_total = conteos['rc_m'] + conteos['rc_h']

        fila = {
            'mes_nombre': nombres_meses[mes_num - 1],
            'd_m': conteos['d_m'], 'd_h': conteos['d_h'], 'd_total_sexo': d_total_sexo,
            'd_a': conteos['d_a'], 'd_b': conteos['d_b'], 'd_c': conteos['d_c'], 'd_d': conteos['d_d'], 'd_total_causal': d_total_causal,
            'r_m': conteos['r_m'], 'r_h': conteos['r_h'], 'r_total_sexo': r_total_sexo,
            'r_a': conteos['r_a'], 'r_b': conteos['r_b'], 'r_c': conteos['r_c'], 'r_total_opcion': r_total_opcion,
            'rc_m': conteos['rc_m'], 'rc_h': conteos['rc_h'], 'rc_total': rc_total,
        }
        matriz_mensual.append(fila)

        # Acumular para los totales globales (Fila 18)
        totales_anuales['d_m'] += conteos['d_m']
        totales_anuales['d_h'] += conteos['d_h']
        totales_anuales['d_total_sexo'] += d_total_sexo
        totales_anuales['d_a'] += conteos['d_a']
        totales_anuales['d_b'] += conteos['d_b']
        totales_anuales['d_c'] += conteos['d_c']
        totales_anuales['d_d'] += conteos['d_d']
        totales_anuales['d_total_causal'] += d_total_causal
        totales_anuales['r_m'] += conteos['r_m']
        totales_anuales['r_h'] += conteos['r_h']
        totales_anuales['r_total_sexo'] += r_total_sexo
        totales_anuales['r_a'] += conteos['r_a']
        totales_anuales['r_b'] += conteos['r_b']
        totales_anuales['r_c'] += conteos['r_c']
        totales_anuales['r_total_opcion'] += r_total_opcion
        totales_anuales['rc_m'] += conteos['rc_m']
        totales_anuales['rc_h'] += conteos['rc_h']
        totales_anuales['rc_total'] += rc_total

    context = {
        'maestro': maestro,
        'secciones_maestro': secciones_maestro,
        'seccion_actual': seccion_actual,
        'matricula_sexo': matricula_sexo,
        'matriz_mensual': matriz_mensual,
        'totales_anuales': totales_anuales
    }

    # Asegúrate de cambiar "dashboard_maestro.html" si tu archivo se llama diferente
    return render(request, "dashboard_maestro.html", context)

@login_required
@roles_permitidos(['maestro'])
def control_alumnos(request):
    hoy = date.today()
    secciones_con_alumnos = {}

    if request.user.rol == 'maestro':
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        secciones = GradoSeccion.objects.filter(maestro_encargado=maestro).order_by('grado', 'seccion')
    else:
        secciones = GradoSeccion.objects.all().order_by('grado', 'seccion')

    for seccion in secciones:
        alumnos = Alumno.objects.filter(grado_seccion=seccion, activo=True).order_by('apellido', 'nombre')
        for a in alumnos:
            if a.fecha_nac:
                f_nac = a.fecha_nac.date() if hasattr(a.fecha_nac, 'date') else a.fecha_nac
                a.edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
            else:
                a.edad = "N/A"
        secciones_con_alumnos[seccion] = alumnos

    return render(request, "control_alumnos.html", {'secciones_con_alumnos': secciones_con_alumnos})

@login_required
@maestro_required
def control_demeritos(request):
    hoy = date.today()
    secciones_con_alumnos = {}

    maestro = get_object_or_404(Maestro, id_usuario=request.user)
    secciones = GradoSeccion.objects.filter(maestro_encargado=maestro).order_by('grado', 'seccion')

    for seccion in secciones:
        alumnos = Alumno.objects.filter(grado_seccion=seccion, activo=True).annotate(
            m_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='R')),
            d_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='D')),
            rc_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='RC'))
        ).order_by('apellido', 'nombre')

        for a in alumnos:
            if a.fecha_nac:
                f_nac = a.fecha_nac.date() if hasattr(a.fecha_nac, 'date') else a.fecha_nac
                a.edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
            else:
                a.edad = "N/A"
            a.total_meritos = a.m_count
            a.total_demeritos = a.d_count
            a.total_reconocimientos = a.rc_count

        secciones_con_alumnos[seccion] = alumnos

    return render(request, "demeritos_control.html", {'secciones_con_alumnos': secciones_con_alumnos})

@login_required
@maestro_required
def registrar_alumno(request):
    maestro = get_object_or_404(Maestro, id_usuario=request.user)
    secciones_docente = GradoSeccion.objects.filter(maestro_encargado=maestro)

    if request.method == 'POST':
        nie = request.POST.get('nie')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        sexo = request.POST.get('sexo')
        grado_codigo = request.POST.get('grado')
        seccion_texto = request.POST.get('seccion')
        fecha_nac_str = request.POST.get('fecha_nac')
        
        if not nie or not nombre or not apellido or not grado_codigo or not seccion_texto or not fecha_nac_str:
            return JsonResponse({'ok': False, 'error': 'Todos los campos son obligatorios.'})

        if Alumno.objects.filter(NIE=nie).exists():
            return JsonResponse({'ok': False, 'error': 'Este número de NIE ya se encuentra registrado.'})
            
        if not re.match(r'^\d{8}$', nie):
            return JsonResponse({'ok': False, 'error': 'El NIE debe contener exactamente 8 dígitos.'})

        try:
            aula = GradoSeccion.objects.get(grado=grado_codigo, seccion=seccion_texto.strip().upper())
        except GradoSeccion.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'La combinación de Grado y Sección seleccionada no existe.'})

        if aula not in secciones_docente:
            return JsonResponse({'ok': False, 'error': 'No tiene autorización para registrar alumnos en este grado/sección.'})

        alumnos_matriculados = aula.alumnos.filter(activo=True).count()
        if alumnos_matriculados >= aula.cupo_maximo:
            return JsonResponse({
                'ok': False, 
                'error': f'Cupo agotado: {aula.get_grado_display()} Sección {aula.seccion} alcanzó su límite.'
            })

        hoy = datetime.now().date()
        fecha_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

        if 'G' in grado_codigo:
            try:
                grado_num = int(grado_codigo.replace('G', ''))
                if edad < 6 and grado_num >= 1:
                    return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: El alumno tiene {edad} años, es muy joven para ingresar a {grado_num}° Grado.'})
                if grado_num == 9 and edad < 12:
                    return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: Un alumno de {edad} años no puede ser matriculado en 9° Grado.'})
                if grado_num == 1 and edad > 10:
                     return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: El alumno tiene {edad} años, excede la edad sugerida para 1° Grado.'})
            except ValueError:
                pass

        try:
            with transaction.atomic():
                Alumno.objects.create(
                    nombre=nombre,
                    apellido=apellido,
                    fecha_nac=fecha_nac,
                    NIE=nie,
                    sexo=sexo,
                    grado_seccion=aula
                )
            return JsonResponse({'ok': True})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno: {str(e)}"})

    grados_mapeados = []
    dict_choices = {}
    for grupo, opciones in GradoSeccion.GRADOS_EL_SALVADOR:
        for cod, nom in opciones:
            dict_choices[cod] = nom

    for gs in secciones_docente:
        if gs.grado in dict_choices and (gs.grado, dict_choices[gs.grado]) not in grados_mapeados:
            grados_mapeados.append((gs.grado, dict_choices[gs.grado]))

    secciones_por_grado = {}
    for gs in secciones_docente:
        if gs.grado not in secciones_por_grado:
            secciones_por_grado[gs.grado] = []
        secciones_por_grado[gs.grado].append(gs.seccion)

    context = {
        'grados_existentes': grados_mapeados,
        'secciones_json': json.dumps(secciones_por_grado)
    }
    return render(request, "registro_alumnos.html", context)

@login_required
@maestro_required
def registro_demeritos_view(request, nie):
    alumno = get_object_or_404(Alumno.objects.select_related('grado_seccion'), NIE=nie)
    
    if request.user.rol == 'maestro':
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        secciones_asignadas = GradoSeccion.objects.filter(maestro_encargado=maestro)
        if alumno.grado_seccion not in secciones_asignadas:
            return redirect('control_alumnos')

    historial_completo = RegistroTarjeta.objects.filter(alumno=alumno).order_by('fecha').select_related('maestro_registra')

    totales = {
        'D_A': 0, 'D_B': 0, 'D_C': 0, 'D_D': 0,
        'R_A': 0, 'R_B': 0, 'R_C': 0, 'R_D': 0,
        'RC_A': 0, 'RC_B': 0, 'RC_C': 0, 'RC_D': 0,
    }

    for h in historial_completo:
        clave = f"{h.tipo}_{h.sub_letra}"
        if clave in totales:
            totales[clave] += 1

    totales['total_demeritos'] = totales['D_A'] + totales['D_B'] + totales['D_C'] + totales['D_D']

    paginator = Paginator(historial_completo, 5)
    numero_pagina = request.GET.get('page', 1)
    historial_paginado = paginator.get_page(numero_pagina)

    context = {
        'alumno': alumno,
        'historial': historial_paginado,  
        'totales': totales
    }
    return render(request, "registrar_demeritos.html", context)

@login_required
@maestro_required
def registrar_demerito(request, nie):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("DATA RECIBIDA:", data)
            tipo_registro = data.get('tipo_registro')
            escala = data.get('escala')
            fecha_str = data.get('fecha')
            print("FECHA STR:", fecha_str, type(fecha_str))

            if not tipo_registro or not escala:
                return JsonResponse({'ok': False, 'error': 'Todos los campos del reporte son obligatorios.'})
            

            if fecha_str and fecha_str.strip():
                try:
                    fecha_final = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except ValueError:
                    fecha_final = date.today() 
            else:
                fecha_final = date.today()

            alumno = get_object_or_404(Alumno, NIE=nie)
            
            maestro = get_object_or_404(Maestro, id_usuario=request.user)
            secciones_asignadas = GradoSeccion.objects.filter(maestro_encargado=maestro)
            if alumno.grado_seccion not in secciones_asignadas:
                return JsonResponse({'ok': False, 'error': 'No está autorizado para añadir reportes a este estudiante.'})
            
            RegistroTarjeta.objects.create(
                alumno=alumno,
                tipo=tipo_registro,
                sub_letra=escala,
                fecha=fecha_final,
                maestro_registra=request.user
            )
            
            return JsonResponse({'ok': True})

        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'El formato de los datos enviados no es válido.'})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno en el servidor: {str(e)}"})
            
    return JsonResponse({'ok': False, 'error': 'Método de petición no permitido.'})

@login_required
@roles_permitidos(['maestro'])
def editar_alumno(request, nie):
    alumno = get_object_or_404(Alumno, NIE=nie)
    
    if request.user.rol == 'maestro':
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        secciones_docente = GradoSeccion.objects.filter(maestro_encargado=maestro)
        if alumno.grado_seccion not in secciones_docente:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
                return JsonResponse({'ok': False, 'error': 'No tiene autorización para editar este alumno.'})
            return redirect('control_alumnos')
    else:
        secciones_docente = GradoSeccion.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        sexo = request.POST.get('sexo')
        grado_codigo = request.POST.get('grado')
        seccion_texto = request.POST.get('seccion')
        fecha_nac_str = request.POST.get('fecha_nac')
        
        if not nombre or not apellido or not grado_codigo or not seccion_texto or not fecha_nac_str:
            return JsonResponse({'ok': False, 'error': 'Todos los campos son obligatorios.'})

        try:
            aula = GradoSeccion.objects.get(grado=grado_codigo, seccion=seccion_texto.strip().upper())
        except GradoSeccion.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'La combinación de Grado y Sección seleccionada no existe.'})

        if request.user.rol == 'maestro' and aula not in secciones_docente:
            return JsonResponse({'ok': False, 'error': 'No tiene autorización para asignar este grado/sección.'})

        if alumno.grado_seccion != aula:
            alumnos_matriculados = aula.alumnos.filter(activo=True).count()
            if alumnos_matriculados >= aula.cupo_maximo:
                return JsonResponse({
                    'ok': False, 
                    'error': f'Cupo agotado: {aula.get_grado_display()} Sección {aula.seccion} alcanzó su límite.'
                })

        hoy = datetime.now().date()
        fecha_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

        if 'G' in grado_codigo:
            try:
                grado_num = int(grado_codigo.replace('G', ''))
                if edad < 6 and grado_num >= 1:
                    return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: El alumno tiene {edad} años, es muy joven para ingresar a {grado_num}° Grado.'})
                if grado_num == 9 and edad < 12:
                    return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: Un alumno de {edad} años no puede ser matriculado en 9° Grado.'})
                if grado_num == 1 and edad > 10:
                     return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: El alumno tiene {edad} años, excede la edad sugerida para 1° Grado.'})
            except ValueError:
                pass

        try:
            with transaction.atomic():
                alumno.nombre = nombre
                alumno.apellido = apellido
                alumno.sexo = sexo
                alumno.grado_seccion = aula
                alumno.fecha_nac = fecha_nac
                alumno.save()
            return JsonResponse({'ok': True})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno: {str(e)}"})

    grados_mapeados = []
    dict_choices = {}
    for grupo, opciones in GradoSeccion.GRADOS_EL_SALVADOR:
        for cod, nom in opciones:
            dict_choices[cod] = nom

    for gs in secciones_docente:
        if gs.grado in dict_choices and (gs.grado, dict_choices[gs.grado]) not in grados_mapeados:
            grados_mapeados.append((gs.grado, dict_choices[gs.grado]))

    secciones_por_grado = {}
    for gs in secciones_docente:
        if gs.grado not in secciones_por_grado:
            secciones_por_grado[gs.grado] = []
        secciones_por_grado[gs.grado].append(gs.seccion)

    context = {
        'alumno': alumno,
        'grados_existentes': grados_mapeados,
        'secciones_json': json.dumps(secciones_por_grado)
    }
    return render(request, "editar_alumno.html", context)


BLOQUES_HORARIO = [
    {'id': 1, 'hora': '07:00 - 07:45', 'es_receso': False},
    {'id': 2, 'hora': '07:45 - 08:30', 'es_receso': False},
    {'id': 0, 'hora': '08:30 - 09:00', 'es_receso': True, 'nombre': 'Primer Receso'},
    {'id': 3, 'hora': '09:00 - 09:45', 'es_receso': False},
    {'id': 4, 'hora': '09:45 - 10:30', 'es_receso': False},
    {'id': 0, 'hora': '10:30 - 10:45', 'es_receso': True, 'nombre': 'Segundo Receso'},
    {'id': 5, 'hora': '10:45 - 11:30', 'es_receso': False},
]

BLOQUES_HORARIO_TARDE = [
    {'id': 1, 'hora': '13:00 - 13:45', 'es_receso': False},
    {'id': 2, 'hora': '13:45 - 14:30', 'es_receso': False},
    {'id': 0, 'hora': '14:30 - 15:00', 'es_receso': True, 'nombre': 'Primer Receso'},
    {'id': 3, 'hora': '15:00 - 15:45', 'es_receso': False},
    {'id': 4, 'hora': '15:45 - 16:30', 'es_receso': False},
    {'id': 0, 'hora': '16:30 - 16:45', 'es_receso': True, 'nombre': 'Segundo Receso'},
    {'id': 5, 'hora': '16:45 - 17:30', 'es_receso': False},
]
DIAS_SEMANA = [
    {'id': 1, 'nombre': 'Lunes'},
    {'id': 2, 'nombre': 'Martes'},
    {'id': 3, 'nombre': 'Miércoles'},
    {'id': 4, 'nombre': 'Jueves'},
    {'id': 5, 'nombre': 'Viernes'},
]


@login_required
@maestro_required
def horario_maestro(request):
    maestro = get_object_or_404(Maestro, id_usuario=request.user)
    anio_actual = datetime.now().year
    turno_actual = 'Tarde' if request.GET.get('turno', '').lower() == 'tarde' else 'Mañana'
    grados_basica = ['PK', '1G', '2G', '3G', '4G', '5G', '6G']
    grados_tercer = ['7G', '8G', '9G']
    nivel_solicitado = request.GET.get('nivel', 'basica').lower()

    todas_las_materias = obtener_materias_docente(maestro, anio=anio_actual)
    todas_las_clases = HorarioClase.objects.filter(
        docente=maestro, anio_lectivo=anio_actual
    ).select_related('materia', 'grado_seccion')

    if nivel_solicitado not in {'basica', 'tercer'}:
        nivel_solicitado = 'basica'
    nivel_actual = nivel_solicitado
    grados_nivel = grados_tercer if nivel_actual == 'tercer' else grados_basica

    materias_disponibles = [
        opcion for opcion in todas_las_materias
        if normalizar_turno(opcion['grado_seccion'].turno) == turno_actual
        and opcion['grado_seccion'].grado in grados_nivel
    ]

    # Clases agendadas por este maestro
    clases = todas_las_clases.filter(
        turno=turno_actual, grado_seccion__grado__in=grados_nivel
    )
    bloques_asignados = set(AsignacionBloqueMaestro.objects.filter(
        maestro=maestro,
        anio_lectivo=anio_actual,
        turno=turno_actual,
        activo=True,
    ).values_list('dia', 'bloque'))
    bloques_utilizables = bloques_asignados.intersection({
        (dia['id'], bloque['id'])
        for dia in DIAS_SEMANA for bloque in BLOQUES_HORARIO
        if not bloque['es_receso']
    })
    tiene_carga = bool(materias_disponibles)
    tiene_clases = clases.exists()
    puede_programar = tiene_carga and bool(bloques_utilizables)

    # Mapa rápido: (dia, bloque) -> objeto HorarioClase
    mapa_horario = {(c.dia, c.bloque): c for c in clases}

    # Armar grilla semanal
    grilla = []
    bloques_horario = BLOQUES_HORARIO_TARDE if turno_actual == 'Tarde' else BLOQUES_HORARIO
    for b in bloques_horario:
        fila = {'info': b, 'celdas': []}
        if not b['es_receso']:
            for d in DIAS_SEMANA:
                clase_slot = mapa_horario.get((d['id'], b['id']))
                fila['celdas'].append({
                    'dia_id': d['id'],
                    'bloque_id': b['id'],
                    'clase': clase_slot,
                    'permitido': puede_programar and (d['id'], b['id']) in bloques_utilizables,
                })
        grilla.append(fila)

    # Calcular progreso semanal
    conteo_materias = {}
    for c in clases:
        clave = f"{c.materia.nombre} ({c.grado_seccion})"
        conteo_materias[clave] = conteo_materias.get(clave, 0) + 1

    progreso = []
    for m in materias_disponibles:
        nombre_clave = f"{m['materia'].nombre} ({m['grado_seccion']})"
        asignadas = conteo_materias.get(nombre_clave, 0)
        meta_sugerida = 4
        porcentaje = min(int((asignadas / meta_sugerida) * 100), 100)
        progreso.append({
            'nombre': nombre_clave,
            'asignadas': asignadas,
            'meta': meta_sugerida,
            'porcentaje': porcentaje
        })
    
    estados_encontrados = set(clases.values_list('estado', flat=True))
    estado_actual = next(iter(estados_encontrados)) if len(estados_encontrados) == 1 else (
        'MIXTO' if estados_encontrados else 'BORRADOR'
    )
    motivo_rechazo = next((
        clase.observaciones.strip() for clase in clases
        if clase.estado == 'RECHAZADO' and clase.observaciones and clase.observaciones.strip()
    ), '')

    combinaciones = {}
    for opcion in todas_las_materias:
        nivel = 'tercer' if opcion['grado_seccion'].es_tercer_ciclo else 'basica'
        turno = normalizar_turno(opcion['grado_seccion'].turno)
        combinaciones.setdefault((nivel, turno), set())
    for clase in todas_las_clases:
        nivel = 'tercer' if clase.grado_seccion.es_tercer_ciclo else 'basica'
        combinaciones.setdefault((nivel, normalizar_turno(clase.turno)), set()).add(clase.estado)
    estados_propuestas = []
    for (nivel, turno), estados in sorted(combinaciones.items()):
        estado = next(iter(estados)) if len(estados) == 1 else ('MIXTO' if estados else 'BORRADOR')
        estados_propuestas.append({
            'nivel': nivel,
            'nivel_nombre': 'Tercer ciclo' if nivel == 'tercer' else 'Niveles básicos',
            'turno': turno,
            'turno_query': turno.lower().replace('ñ', 'n'),
            'estado': estado,
            'seleccionado': nivel == nivel_actual and turno == turno_actual,
        })

    contexto = {
        'maestro': maestro,
        'dias': DIAS_SEMANA,
        'grilla': grilla,
        'materias_disponibles': materias_disponibles,
        'progreso': progreso,
        'anio_actual': anio_actual,
        'estado_actual': estado_actual,
        'motivo_rechazo': motivo_rechazo,
        'tiene_carga': tiene_carga,
        'tiene_clases': tiene_clases,
        'puede_programar': puede_programar,
        'estados_propuestas': estados_propuestas,
        'nivel_actual': nivel_actual,
        'titulo_nivel_actual': 'Tercer ciclo' if nivel_actual == 'tercer' else 'Niveles básicos',
        'turno_actual': turno_actual,
    }

    return render(request, 'horarios.html', contexto)


@login_required
@require_POST
def guardar_bloque_horario(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        dia = int(data.get('dia'))
        bloque = int(data.get('bloque'))
        grado_seccion_id = int(data.get('grado_seccion_id'))
        materia_id = int(data.get('materia_id'))
        anio = int(data.get('anio_lectivo', datetime.now().year))

        grado_seccion = GradoSeccion.objects.get(id=grado_seccion_id)
        materia = Materia.objects.get(id=materia_id)
        turno_clase = normalizar_turno(grado_seccion.turno)

        if not AsignacionBloqueMaestro.objects.filter(
            maestro=maestro, dia=dia, bloque=bloque, turno=turno_clase,
            anio_lectivo=anio, activo=True
        ).exists():
            return JsonResponse({
                'success': False,
                'error': 'Este bloque no está asignado por Dirección para el turno seleccionado.'
            }, status=400)

        combinacion_permitida = any(
            opcion['grado_seccion'].id == grado_seccion.id and opcion['materia'].id == materia.id
            for opcion in obtener_materias_docente(maestro, anio=anio)
        )
        if not combinacion_permitida:
            return JsonResponse({
                'success': False,
                'error': 'La materia y el grado seleccionados no forman parte de tu carga académica.'
            }, status=400)

        grados_nivel = ['7G', '8G', '9G'] if grado_seccion.es_tercer_ciclo else ['PK', '1G', '2G', '3G', '4G', '5G', '6G']
        if HorarioClase.objects.filter(
            docente=maestro,
            anio_lectivo=anio,
            grado_seccion__grado__in=grados_nivel,
            estado='PUBLICADO',
            turno=turno_clase,
        ).exists():
            return JsonResponse({
                'success': False,
                'error': 'El horario oficial de este nivel ya fue publicado y no puede modificarse.'
            }, status=400)

        # Validación 1: Verificar si el aula ya está ocupada por otro docente
        choque_aula = HorarioClase.objects.filter(
            grado_seccion=grado_seccion,
            dia=dia,
            bloque=bloque,
            anio_lectivo=anio
        ).exclude(docente=maestro).first()

        if choque_aula:
            return JsonResponse({
                'success': False,
                'error': f'Conflicto: {grado_seccion} ya tiene la clase de {choque_aula.materia.nombre} con {choque_aula.docente.nombre} en este bloque.'
            }, status=400)

        # Guardar o actualizar clase del docente
        clase, _ = HorarioClase.objects.update_or_create(
            docente=maestro,
            dia=dia,
            bloque=bloque,
            anio_lectivo=anio,
            turno=turno_clase,
            defaults={
                'grado_seccion': grado_seccion,
                'materia': materia,
            }
        )

        return JsonResponse({
            'success': True,
            'materia_nombre': materia.nombre,
            'materia_color': materia.color,
            'seccion_nombre': f"{grado_seccion.get_grado_display()} '{grado_seccion.seccion}'"
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def eliminar_bloque_horario(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        dia = int(data.get('dia'))
        bloque = int(data.get('bloque'))
        anio = int(data.get('anio_lectivo', datetime.now().year))

        clase = HorarioClase.objects.filter(
            docente=maestro,
            dia=dia,
            bloque=bloque,
            anio_lectivo=anio,
            turno='Tarde' if str(data.get('turno', '')).lower() == 'tarde' else 'Mañana',
        ).first()
        if clase and clase.estado == 'PUBLICADO':
            return JsonResponse({
                'success': False,
                'error': 'Una clase del horario oficial publicado no puede eliminarse.'
            }, status=400)
        if clase:
            clase.delete()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def enviar_horario_revision(request):
    try:
        maestro = get_object_or_404(Maestro, id_usuario=request.user)
        anio = datetime.now().year
        data = json.loads(request.body.decode('utf-8') or '{}')
        turno = 'Tarde' if str(data.get('turno', '')).lower() == 'tarde' else 'Mañana'
        nivel = str(data.get('nivel', '')).lower()
        if nivel == 'tercer':
            grados_nivel = ['7G', '8G', '9G']
            nombre_nivel = 'tercer ciclo'
        elif nivel == 'basica':
            grados_nivel = ['PK', '1G', '2G', '3G', '4G', '5G', '6G']
            nombre_nivel = 'niveles básicos'
        else:
            return JsonResponse({'success': False, 'error': 'El nivel educativo no es válido.'}, status=400)

        clases = HorarioClase.objects.filter(
            docente=maestro, anio_lectivo=anio, turno=turno,
            grado_seccion__grado__in=grados_nivel,
        )

        if not clases.exists():
            return JsonResponse({
                'success': False, 
                'error': 'No tienes ninguna clase programada en tu horario para enviar.'
            }, status=400)

        clases_editables = clases.filter(estado__in=['BORRADOR', 'RECHAZADO'])
        if not clases_editables.exists():
            return JsonResponse({
                'success': False,
                'error': 'No hay cambios en borrador o rechazados para enviar.'
            }, status=400)

        # Los horarios aprobados o publicados conservan su estado.
        clases_editables.update(estado='ENVIADO', observaciones='')

        return JsonResponse({
            'success': True,
            'mensaje': f'Tu horario de {nombre_nivel} para el turno {turno.lower()} fue enviado a Dirección.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
