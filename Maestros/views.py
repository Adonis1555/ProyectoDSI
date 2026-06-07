from django.shortcuts import render
from  Maestros.models import Alumno 
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from django.http import JsonResponse 
from django.db import transaction
from datetime import date,datetime
from django.core.paginator import Paginator
import re

@login_required
@maestro_required
def maestro_view(request):
    return render(request, "dashboard_maestro.html")

@login_required
@roles_permitidos(['maestro','directora'])
def control_alumnos(request):
    alumno_lista=Alumno.objects.all().order_by('apellido','nombre')
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
        nie=request.POST.get('nie')
        nombre=request.POST.get('nombre')
        apellido=request.POST.get('apellido')
        sexo=request.POST.get('sexo')
        grado_str=request.POST.get('grado')
        seccion=request.POST.get('seccion')
        fecha_nac_str=request.POST.get('fecha_nac')
        
        if Alumno.objects.filter(NIE=nie).exists():
            return JsonResponse({'ok': False, 'error': 'Este número de NIE ya se encuentra registrado.'})
        if not re.match(r'^\d{8}$',nie):
            return JsonResponse({'ok': False, 'error': 'El NIE debe contener 8 digitos.'})

        hoy = datetime.now().date()
        fecha_nac = datetime.strptime(fecha_nac_str, '%Y-%m-%d').date()
        edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

        try:
            grado_num = int(grado_str)
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
                    grado=grado_str,
                    seccion=seccion,

                )

            return JsonResponse({'ok': True})
        
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno: {str(e)}"})

    return render(request,"registro_alumnos.html")

@login_required
@maestro_required
def control_demeritos(request):
    return render(request,"demeritos_control.html")

# Create your views here.
