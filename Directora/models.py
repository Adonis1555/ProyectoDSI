from django.db import models
from django.conf import settings
from datetime import datetime
import unicodedata


def normalizar_nombre_academico(valor):
    """Normaliza nombres para comparar materias y especialidades de forma segura."""
    texto = unicodedata.normalize('NFKD', valor or '')
    return ''.join(caracter for caracter in texto if not unicodedata.combining(caracter)).casefold().strip()


def especialidad_coincide_con_materia(maestro, materia):
    return normalizar_nombre_academico(maestro.especialidad) == normalizar_nombre_academico(materia.nombre)


def normalizar_turno(valor):
    return 'Tarde' if normalizar_nombre_academico(valor) == 'tarde' else 'Mañana'


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
    NIVELES_CHOICES = [
        ('PARVULARIA', 'Solo Parvularia'),
        ('BASICA', 'Solo Básica (1° a 6°)'),
        ('TERCER', 'Solo Tercer Ciclo (7° a 9°)'),
        ('BASICA_Y_TERCER', 'Básica y Tercer Ciclo'),
    ]
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=20, blank=True, null=True)
    color = models.CharField(max_length=7, default="#D6E4FF")
    bloques_semanales = models.PositiveSmallIntegerField(default=5)
    nivel_aplicable = models.CharField(
        max_length=20,
        choices=NIVELES_CHOICES,
        default='BASICA_Y_TERCER'
    )

    def __str__(self):
        return f"{self.nombre} ({self.get_nivel_aplicable_display()})"


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


class AsignacionBloqueMaestro(models.Model):
    TURNOS = [('Mañana', 'Mañana'), ('Tarde', 'Tarde')]
    DIAS_SEMANA = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
    ]
    BLOQUES = [
        (1, '07:00 - 07:45'),
        (2, '07:45 - 08:30'),
        (3, '09:00 - 09:45'),
        (4, '09:45 - 10:30'),
        (5, '10:30 - 11:15'),
    ]

    maestro = models.ForeignKey(
        Maestro,
        on_delete=models.CASCADE,
        related_name='bloques_asignados',
        verbose_name='Maestro'
    )
    dia = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    bloque = models.PositiveSmallIntegerField(choices=BLOQUES)
    turno = models.CharField(max_length=10, choices=TURNOS, default='Mañana')
    anio_lectivo = models.PositiveIntegerField(
        default=datetime.now().year,
        verbose_name='Año Lectivo'
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asignación de bloque a maestro'
        verbose_name_plural = 'Asignaciones de bloques a maestros'
        constraints = [
            models.UniqueConstraint(
                fields=['maestro', 'dia', 'bloque', 'turno', 'anio_lectivo'],
                name='bloque_unico_maestro_turno_anio'
            )
        ]
        ordering = ['maestro', 'turno', 'dia', 'bloque']

    def __str__(self):
        return f"{self.maestro} - {self.get_dia_display()} {self.get_bloque_display()}"
