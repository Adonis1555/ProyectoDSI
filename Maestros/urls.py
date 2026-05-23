from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.maestro_view,name="dashboard_maestro")
        
]