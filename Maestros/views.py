from datetime import date, datetime
import json
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count, Q
from Login.decorators import maestro_required, roles_permitidos
from Directora.models import GradoSeccion, Maestro
from Maestros.models import Alumno, RegistroTarjeta
from django.core.paginator import Paginator

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
@roles_permitidos(['maestro', 'directora'])
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
@roles_permitidos(['maestro', 'directora'])
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