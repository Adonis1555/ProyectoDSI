from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos

@login_required
@maestro_required
def maestro_view(request):
    return render(request, "dashboard_maestro.html")

@login_required
@roles_permitidos(['maestro','directora'])
def control_alumnos(request):
    return render(request,"control_alumnos.html")

@login_required
@maestro_required
def registrar_alumno(request):
    return render(request,"registro_alumnos.html")

@login_required
@maestro_required
def control_demeritos(request):
    return render(request,"demeritos_control.html")

# Create your views here.
