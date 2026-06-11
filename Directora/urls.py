from django.urls import path
from . import views

urlpatterns = [

        path('maestro/',views.directora_view,name="control_maestro"),
        path('registro_maestro/', views.registro_maestro_view,name="registro_maestro"),
        path('grado_seccion/',views.grado_seccion_control,name="grado_seccion_control"),
        path('registrar_grado/',views.registrar_grado_seccion,name="registrar_grado_seccion"),
        path('control_demerito_directora/',views.control_demeritos,name="control_demerito_directora"),
        path('dashboard/', views.directora_dashboard, name="dashboard_directora"),
        path('eliminar_grado_seccion/<int:pk>/', views.eliminar_grado_seccion, name='eliminar_grado_seccion'),
]