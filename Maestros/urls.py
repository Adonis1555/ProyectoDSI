from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.maestro_view,name="dashboard_maestro"),
        path('control_alumnos/',views.control_alumnos,name="control_alumnos"),
        path('registro_alumnos/',views.registrar_alumno,name="registro_alumnos"),
        path('control_demeritos/', views.control_demeritos, name="control_demeritos"),
        path('registro_demeritos/<str:nie>/', views.registro_demeritos_view, name="registro_demeritos_view"),
        path('registrar_demerito/<str:nie>/', views.registrar_demerito, name="registrar_demerito"),
        path('editar_alumno/<str:nie>/', views.editar_alumno, name="editar_alumno"),
        path('horario/', views.horario_maestro, name='horarios'),
        path('guardar-bloque-horario/', views.guardar_bloque_horario, name='guardar_bloque_horario'),
        path('eliminar-bloque-horario/', views.eliminar_bloque_horario, name='eliminar_bloque_horario'),
        path('enviar-horario-revision/', views.enviar_horario_revision, name='enviar_horario_revision'),

        
]