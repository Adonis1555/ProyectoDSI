from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages


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
    if user.es_maestro(): return redirect("dashboard_maestro")
    if user.es_responsable(): return redirect("dashboard_responsable")
    return redirect("login")

# Create your views here.
