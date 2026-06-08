from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from Directora.models import Maestro,GradoSeccion

class Alumno(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]
    NIE = models.CharField(max_length=10, primary_key=True, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nac = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento")
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES) 
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True) 
    turno = models.CharField(max_length=20, default="Mañana")
    activo = models.BooleanField(default=True)

    grado_seccion = models.ForeignKey(
        'Directora.GradoSeccion', 
        on_delete=models.PROTECT, 
        related_name='alumnos',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.NIE})"


class RegistroTarjeta(models.Model):
    TIPO_CASO_CHOICES = [
        ('D', 'Demérito'),
        ('R', 'Redención'),
        ('RC', 'Reconocimiento'),
    ]
    
    SUB_LETRA_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='registros_tarjeta')
    fecha = models.DateField(auto_now_add=True) 

    tipo = models.CharField(max_length=2, choices=TIPO_CASO_CHOICES)
    sub_letra = models.CharField(max_length=1, choices=SUB_LETRA_CHOICES) 

    maestro_registra = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='demeritos_creados',
        null=True, 
        blank=True
    )
    responsable_redencion = models.CharField(max_length=150, blank=True, null=True)
    
    class Meta:
        verbose_name = "Registro de Tarjeta"
        verbose_name_plural = "Registros de Tarjetas"
        ordering = ['fecha', 'id']

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.sub_letra}) - Alumno: {self.alumno.nombre} {self.alumno.apellido}"


