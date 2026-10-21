from django.shortcuts import render

def responsable_view(request):
    return render(request, "dashboard_responsable.html")

def ficha_matricula_view(request):
    return render(request, "ficha_matricula.html")
# Create your views here.
