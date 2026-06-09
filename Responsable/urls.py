from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.responsable_view,name="dashboard_responsable")     
]