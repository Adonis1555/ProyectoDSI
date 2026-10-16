from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Usuario
from django.db import transaction
from Responsable.models import Responsable
import re
import dns.resolver
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse


def Login(request):
    if request.method == 'POST':

        email = request.POST.get('Usuario')
        password = request.POST.get('Password')
        if not email or not password:
            messages.error(request, 'Por favor, rellene todos los campos.')
            return render(request, "login.html")

        user = authenticate(request, username=email, password= password) 
            
        if user is not None:
            if user.activo:
                login(request, user)
                return redirigir_por_rol(user)
            else:
                messages.error(request, 'Tu cuenta está inactiva.')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            
    return render(request, "login.html")

def redirigir_por_rol(user):
    if user.es_directora(): return redirect("dashboard_directora")
    if user.es_maestro(): return redirect("control_alumnos")
    if user.es_responsable(): return redirect("dashboard_responsable")
    return redirect("login")

def verificar_dominio_correo(email):
    try:
        validate_email(email)
    except ValidationError:
        return False, "El formato del correo electrónico no es válido."

    dominio = email.split('@')[-1]

    try:
        registros_mx = dns.resolver.resolve(dominio, 'MX', lifetime=4.0)
        if not registros_mx:
            return False, f"El dominio @{dominio} no posee servidores de correo configurados."
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return False, f"El dominio @{dominio} no existe o no puede recibir correos."
    except (dns.resolver.Timeout, Exception):
        pass

    return True, None


def registro_responsable(request):
    #if request.user.is_authenticated:
     #   return redirect('login')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        dui = request.POST.get('dui', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        # Validaciones de campos
        if not all([nombre, apellido, dui, telefono, email, password, password_confirm]):
            return JsonResponse({'status': 'error', 'message': 'Todos los campos son obligatorios.'}, status=400)

        if not re.match(r'^\d{8}-\d$', dui):
            return JsonResponse({'status': 'error', 'message': 'El DUI debe tener el formato 00000000-0.'}, status=400)

        if not re.match(r'^[267]\d{3}-\d{4}$', telefono):
            return JsonResponse({'status': 'error', 'message': 'El teléfono debe tener el formato 0000-0000.'}, status=400)

        if password != password_confirm:
            return JsonResponse({'status': 'error', 'message': 'Las contraseñas no coinciden.'}, status=400)

        if len(password) < 6:
            return JsonResponse({'status': 'error', 'message': 'La contraseña debe tener al menos 6 caracteres.'}, status=400)

        # Validación DNS MX
        correo_valido, motivo_error = verificar_dominio_correo(email)
        if not correo_valido:
            return JsonResponse({'status': 'error', 'message': motivo_error}, status=400)

        if Responsable.objects.filter(dui=dui).exists():
            return JsonResponse({'status': 'error', 'message': 'Ya existe un responsable registrado con este DUI.'}, status=400)

        usuario_existente = Usuario.objects.filter(email=email).first()
        if usuario_existente:
            if usuario_existente.check_password(password):
                if hasattr(usuario_existente, 'perfil_responsable') and usuario_existente.perfil_responsable is not None:
                    return JsonResponse({'status': 'error', 'message': 'Este correo ya cuenta con un perfil de responsable activo.'}, status=400)

                Responsable.objects.create(
                    dui=dui,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    id_usuario=usuario_existente
                )
                return JsonResponse({'status': 'success', 'message': '¡Cuenta institucional vinculada como responsable exitosamente!'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Ya existe una cuenta con este correo. Ingresa tu contraseña institucional válida.'}, status=400)

        # Creación atómica
        try:
            with transaction.atomic():
                usuario = Usuario.objects.create_user(
                    email=email,
                    password=password,
                    nombre=nombre,
                    apellido=apellido,
                    rol='responsable',
                    activo=True
                )

                Responsable.objects.create(
                    dui=dui,
                    nombre=nombre,
                    apellido=apellido,
                    telefono=telefono,
                    id_usuario=usuario
                )

            return JsonResponse({'status': 'success', 'message': '¡Registro exitoso! Ya puedes iniciar sesión con tu cuenta.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Error en el registro: {str(e)}'}, status=500)

    return render(request, 'registro_responsable.html')