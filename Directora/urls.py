from django.urls import path
from . import views

urlpatterns = [

        path('maestro/',views.directora_view,name="control_maestro"),
        path('registro_maestro/', views.registro_maestro_view,name="registro_maestro"),
        path('toggle_maestro_activo/<str:dui>/', views.toggle_maestro_activo, name="toggle_maestro_activo"),
        path('asignar_grado_maestro/', views.asignar_grado_maestro, name="asignar_grado_maestro"),
        path('get_maestro_grados/<str:dui>/', views.get_maestro_grados, name="get_maestro_grados"),
        path('desasignar_grado_maestro/', views.desasignar_grado_maestro, name="desasignar_grado_maestro"),
        path('toggle_grado_activo/<int:pk>/', views.toggle_grado_activo, name="toggle_grado_activo"),
        path('grado_seccion/',views.grado_seccion_control,name="grado_seccion_control"),
        path('registrar_grado/',views.registrar_grado_seccion,name="registrar_grado_seccion"),
        path('control_demerito_directora/',views.control_demeritos,name="control_demerito_directora"),
        path('exportar_excel_conducta/', views.exportar_excel_conducta, name="exportar_excel_conducta"),
        path('dashboard/', views.directora_dashboard, name="dashboard_directora"),
        path('materia/', views.directora_materia, name="directora_materia"),
        path('guardar-materia/', views.guardar_materia, name='guardar_materia'),
        path('asignar-materia-docente/', views.asignar_materia_docente, name='asignar_materia_docente'),
]