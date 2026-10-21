from django.urls import path
from . import views

urlpatterns = [

        path('dashboard/',views.responsable_view,name="dashboard_responsable"),  
        path('ficha_matricula/',views.ficha_matricula_view,name="ficha_matricula"),
        path('ficha-matricula/comprobante/<int:ficha_id>/', views.ficha_matricula_view, name='comprobante_ficha'),
]