from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.directora_view,name="dashboard_directora")
        
]