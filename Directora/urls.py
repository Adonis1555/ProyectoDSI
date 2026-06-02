from django.urls import path
from . import views

urlpatterns = [

        path('maestro/',views.directora_view,name="control_maestro"),
        path('registro_maestro/', views.registro_maestro_view,name="registro_maestro"),
        
]