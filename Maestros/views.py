from django.shortcuts import render
from  Maestros.models import Alumno 
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from django.http import JsonResponse 
from django.db import transaction
from datetime import date,datetime
from django.core.paginator import Paginator
from Directora.models import GradoSeccion
import re
import json
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from .models import Alumno, RegistroTarjeta, Maestro
@login_required
@maestro_required
def maestro_view(request):
    return render(request, "dashboard_maestro.html")

@login_required
@roles_permitidos(['maestro','directora'])
def control_alumnos(request):
    alumno_lista = Alumno.objects.all().select_related('grado_seccion').order_by('apellido', 'nombre')
    hoy=date.today()

    paginator = Paginator(alumno_lista, 5)
    numero_pagina = request.GET.get('page', 1)
    alumno_paginados = paginator.get_page(numero_pagina)

    for m in alumno_paginados:
        if m.fecha_nac:
           f_nac = m.fecha_nac.date() if hasattr(m.fecha_nac, 'date') else m.fecha_nac
           m.edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
        else:
            m.edad = "N/A"

    return render(request, "control_alumnos.html",{'alumnos': alumno_paginados})

@login_required
@maestro_required
def registrar_alumno(request):
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
            return JsonResponse({'ok': False, 'error': 'La combinación de Grado y Sección seleccionada no existe en el sistema.'})

        alumnos_matriculados = aula.alumnos.filter(activo=True).count()
        if alumnos_matriculados >= aula.cupo_maximo:
            return JsonResponse({
                'ok': False, 
                'error': f'Cupo agotado: {aula.get_grado_display()} Sección {aula.seccion} alcanzó su límite de {aula.cupo_maximo} alumnos.'
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
                    return JsonResponse({'ok': False, 'error': f'Incoherencia de matrícula: Un alumno de {edad} años no puede ser matriculado en 9° Grado (Mínimo 12 años).'})
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

    grados_en_uso = GradoSeccion.objects.values_list('grado', flat=True).distinct()
    
    grados_mapeados = []
    dict_choices = {}
    for grupo, opciones in GradoSeccion.GRADOS_EL_SALVADOR:
        for cod, nom in opciones:
            dict_choices[cod] = nom

    for cod in dict_choices:
        if cod in grados_en_uso:
            grados_mapeados.append((cod, dict_choices[cod]))

    secciones_por_grado = {}
    for gs in GradoSeccion.objects.all():
        if gs.grado not in secciones_por_grado:
            secciones_por_grado[gs.grado] = []
        secciones_por_grado[gs.grado].append(gs.seccion)

    secciones_json_string = json.dumps(secciones_por_grado)

    context = {
        'grados_existentes': grados_mapeados,
        'secciones_json': secciones_json_string
    }
    return render(request, "registro_alumnos.html", context)

@login_required
@maestro_required
def control_demeritos(request):
    alumno_lista = Alumno.objects.filter(activo=True).select_related('grado_seccion').annotate(
        m_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='R')),
        d_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='D')),
        rc_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='RC'))
    ).order_by('apellido', 'nombre')
    
    hoy = date.today()

    paginator = Paginator(alumno_lista, 5)
    numero_pagina = request.GET.get('page', 1)
    alumno_paginados = paginator.get_page(numero_pagina)

    for m in alumno_paginados:
        if m.fecha_nac:
            f_nac = m.fecha_nac.date() if hasattr(m.fecha_nac, 'date') else m.fecha_nac
            m.edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
        else:
            m.edad = "N/A"
            
        m.total_meritos = m.m_count
        m.total_demeritos = m.d_count
        m.total_reconocimientos = m.rc_count

    return render(request, "demeritos_control.html", {'alumnos': alumno_paginados})

@login_required
@maestro_required
def registro_demeritos_view(request, nie):
    alumno = get_object_or_404(Alumno.objects.select_related('grado_seccion'), NIE=nie)
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
            tipo_registro = data.get('tipo_registro')
            escala = data.get('escala')
            fecha_str = data.get('fecha')

            if not tipo_registro or not escala:
                return JsonResponse({'ok': False, 'error': 'Todos los campos del reporte son obligatorios.'})

            alumno = get_object_or_404(Alumno, NIE=nie)
            
            RegistroTarjeta.objects.create(
                alumno=alumno,
                tipo=tipo_registro,
                sub_letra=escala,
                fecha=fecha_str if fecha_str else date.today(),
                maestro_registra=request.user
            )
            
            return JsonResponse({'ok': True})

        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'El formato de los datos enviados no es válido.'})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno en el servidor: {str(e)}"})
            
    return JsonResponse({'ok': False, 'error': 'Método de petición no permitido.'})