from django.contrib import admin
from django.urls import path,include
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('Login.Urls')),
    path('maestros/',include('Maestros.urls')),
    path('responsables/',include('Responsable.urls')),
    path('directora/',include('Directora.urls')),
    path('logout/',LogoutView.as_view(next_page='login'),name='logout'),
]
