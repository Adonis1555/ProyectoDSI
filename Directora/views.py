from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from Login.decorators import directora_required, maestro_required, responsable_required,roles_permitidos

@login_required
@directora_required
def directora_view(request):
    return render(request, "control_maestro.html")

@login_required
@directora_required
def registro_maestro_view(request):
    return render(request,"registro_maestro.html")
# Create your views here.
