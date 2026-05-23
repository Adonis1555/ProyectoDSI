from django.shortcuts import render

def responsable_view(request):
    return render(request, "dashboard_responsable.html")

# Create your views here.
