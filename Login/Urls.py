from django.urls import path
from . import views

urlpatterns = [

        path('',views.Login,name="login"),
        path('registro',views.registro_responsable,name="registro_responsable")
        
]