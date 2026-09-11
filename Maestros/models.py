from datetime import date, datetime
from django.db import models
from django.conf import settings
from Directora.models import Maestro, GradoSeccion, Materia


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
    fecha = models.DateField(default=date.today) 

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


class HorarioClase(models.Model):
    DIAS_SEMANA = [
        (1, 'Lunes'),
        (2, 'Martes'),
        (3, 'Miércoles'),
        (4, 'Jueves'),
        (5, 'Viernes'),
    ]

    ESTADOS = [
        ('BORRADOR', 'Borrador'),
        ('ENVIADO', 'Enviado para Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    docente = models.ForeignKey(
        Maestro, 
        on_delete=models.CASCADE, 
        related_name='horarios_clase'
    )
    grado_seccion = models.ForeignKey(
        GradoSeccion, 
        on_delete=models.CASCADE, 
        related_name='horarios'
    )
    materia = models.ForeignKey(
        Materia, 
        on_delete=models.CASCADE
    )
    dia = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    bloque = models.PositiveSmallIntegerField(
        help_text="Número de bloque de clase (1 a 7)"
    )
    anio_lectivo = models.PositiveIntegerField(default=2026)

    estado = models.CharField(
        max_length=15,
        choices=ESTADOS,
        default='BORRADOR',
        verbose_name="Estado de Aprobación"
    )
    observaciones = models.TextField(
        blank=True, 
        null=True, 
        help_text="Retroalimentación o motivo de rechazo de Dirección"
    )

    class Meta:
        verbose_name = "Horario de Clase"
        verbose_name_plural = "Horarios de Clases"
        unique_together = [
            ('docente', 'dia', 'bloque', 'anio_lectivo'),
            ('grado_seccion', 'dia', 'bloque', 'anio_lectivo'),
        ]


    def __str__(self):
        return f"{self.get_dia_display()} Bloque {self.bloque}: {self.materia} ({self.grado_seccion})"


# Función auxiliar que recibe la instancia del maestro
def obtener_materias_docente(maestro, anio=None):
    if anio is None:
        anio = datetime.now().year

    materias_permitidas = []
    from Directora.models import AsignacionMateria

    # 1. Caso Educación Básica: Es titular de la sección
    secciones_titular = maestro.grados_a_cargo.filter(activo=True)
    todas_las_materias = list(Materia.objects.all())

    for sec in secciones_titular:
        if not sec.es_tercer_ciclo:
            for mat in todas_las_materias:
                materias_permitidas.append({
                    'grado_seccion': sec,
                    'materia': mat,
                    'tipo': 'Basica (Titular)'
                })

    # 2. Caso Tercer Ciclo: Asignaciones específicas
    asignaciones = AsignacionMateria.objects.filter(
        docente=maestro,
        anio_lectivo=anio
    ).select_related('grado_seccion', 'materia')

    for asig in asignaciones:
        materias_permitidas.append({
            'grado_seccion': asig.grado_seccion,
            'materia': asig.materia,
            'tipo': 'Tercer Ciclo (Especialista)'
        })

    return materias_permitidas