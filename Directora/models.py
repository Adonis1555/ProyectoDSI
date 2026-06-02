from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class GradoSeccion(models.Model):
    grado=models.CharField(max_length=50)
    seccion=models.CharField(max_length=2)

    class Meta:
        verbose_name="Grado y Sección"
        verbose_name_plural="Grados y Secciones"

        unique_together=('grado','seccion')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.grado}- Seccion {self.seccion}"

class Maestro(models.Model):
    dui=models.CharField(max_length=10, primary_key=True, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nac=models.DateTimeField(blank=True, null=True,verbose_name="Fecha de Nacimiento")
    especialidad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=9)
    activo = models.BooleanField(default=True)

    fecha_creacion=models.DateTimeField(auto_now_add=True)
    fecha_actualizacion=models.DateTimeField(auto_now_add=True)
    id_usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='maestro_perfil')

    grado_a_cargo = models.ForeignKey(
        GradoSeccion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='maestro_encargado',
        help_text="Grado y sección que el maestro tiene asignado como orientador."
    )

    class Meta:
        verbose_name = "Maestro"
        verbose_name_plural = "Maestros"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.dui})"



