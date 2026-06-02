from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class Alumno(models.Model):
    NIE=models.CharField(max_length=10, primary_key=True, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nac=models.DateTimeField(blank=True, null=True,verbose_name="Fecha de Nacimiento")
    sexo = models.CharField(max_length=2)
    fecha_creacion=models.DateTimeField(auto_now_add=True)
    fecha_actualizacion=models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Maestro"
        verbose_name_plural = "Maestros"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.NIE})"


