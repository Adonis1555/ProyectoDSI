from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.maestro_view,name="dashboard_maestro"),
        path('control_alumnos/',views.control_alumnos,name="control_alumnos"),
        path('registro_alumnos/',views.registrar_alumno,name="registro_alumnos"),
        path('control_demeritos/',views.control_demeritos,name="control_demeritos"),
        
]