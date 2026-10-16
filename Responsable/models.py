from django.db import models

from django.core.exceptions import ValidationError
from Login.models import Usuario


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