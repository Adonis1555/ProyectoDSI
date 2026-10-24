from django.db import models

from django.core.exceptions import ValidationError
from Login.models import Usuario
from Directora.models import GradoSeccion


class Responsable(models.Model):
    PARENTESCO_CHOICES = [
        ('MADRE', 'Madre'),
        ('PADRE', 'Padre'),
        ('TUTOR', 'Tutor Legal'),
        ('OTRO', 'Otro Familiar'),
    ]

    dui = models.CharField(max_length=10, primary_key=True, verbose_name="DUI")
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=15)
    direccion = models.TextField(blank=True, null=True)
    parentesco = models.CharField(max_length=10, choices=PARENTESCO_CHOICES, default='MADRE')

    id_usuario = models.OneToOneField(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil_responsable',
        limit_choices_to={'rol': 'responsable'},
        verbose_name="Cuenta de Usuario"
    )

    class Meta:
        verbose_name = "Responsable"
        verbose_name_plural = "Responsables"

    def __str__(self):
        return f"{self.nombre} {self.apellido} (DUI: {self.dui})"

    def clean(self):
        super().clean()
        # Validación lógica estricta para evitar inconsistencias
        if self.id_usuario and not self.id_usuario.es_responsable():
            raise ValidationError({
                'id_usuario': "El usuario asociado debe tener asignado el rol de 'responsable'."
            })

    def save(self, *args, **kwargs):
        # Si se vincula un usuario existente, asegurarse de forzar el rol
        if self.id_usuario and self.id_usuario.rol != 'responsable':
            self.id_usuario.rol = 'responsable'
            self.id_usuario.save(update_fields=['rol'])
        self.full_clean()
        super().save(*args, **kwargs)

class FichaMatricula(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    # Relación con la sección y el responsable que la llena
    grado_seccion = models.ForeignKey(
        GradoSeccion,
        on_delete=models.PROTECT,
        related_name='fichas_matricula'
    )
    responsable = models.ForeignKey(
        Responsable,
        on_delete=models.PROTECT,
        related_name='fichas_enviadas'
    )

    # 1. Identificación y Datos del Estudiante
    nie = models.CharField(max_length=15)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    nacionalidad = models.CharField(max_length=50, default="Salvadoreña")
    genero = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Femenino')])

    # Lugar de Nacimiento
    depto_nacimiento = models.CharField(max_length=50, blank=True, null=True)
    municipio_nacimiento = models.CharField(max_length=50, blank=True, null=True)
    distrito_nacimiento = models.CharField(max_length=50, blank=True, null=True)

    # Discapacidad
    tiene_discapacidad = models.BooleanField(default=False)
    tipo_discapacidad = models.CharField(max_length=100, blank=True, null=True)

    # Residencia del Estudiante
    zona_residencia = models.CharField(max_length=10, choices=[('Urbana', 'Urbana'), ('Rural', 'Rural')], default='Urbana')
    depto_residencia = models.CharField(max_length=50, blank=True, null=True)
    municipio_residencia = models.CharField(max_length=50, blank=True, null=True)
    distrito_residencia = models.CharField(max_length=50, blank=True, null=True)
    direccion_exacta = models.TextField(blank=True, null=True)

    # 2. Salud
    tiene_problemas_salud = models.BooleanField(default=False)
    detalle_salud = models.TextField(blank=True, null=True)
    vacunas_completas = models.BooleanField(default=True)

    # Datos Progenitores
    nombre_padre = models.CharField(max_length=150, blank=True, null=True)
    dui_padre = models.CharField(max_length=10, blank=True, null=True)
    estado_padre = models.CharField(max_length=20, default='Presente')

    nombre_madre = models.CharField(max_length=150, blank=True, null=True)
    dui_madre = models.CharField(max_length=10, blank=True, null=True)
    estado_madre = models.CharField(max_length=20, default='Presente')

    # Tutor Alternativo
    nombre_tutor_alt = models.CharField(max_length=150, blank=True, null=True)
    dui_tutor_alt = models.CharField(max_length=10, blank=True, null=True)
    parentesco_tutor_alt = models.CharField(max_length=50, blank=True, null=True)

    # 3. Datos del Responsable al momento del llenado
    parentesco_responsable = models.CharField(max_length=50)
    telefono_contacto = models.CharField(max_length=10)
    correo_notas = models.EmailField(blank=True, null=True)
    direccion_responsable = models.TextField(blank=True, null=True)

    # Control y Estado
    fecha_envio = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Ficha de Matrícula"
        verbose_name_plural = "Fichas de Matrícula"
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"Ficha {self.nie} - {self.nombres} {self.apellidos} ({self.get_estado_display()})"

class Matricula(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('RETIRADO', 'Retirado'),
        ('PROMOVIDO', 'Promovido'),
        ('GRADUADO', 'Graduado'),
    ]

    alumno = models.ForeignKey('Maestros.Alumno', on_delete=models.CASCADE, related_name='matriculas')
    grado_seccion = models.ForeignKey('Directora.GradoSeccion', on_delete=models.CASCADE, related_name='matriculas_seccion')
    anio_lectivo = models.PositiveIntegerField(default=2026)
    fecha_matricula = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')

    class Meta:
        # Un alumno solo puede tener una matrícula por año escolar
        unique_together = ('alumno', 'anio_lectivo')
        verbose_name = "Matrícula Anual"