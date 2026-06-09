import re
from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from datetime import date,datetime
from Login.models import Usuario  
from Directora.models import Maestro,GradoSeccion
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
import secrets
import string
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError
from django.contrib import messages

@login_required
@directora_required
def directora_view(request):
    maestros_lista=Maestro.objects.filter(activo=True)
    hoy=date.today()

    paginator = Paginator(maestros_lista, 5)
    numero_pagina = request.GET.get('page', 1)
    maestros_paginados = paginator.get_page(numero_pagina)

    for m in maestros_paginados:
        if m.fecha_nac:
           f_nac = m.fecha_nac.date() if hasattr(m.fecha_nac, 'date') else m.fecha_nac
           m.edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
        else:
            m.edad = "N/A"

    return render(request, "control_maestro.html",{'maestros': maestros_paginados})

@login_required
@directora_required
def registro_maestro_view(request):
    if request.method == 'POST':
        email = request.POST.get('correo')
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        especialidad = request.POST.get('especialidad')
        dui = request.POST.get('dui')
        telefono = request.POST.get('telefono')
        fecha_nac = request.POST.get('fecha_nac')

        if not re.match(r'^\d{8}-\d{1}$', dui):
            return JsonResponse({'ok': False, 'error': 'El formato del DUI debe ser 00000000-0 y contener solo números.'})

        if not re.match(r'^[267]\d{3}-\d{4}$', telefono):
            return JsonResponse({'ok': False, 'error': 'El teléfono debe tener el formato de El Salvador (Ej: 7000-0000).'})

        if not fecha_nac:
            return JsonResponse({'ok': False, 'error': 'La fecha de nacimiento es obligatoria.'})
        
        try:
            fecha_nac_dt = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
            hoy = date.today()
            edad = hoy.year - fecha_nac_dt.year - ((hoy.month, hoy.day) < (fecha_nac_dt.month, fecha_nac_dt.day))
            
            if edad < 22:
                return JsonResponse({'ok': False, 'error': 'El maestro debe tener una edad válida (mínimo 22 años).'})
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Formato de fecha inválido.'})

        if Usuario.objects.filter(email=email).exists():
            return JsonResponse({'ok': False, 'error': 'Este correo electrónico ya ha sido registrado.'})

        if Maestro.objects.filter(dui=dui).exists():
            return JsonResponse({'ok': False, 'error': 'Este número de DUI ya está registrado.'})
        
        caracteres = string.ascii_letters + string.digits
        contrasenia_plana = ""
        
        while True:
            contrasenia_plana = ''.join(secrets.choice(caracteres) for _ in range(8))
            hash_temporal = make_password(contrasenia_plana)
            if not Usuario.objects.filter(password=hash_temporal).exists():
                break

        try:
            asunto = 'Credenciales de acceso al sistema escolar'
            mensaje = f'Hola {nombre} {apellido},\n\nSe ha creado tu cuenta de maestro con éxito.\n\nTus credenciales de acceso son:\nUsuario: {email}\nContraseña: {contrasenia_plana}\n'
            correo_emisor = settings.EMAIL_HOST_USER
            
            send_mail(
                asunto,
                mensaje,
                correo_emisor,
                [email],
                fail_silently=False,
            )
        except Exception:
            return JsonResponse({'ok': False, 'error': 'El correo electrónico ingresado no es válido o no existe. No se pudo completar el registro.'})
        try:
            with transaction.atomic():
                nuevo_usuario = Usuario.objects.create_user(
                    email=email,
                    password=contrasenia_plana,
                    nombre=nombre,
                    apellido=apellido,
                    rol='maestro'
                )

                Maestro.objects.create(
                    dui=dui,
                    nombre=nombre,
                    apellido=apellido,
                    especialidad=especialidad,
                    telefono=telefono,
                    fecha_nac=fecha_nac_dt,
                    id_usuario=nuevo_usuario
                )

            return JsonResponse({'ok': True})
        
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f"Error interno: {str(e)}"})

    return render(request, "registro_maestro.html")

@login_required
@directora_required
def grado_seccion_control(request):
    grados_lista = GradoSeccion.objects.all().order_by('grado', 'seccion')
    
    paginator = Paginator(grados_lista, 5) 
    
    page_number = request.GET.get('page')
    grados_secciones = paginator.get_page(page_number)
    
    context = {
        'grados_secciones': grados_secciones
    }
    return render(request, "grado_seccion_control.html", context)

@login_required
@directora_required
def registrar_grado_seccion(request):
    if request.method == 'POST':
        grado_codigo = request.POST.get('grado')
        seccion_texto = request.POST.get('seccion')
        maestro_dui = request.POST.get('maestro_dui')
        cupos = request.POST.get('cupos')

        if not grado_codigo or not seccion_texto:
            return JsonResponse({'ok': False, 'error': 'El grado y la sección son campos obligatorios.'})

        seccion_limpia = seccion_texto.strip().upper()
        cupo_maximo = int(cupos) if cupos and cupos.isdigit() else 35

        instancia_maestro = None

        if maestro_dui:
            try:
                instancia_maestro = Maestro.objects.get(dui=maestro_dui, activo=True)
                
                grados_actuales_count = instancia_maestro.grados_a_cargo.count()
                if grados_actuales_count >= 2:
                    return JsonResponse({
                        'ok': False, 
                        'error': f'El Prof. {instancia_maestro.apellido} ya tiene el límite máximo de 2 grados asignados.'
                    })
                
                seccion_duplicada = instancia_maestro.grados_a_cargo.filter(seccion=seccion_limpia).exists()
                if seccion_duplicada:
                    return JsonResponse({
                        'ok': False, 
                        'error': f'El Prof. {instancia_maestro.apellido} ya es encargado de un grado en la Sección "{seccion_limpia}".'
                    })
                    
            except Maestro.DoesNotExist:
                return JsonResponse({'ok': False, 'error': 'El maestro seleccionado no existe o está inactivo.'})

        try:
            nuevo_grado = GradoSeccion.objects.create(
                grado=grado_codigo,
                seccion=seccion_limpia,
                cupo_maximo=cupo_maximo,
                maestro_encargado=instancia_maestro
            )

            if instancia_maestro:
                msg = f"¡Grado creado con cupo de {cupo_maximo} y asignado al Prof. {instancia_maestro.nombre} con éxito!"
            else:
                msg = f"Grado y sección creados correctamente con un cupo de {cupo_maximo} sin encargado."

            return JsonResponse({'ok': True, 'mensaje': msg})

        except IntegrityError:
            return JsonResponse({'ok': False, 'error': 'La combinación de grado y sección ya existe en el sistema.'})

    grados_secciones = GradoSeccion.objects.all().order_by('grado', 'seccion')
    maestros_disponibles = Maestro.objects.filter(activo=True).order_by('apellido')

    context = {
        'grados_secciones': grados_secciones,
        'maestros_disponibles': maestros_disponibles,
        'grados_listado': GradoSeccion.GRADOS_EL_SALVADOR,
    }
    return render(request, "registrar_grado_seccion.html", context)

@login_required
@directora_required
def control_demeritos(request):
    return render(request,"control_demerito.html")