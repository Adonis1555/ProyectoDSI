import re
from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos
from datetime import date,datetime
from Login.models import Usuario  
from Directora.models import Maestro,GradoSeccion
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator,PageNotAnInteger
import secrets
import string
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import ProtectedError
from django.shortcuts import render, get_object_or_404

@login_required
@directora_required
def directora_view(request):
    from django.db.models import Q
    q = request.GET.get('q', '')
    if q:
        maestros_lista = Maestro.objects.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(dui__icontains=q) |
            Q(especialidad__icontains=q)
        ).order_by('apellido')
    else:
        maestros_lista = Maestro.objects.all().order_by('apellido')
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

    grados_disponibles = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')

    return render(request, "control_maestro.html", {
        'maestros': maestros_paginados,
        'grados_disponibles': grados_disponibles,
        'q': q
    })

@login_required
@directora_required
@require_POST
def toggle_maestro_activo(request, dui):
    try:
        maestro = get_object_or_404(Maestro, dui=dui)
        maestro.activo = not maestro.activo
        maestro.save()
        
        usuario = maestro.id_usuario
        usuario.activo = maestro.activo
        usuario.is_active = maestro.activo
        usuario.save()
        
        status_str = "activo" if maestro.activo else "inactivo"
        return JsonResponse({'ok': True, 'mensaje': f'El maestro ahora está {status_str}.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@login_required
@directora_required
@require_POST
def asignar_grado_maestro(request):
    try:
        import json
        data = json.loads(request.body)
        maestro_dui = data.get('maestro_dui')
        grado_id = data.get('grado_id')
        
        if not maestro_dui:
            return JsonResponse({'ok': False, 'error': 'DUI de maestro es obligatorio.'})
        
        maestro = get_object_or_404(Maestro, dui=maestro_dui)
        
        if not grado_id:
            return JsonResponse({'ok': False, 'error': 'Debe seleccionar un grado.'})
        
        grado = get_object_or_404(GradoSeccion, id=grado_id, activo=True)
        
        grados_actuales_count = maestro.grados_a_cargo.exclude(id=grado.id).count()
        if grados_actuales_count >= 2:
            return JsonResponse({
                'ok': False, 
                'error': f'El Prof. {maestro.apellido} ya tiene el límite máximo de 2 grados asignados.'
            })
        
        maestro_mismo_turno = maestro.grados_a_cargo.exclude(id=grado.id).filter(turno=grado.turno).exists()
        if maestro_mismo_turno:
            return JsonResponse({
                'ok': False,
                'error': f'El Prof. {maestro.apellido} ya tiene un grado asignado en el turno de la {grado.turno.lower()}.'
            })
        
        seccion_duplicada = maestro.grados_a_cargo.exclude(id=grado.id).filter(seccion=grado.seccion).exists()
        if seccion_duplicada:
            return JsonResponse({
                'ok': False,
                'error': f'El Prof. {maestro.apellido} ya es encargado de un grado en la Sección "{grado.seccion}".'
            })
        
        grado.maestro_encargado = maestro
        grado.save()
        
        return JsonResponse({'ok': True, 'mensaje': f'Grado asignado con éxito al Prof. {maestro.nombre} {maestro.apellido}.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

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
    
    parvularia = [gs for gs in grados_lista if gs.grado == 'PK']
    ciclo_1 = [gs for gs in grados_lista if gs.grado in ['1G', '2G', '3G']]
    ciclo_2 = [gs for gs in grados_lista if gs.grado in ['4G', '5G', '6G']]
    ciclo_3 = [gs for gs in grados_lista if gs.grado in ['7G', '8G', '9G']]
    
    context = {
        'parvularia': parvularia,
        'ciclo_1': ciclo_1,
        'ciclo_2': ciclo_2,
        'ciclo_3': ciclo_3,
    }
    return render(request, "grado_seccion_control.html", context)

@login_required
@directora_required
@require_POST
def toggle_grado_activo(request, pk):
    try:
        gs = get_object_or_404(GradoSeccion, id=pk)
        gs.activo = not gs.activo
        gs.save()
        status_str = "activo" if gs.activo else "inactivo"
        return JsonResponse({'ok': True, 'mensaje': f'El grado/sección ahora está {status_str}.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@login_required
@directora_required
@require_POST
def eliminar_grado_seccion(request, pk):
    try:
        grado_seccion = get_object_or_404(GradoSeccion, id=pk)
        
        conteo_alumnos = grado_seccion.alumnos.count() 
        
        if conteo_alumnos > 0:
            return JsonResponse({
                'ok': False, 
                'error': f'No se puede eliminar porque este grado tiene {conteo_alumnos} alumno(s) inscrito(s). Debes trasladarlos o eliminarlos primero.'
            })
        
        nombre_eliminado = f"{grado_seccion.get_grado_display()} - Sección {grado_seccion.seccion}"
        
        grado_seccion.delete()
        
        return JsonResponse({'ok': True, 'mensaje': f'El "{nombre_eliminado}" se eliminó con éxito.'})
        
    except ProtectedError:
        return JsonResponse({
            'ok': False, 
            'error': 'No se puede eliminar el registro debido a restricciones de integridad de datos asociados.'
        })
    except Exception as e:
        return JsonResponse({
            'ok': False, 
            'error': f'Error interno al intentar eliminar: {str(e)}'
        })

@login_required
@directora_required
def registrar_grado_seccion(request):
    if request.method == 'POST':
        grado_codigo = request.POST.get('grado')
        seccion_texto = request.POST.get('seccion')
        maestro_dui = request.POST.get('maestro_dui')
        cupos = request.POST.get('cupos')
        turno = request.POST.get('turno')  

        if not grado_codigo or not seccion_texto or not turno:
            return JsonResponse({'ok': False, 'error': 'El grado, la sección y el turno son campos obligatorios.'})

        seccion_limpia = seccion_texto.strip().upper()
        cupo_maximo = int(cupos) if cupos and cupos.isdigit() else 35

        if seccion_limpia == 'A':
            turno = 'Mañana'

        secciones_mismo_turno = GradoSeccion.objects.filter(grado=grado_codigo, turno=turno).count()
        if secciones_mismo_turno >= 2:
            return JsonResponse({
                'ok': False, 
                'error': f'Ya existen 2 secciones registradas en el turno de la {turno.lower()} para este grado.'
            })

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
                
                maestro_mismo_turno = instancia_maestro.grados_a_cargo.filter(turno=turno).exists()
                if maestro_mismo_turno:
                    return JsonResponse({
                        'ok': False,
                        'error': f'El Prof. {instancia_maestro.apellido} ya tiene un grado asignado en el turno de la {turno.lower()}.'
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
                maestro_encargado=instancia_maestro,
                turno=turno  
            )

            if instancia_maestro:
                msg = f"¡Grado creado exitosamente en turno {turno.lower()} y asignado al Prof. {instancia_maestro.nombre}!"
            else:
                msg = f"Grado y sección creados correctamente en turno {turno.lower()} sin encargado."

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
    hoy = date.today()
    mes_actual = int(request.GET.get('mes', hoy.month))
    anio_actual = int(request.GET.get('anio', hoy.year))
    
    from Maestros.models import Alumno, RegistroTarjeta
    
    secciones = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')
    
    matriz_grados = []
    
    totales_globales = {
        'mat_m': 0, 'mat_h': 0, 'mat_total': 0,
        'd_m': 0, 'd_h': 0, 'd_total_sexo': 0,
        'd_a': 0, 'd_b': 0, 'd_c': 0, 'd_d': 0, 'd_total_causal': 0,
        'r_m': 0, 'r_h': 0, 'r_total_sexo': 0,
        'r_a': 0, 'r_b': 0, 'r_c': 0, 'r_total_opcion': 0,
        'rc_m': 0, 'rc_h': 0, 'rc_total': 0
    }
    
    for seccion in secciones:
        alumnos = Alumno.objects.filter(grado_seccion=seccion, activo=True)
        mat_m = alumnos.filter(sexo='F').count()
        mat_h = alumnos.filter(sexo='M').count()
        mat_total = mat_m + mat_h
        
        tarjetas = RegistroTarjeta.objects.filter(
            alumno__grado_seccion=seccion,
            fecha__month=mes_actual,
            fecha__year=anio_actual
        )
        
        d_m = tarjetas.filter(tipo='D', alumno__sexo='F').count()
        d_h = tarjetas.filter(tipo='D', alumno__sexo='M').count()
        d_total_sexo = d_m + d_h
        
        d_a = tarjetas.filter(tipo='D', sub_letra='A').count()
        d_b = tarjetas.filter(tipo='D', sub_letra='B').count()
        d_c = tarjetas.filter(tipo='D', sub_letra='C').count()
        d_d = tarjetas.filter(tipo='D', sub_letra='D').count()
        d_total_causal = d_a + d_b + d_c + d_d
        
        r_m = tarjetas.filter(tipo='R', alumno__sexo='F').count()
        r_h = tarjetas.filter(tipo='R', alumno__sexo='M').count()
        r_total_sexo = r_m + r_h
        
        r_a = tarjetas.filter(tipo='R', sub_letra='A').count()
        r_b = tarjetas.filter(tipo='R', sub_letra='B').count()
        r_c = tarjetas.filter(tipo='R', sub_letra='C').count()
        r_total_opcion = r_a + r_b + r_c
        
        rc_m = tarjetas.filter(tipo='RC', alumno__sexo='F').count()
        rc_h = tarjetas.filter(tipo='RC', alumno__sexo='M').count()
        rc_total = rc_m + rc_h
        
        fila = {
            'seccion_obj': seccion,
            'mat_m': mat_m, 'mat_h': mat_h, 'mat_total': mat_total,
            'd_m': d_m, 'd_h': d_h, 'd_total_sexo': d_total_sexo,
            'd_a': d_a, 'd_b': d_b, 'd_c': d_c, 'd_d': d_d, 'd_total_causal': d_total_causal,
            'r_m': r_m, 'r_h': r_h, 'r_total_sexo': r_total_sexo,
            'r_a': r_a, 'r_b': r_b, 'r_c': r_c, 'r_total_opcion': r_total_opcion,
            'rc_m': rc_m, 'rc_h': rc_h, 'rc_total': rc_total
        }
        matriz_grados.append(fila)
        
        totales_globales['mat_m'] += mat_m
        totales_globales['mat_h'] += mat_h
        totales_globales['mat_total'] += mat_total
        
        totales_globales['d_m'] += d_m
        totales_globales['d_h'] += d_h
        totales_globales['d_total_sexo'] += d_total_sexo
        
        totales_globales['d_a'] += d_a
        totales_globales['d_b'] += d_b
        totales_globales['d_c'] += d_c
        totales_globales['d_d'] += d_d
        totales_globales['d_total_causal'] += d_total_causal
        
        totales_globales['r_m'] += r_m
        totales_globales['r_h'] += r_h
        totales_globales['r_total_sexo'] += r_total_sexo
        
        totales_globales['r_a'] += r_a
        totales_globales['r_b'] += r_b
        totales_globales['r_c'] += r_c
        totales_globales['r_total_opcion'] += r_total_opcion
        
        totales_globales['rc_m'] += rc_m
        totales_globales['rc_h'] += rc_h
        totales_globales['rc_total'] += rc_total

    context = {
        'matriz_grados': matriz_grados,
        'totales_globales': totales_globales,
        'mes_actual': mes_actual,
        'anio_actual': anio_actual,
    }
    return render(request, "control_demerito.html", context)

@login_required
@directora_required
def exportar_excel_conducta(request):
    import base64
    import os
    from django.http import HttpResponse
    from django.conf import settings
    from datetime import date
    from Maestros.models import Alumno, RegistroTarjeta

    hoy = date.today()
    mes_actual = int(request.GET.get('mes', hoy.month))
    anio_actual = int(request.GET.get('anio', hoy.year))

    meses_nombres = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    nombre_mes = meses_nombres.get(mes_actual, '')

    secciones = GradoSeccion.objects.filter(activo=True).order_by('grado', 'seccion')
    matriz_grados = []
    totales_globales = {
        'mat_m': 0, 'mat_h': 0, 'mat_total': 0,
        'd_m': 0, 'd_h': 0, 'd_total_sexo': 0,
        'd_a': 0, 'd_b': 0, 'd_c': 0, 'd_d': 0, 'd_total_causal': 0,
        'r_m': 0, 'r_h': 0, 'r_total_sexo': 0,
        'r_a': 0, 'r_b': 0, 'r_c': 0, 'r_total_opcion': 0,
        'rc_m': 0, 'rc_h': 0, 'rc_total': 0
    }

    for seccion in secciones:
        alumnos = Alumno.objects.filter(grado_seccion=seccion, activo=True)
        mat_m = alumnos.filter(sexo='F').count()
        mat_h = alumnos.filter(sexo='M').count()
        mat_total = mat_m + mat_h

        tarjetas = RegistroTarjeta.objects.filter(
            alumno__grado_seccion=seccion,
            fecha__month=mes_actual,
            fecha__year=anio_actual
        )

        d_m = tarjetas.filter(tipo='D', alumno__sexo='F').count()
        d_h = tarjetas.filter(tipo='D', alumno__sexo='M').count()
        d_total_sexo = d_m + d_h

        d_a = tarjetas.filter(tipo='D', sub_letra='A').count()
        d_b = tarjetas.filter(tipo='D', sub_letra='B').count()
        d_c = tarjetas.filter(tipo='D', sub_letra='C').count()
        d_d = tarjetas.filter(tipo='D', sub_letra='D').count()
        d_total_causal = d_a + d_b + d_c + d_d

        r_m = tarjetas.filter(tipo='R', alumno__sexo='F').count()
        r_h = tarjetas.filter(tipo='R', alumno__sexo='M').count()
        r_total_sexo = r_m + r_h

        r_a = tarjetas.filter(tipo='R', sub_letra='A').count()
        r_b = tarjetas.filter(tipo='R', sub_letra='B').count()
        r_c = tarjetas.filter(tipo='R', sub_letra='C').count()
        r_total_opcion = r_a + r_b + r_c

        rc_m = tarjetas.filter(tipo='RC', alumno__sexo='F').count()
        rc_h = tarjetas.filter(tipo='RC', alumno__sexo='M').count()
        rc_total = rc_m + rc_h

        fila = {
            'seccion_obj': seccion,
            'mat_m': mat_m, 'mat_h': mat_h, 'mat_total': mat_total,
            'd_m': d_m, 'd_h': d_h, 'd_total_sexo': d_total_sexo,
            'd_a': d_a, 'd_b': d_b, 'd_c': d_c, 'd_d': d_d, 'd_total_causal': d_total_causal,
            'r_m': r_m, 'r_h': r_h, 'r_total_sexo': r_total_sexo,
            'r_a': r_a, 'r_b': r_b, 'r_c': r_c, 'r_total_opcion': r_total_opcion,
            'rc_m': rc_m, 'rc_h': rc_h, 'rc_total': rc_total
        }
        matriz_grados.append(fila)

        totales_globales['mat_m'] += mat_m
        totales_globales['mat_h'] += mat_h
        totales_globales['mat_total'] += mat_total

        totales_globales['d_m'] += d_m
        totales_globales['d_h'] += d_h
        totales_globales['d_total_sexo'] += d_total_sexo

        totales_globales['d_a'] += d_a
        totales_globales['d_b'] += d_b
        totales_globales['d_c'] += d_c
        totales_globales['d_d'] += d_d
        totales_globales['d_total_causal'] += d_total_causal

        totales_globales['r_m'] += r_m
        totales_globales['r_h'] += r_h
        totales_globales['r_total_sexo'] += r_total_sexo

        totales_globales['r_a'] += r_a
        totales_globales['r_b'] += r_b
        totales_globales['r_c'] += r_c
        totales_globales['r_total_opcion'] += r_total_opcion

        totales_globales['rc_m'] += rc_m
        totales_globales['rc_h'] += rc_h
        totales_globales['rc_total'] += rc_total

    logo_path = os.path.join(settings.BASE_DIR, 'Directora', 'static', 'logo.jpg')
    logo_base64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

    html_content = f"""<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<!--[if gte mso 9]>
<xml>
 <x:ExcelWorkbook>
  <x:ExcelWorksheets>
   <x:ExcelWorksheet>
    <x:Name>Control de conducta</x:Name>
    <x:WorksheetOptions>
     <x:DisplayGridlines/>
    </x:WorksheetOptions>
   </x:ExcelWorksheet>
  </x:ExcelWorksheets>
 </x:ExcelWorkbook>
</xml>
<![endif]-->
<style>
    .table-header {{
        font-weight: bold;
        background-color: #f1f5f9;
        text-align: center;
        border: 0.5pt solid #94a3b8;
    }}
    .data-cell {{
        border: 0.5pt solid #94a3b8;
        text-align: center;
    }}
    .total-cell {{
        background-color: #e2e8f0;
        font-weight: bold;
        border: 0.5pt solid #94a3b8;
        text-align: center;
    }}
    .header-title {{
        font-size: 16pt;
        font-weight: bold;
        color: #1e293b;
    }}
    .header-label {{
        font-size: 10pt;
        color: #64748b;
        font-weight: bold;
    }}
    .header-value {{
        font-size: 10pt;
        color: #1e293b;
    }}
</style>
</head>
<body>
<table>
    <tr>
        <td colspan="3" rowspan="4" align="center" valign="middle">
"""
    if logo_base64:
        html_content += f'            <img src="data:image/jpeg;base64,{logo_base64}" width="80" height="80">'
    else:
        html_content += "            LOGO"
        
    html_content += f"""
        </td>
        <td colspan="22" align="center" class="header-title">CONSOLIDADO MENSUAL INSTITUCIONAL - CONTROL DE CONDUCTA</td>
    </tr>
    <tr>
        <td colspan="22" align="center" style="font-size: 11pt; font-weight: bold;">Centro Educativo Natalia López (Código: 11243)</td>
    </tr>
    <tr>
        <td colspan="22" align="center" style="font-size: 10pt;">Mes de Análisis: {nombre_mes} {anio_actual}</td>
    </tr>
    <tr>
        <td colspan="22"></td>
    </tr>
    <tr>
        <td colspan="25"></td>
    </tr>
    <tr>
        <td colspan="5" class="header-label">1. Nombre del Centro Educativo:</td>
        <td colspan="6" class="header-value">C.E Natalia López</td>
        <td colspan="3" class="header-label">2. Código del C.E:</td>
        <td colspan="3" class="header-value">11243</td>
        <td colspan="3" class="header-label">3. Departamento:</td>
        <td colspan="5" class="header-value">La Libertad</td>
    </tr>
    <tr>
        <td colspan="5" class="header-label">4. Municipio:</td>
        <td colspan="6" class="header-value">La Libertad Norte</td>
        <td colspan="3" class="header-label">5. Distrito:</td>
        <td colspan="3" class="header-value">San Matías</td>
        <td colspan="3" class="header-label">Rol Encargado:</td>
        <td colspan="5" class="header-value">Personal Directivo</td>
    </tr>
    <tr>
        <td colspan="25"></td>
    </tr>
    <tr>
        <th rowspan="2" class="table-header">No.</th>
        <th rowspan="2" class="table-header" style="width: 150px;">7. Grado</th>
        <th rowspan="2" class="table-header">8. Sección</th>
        <th rowspan="2" class="table-header" style="width: 100px;">9. Turno</th>
        <th colspan="3" class="table-header">10. Matrícula</th>
        <th colspan="3" class="table-header">11. Núm. Deméritos por Sexo</th>
        <th colspan="5" class="table-header">12. Núm. Deméritos por Causales</th>
        <th colspan="3" class="table-header">13. Núm. Redenciones por Sexo</th>
        <th colspan="4" class="table-header">14. Núm. Redenciones por Opción</th>
        <th colspan="3" class="table-header">15. Núm. Reconocimientos</th>
    </tr>
    <tr>
        <th class="table-header">M</th><th class="table-header">H</th><th class="table-header">Total</th>
        <th class="table-header">M</th><th class="table-header">H</th><th class="table-header">Total</th>
        <th class="table-header">A</th><th class="table-header">B</th><th class="table-header">C</th><th class="table-header">D</th><th class="table-header">Total</th>
        <th class="table-header">M</th><th class="table-header">H</th><th class="table-header">Total</th>
        <th class="table-header">A</th><th class="table-header">B</th><th class="table-header">C</th><th class="table-header">Total</th>
        <th class="table-header">M</th><th class="table-header">H</th><th class="table-header">Total</th>
    </tr>
"""

    for i, fila in enumerate(matriz_grados, 1):
        html_content += f"""    <tr>
        <td class="data-cell">{i}</td>
        <td class="data-cell" style="text-align: left;">{fila['seccion_obj'].get_grado_display()}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['seccion_obj'].seccion}</td>
        <td class="data-cell" style="text-transform: capitalize;">{fila['seccion_obj'].turno.lower()}</td>
        <td class="data-cell">{fila['mat_m']}</td>
        <td class="data-cell">{fila['mat_h']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['mat_total']}</td>
        <td class="data-cell">{fila['d_m']}</td>
        <td class="data-cell">{fila['d_h']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['d_total_sexo']}</td>
        <td class="data-cell">{fila['d_a']}</td>
        <td class="data-cell">{fila['d_b']}</td>
        <td class="data-cell">{fila['d_c']}</td>
        <td class="data-cell">{fila['d_d']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['d_total_causal']}</td>
        <td class="data-cell">{fila['r_m']}</td>
        <td class="data-cell">{fila['r_h']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['r_total_sexo']}</td>
        <td class="data-cell">{fila['r_a']}</td>
        <td class="data-cell">{fila['r_b']}</td>
        <td class="data-cell">{fila['r_c']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['r_total_opcion']}</td>
        <td class="data-cell">{fila['rc_m']}</td>
        <td class="data-cell">{fila['rc_h']}</td>
        <td class="data-cell" style="font-weight: bold;">{fila['rc_total']}</td>
    </tr>
"""

    html_content += f"""    <tr>
        <td colspan="4" class="total-cell" style="text-align: right;">16. TOTAL</td>
        <td class="total-cell">{totales_globales['mat_m']}</td>
        <td class="total-cell">{totales_globales['mat_h']}</td>
        <td class="total-cell">{totales_globales['mat_total']}</td>
        <td class="total-cell">{totales_globales['d_m']}</td>
        <td class="total-cell">{totales_globales['d_h']}</td>
        <td class="total-cell">{totales_globales['d_total_sexo']}</td>
        <td class="total-cell">{totales_globales['d_a']}</td>
        <td class="total-cell">{totales_globales['d_b']}</td>
        <td class="total-cell">{totales_globales['d_c']}</td>
        <td class="total-cell">{totales_globales['d_d']}</td>
        <td class="total-cell">{totales_globales['d_total_causal']}</td>
        <td class="total-cell">{totales_globales['r_m']}</td>
        <td class="total-cell">{totales_globales['r_h']}</td>
        <td class="total-cell">{totales_globales['r_total_sexo']}</td>
        <td class="total-cell">{totales_globales['r_a']}</td>
        <td class="total-cell">{totales_globales['r_b']}</td>
        <td class="total-cell">{totales_globales['r_c']}</td>
        <td class="total-cell">{totales_globales['r_total_opcion']}</td>
        <td class="total-cell">{totales_globales['rc_m']}</td>
        <td class="total-cell">{totales_globales['rc_h']}</td>
        <td class="total-cell">{totales_globales['rc_total']}</td>
    </tr>
    <tr>
        <td colspan="25"></td>
    </tr>
    <tr>
        <td colspan="25"></td>
    </tr>
    <tr>
        <td colspan="25" style="font-weight: bold;">Nombre, firma y sello del Director del C. E. __________________________________________________</td>
    </tr>
</table>
</body>
</html>"""

    response = HttpResponse(html_content, content_type='application/vnd.ms-excel')
    filename = f"consolidado_conducta_{mes_actual}_{anio_actual}.xls"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
@directora_required
def get_maestro_grados(request, dui):
    try:
        maestro = get_object_or_404(Maestro, dui=dui)
        grados = [{
            'id': g.id,
            'nombre': f"{g.get_grado_display()} - Sección {g.seccion} ({g.turno.lower()})"
        } for g in maestro.grados_a_cargo.all()]
        return JsonResponse({'ok': True, 'grados': grados})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@login_required
@directora_required
@require_POST
def desasignar_grado_maestro(request):
    try:
        import json
        data = json.loads(request.body)
        grado_id = data.get('grado_id')
        if not grado_id:
            return JsonResponse({'ok': False, 'error': 'ID de grado es obligatorio.'})
        grado = get_object_or_404(GradoSeccion, id=grado_id)
        grado.maestro_encargado = None
        grado.save()
        return JsonResponse({'ok': True, 'mensaje': 'Grado desasignado con éxito.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})

@login_required
@directora_required
def directora_dashboard(request):
    import json
    from django.db.models import Count, Q
    from Maestros.models import Alumno, RegistroTarjeta
    
    total_alumnos = Alumno.objects.filter(activo=True).count()
    total_maestros = Maestro.objects.filter(activo=True).count()
    total_secciones = GradoSeccion.objects.filter(activo=True).count()
    
    top_alumnos = Alumno.objects.filter(activo=True).annotate(
        demeritos_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='D'))
    ).filter(demeritos_count__gt=0).order_by('-demeritos_count')[:5]
    
    top_alumnos_reconocimientos = Alumno.objects.filter(activo=True).annotate(
        reconocimientos_count=Count('registros_tarjeta', filter=Q(registros_tarjeta__tipo='RC'))
    ).filter(reconocimientos_count__gt=0).order_by('-reconocimientos_count')[:5]
    
    hoy = date.today()
    anio = hoy.year
    
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    chart_demeritos = [0] * 12
    chart_redenciones = [0] * 12
    
    tarjetas_anio = RegistroTarjeta.objects.filter(fecha__year=anio)
    for t in tarjetas_anio:
        mes_idx = t.fecha.month - 1
        if 0 <= mes_idx < 12:
            if t.tipo == 'D':
                chart_demeritos[mes_idx] += 1
            elif t.tipo == 'R':
                chart_redenciones[mes_idx] += 1
                
    causales_count = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    demeritos_totales = RegistroTarjeta.objects.filter(tipo='D')
    for d in demeritos_totales:
        if d.sub_letra in causales_count:
            causales_count[d.sub_letra] += 1
            
    context = {
        'total_alumnos': total_alumnos,
        'total_maestros': total_maestros,
        'total_secciones': total_secciones,
        'top_alumnos': top_alumnos,
        'top_alumnos_reconocimientos': top_alumnos_reconocimientos,
        'meses_labels': json.dumps(meses_nombres),
        'chart_demeritos': json.dumps(chart_demeritos),
        'chart_redenciones': json.dumps(chart_redenciones),
        'causales_labels': json.dumps(['Leve (A)', 'Grave (B)', 'Muy Grave (C)', 'Extrema (D)']),
        'causales_data': json.dumps([causales_count['A'], causales_count['B'], causales_count['C'], causales_count['D']]),
        'anio': anio
    }
    return render(request, "dashboard_directora.html", context)