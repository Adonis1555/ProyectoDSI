from django.db import models
from django.conf import settings
from datetime import datetime


class Maestro(models.Model):
    dui = models.CharField(max_length=10, primary_key=True, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nac = models.DateTimeField(blank=True, null=True, verbose_name="Fecha de Nacimiento")
    especialidad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=9)
    activo = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    id_usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='maestro_perfil'
    )

    class Meta:
        verbose_name = "Maestro"
        verbose_name_plural = "Maestros"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.dui})"


class GradoSeccion(models.Model):
    GRADOS_EL_SALVADOR = [
        ('Parvularia', (
            ('PK', 'Parvularia'),
        )),
        ('Básica Ciclo I', (
            ('1G', '1° Grado'),
            ('2G', '2° Grado'),
            ('3G', '3° Grado'),
        )),
        ('Básica Ciclo II', (
            ('4G', '4° Grado'),
            ('5G', '5° Grado'),
            ('6G', '6° Grado'),
        )),
        ('Básica Ciclo III', (
            ('7G', '7° Grado'),
            ('8G', '8° Grado'),
            ('9G', '9° Grado'),
        )),
    ]

    grado = models.CharField(
        max_length=20,
        choices=GRADOS_EL_SALVADOR,
        help_text="Seleccione el nivel académico oficial"
    )
    seccion = models.CharField(max_length=2)
    cupo_maximo = models.PositiveIntegerField(default=0, help_text="Cantidad máxima de estudiantes permitidos")
    turno = models.CharField(default="mañana", max_length=50)
    activo = models.BooleanField(default=True)

    maestro_encargado = models.ForeignKey(
        Maestro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grados_a_cargo'
    )

    class Meta:
        verbose_name = "Grado y Sección"
        verbose_name_plural = "Grados y Secciones"
        unique_together = ('grado', 'seccion')

    def __str__(self):
        return f"{self.get_grado_display()} - Sección {self.seccion}"

    @property
    def es_tercer_ciclo(self):
        return self.grado in ['7G', '8G', '9G']


class Materia(models.Model):
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, blank=True, null=True)
    color = models.CharField(max_length=7, default="#D6E4FF")

    def __str__(self):
        return self.nombre


class AsignacionMateria(models.Model):
    grado_seccion = models.ForeignKey(
        GradoSeccion,
        on_delete=models.CASCADE,
        related_name='materias_distribuidas',
        verbose_name="Grado y Sección"
    )
    materia = models.ForeignKey(
        Materia,
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Materia"
    )
    docente = models.ForeignKey(
        Maestro,
        on_delete=models.CASCADE,
        related_name='materias_impartidas',
        verbose_name="Docente Asignado"
    )
    anio_lectivo = models.PositiveIntegerField(
        default=datetime.now().year,
        verbose_name="Año Lectivo"
    )

    class Meta:
        verbose_name = "Asignación de Materia"
        verbose_name_plural = "Asignaciones de Materias"
        unique_together = ('grado_seccion', 'materia', 'anio_lectivo')

    def __str__(self):
        return f"{self.materia.nombre} - {self.grado_seccion} -> {self.docente.nombre} {self.docente.apellido}"