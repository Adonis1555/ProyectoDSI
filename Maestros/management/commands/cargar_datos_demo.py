"""Instala los escenarios de defensa en una base de datos vacía."""

from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from Directora.models import (
    AsignacionBloqueMaestro, AsignacionMateria, GradoSeccion, Maestro, Materia,
)
from Login.models import Usuario
from Maestros.models import Alumno, HorarioClase, RegistroTarjeta


MODELOS_DEMO = (
    Usuario, Maestro, GradoSeccion, Materia, AsignacionMateria,
    AsignacionBloqueMaestro, Alumno, RegistroTarjeta, HorarioClase,
)
ARCHIVO_DEMO = Path(__file__).resolve().parents[2] / 'fixtures' / 'horarios_demo.json'
CLAVE_DEMO = 'sistema123'


class Command(BaseCommand):
    help = 'Carga los datos ficticios de defensa en una base vacía de desarrollo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar-demo', action='store_true',
            help='Confirma que se trata de una base local exclusiva para demostración.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG or not options['confirmar_demo']:
            raise CommandError(
                'Esta carga requiere DEBUG=True y --confirmar-demo; nunca la ejecutes en producción.'
            )
        ocupados = [modelo._meta.label for modelo in MODELOS_DEMO if modelo.objects.exists()]
        if ocupados:
            raise CommandError(
                'La base ya contiene datos de la aplicación. Usa una base recién migrada; '
                'no se borró ni sobrescribió ningún registro. Modelos ocupados: '
                + ', '.join(ocupados)
            )
        if not ARCHIVO_DEMO.is_file():
            raise CommandError(f'No se encontró el archivo de datos: {ARCHIVO_DEMO}')

        with transaction.atomic():
            call_command('loaddata', str(ARCHIVO_DEMO), verbosity=0)
            usuarios = list(Usuario.objects.all())
            if len(usuarios) != 13 or not any(
                usuario.email == 'directora@cenalop.edu.sv' and usuario.rol == 'directora'
                for usuario in usuarios
            ):
                raise CommandError('El archivo demo no contiene las cuentas esperadas.')
            for usuario in usuarios:
                usuario.set_password(CLAVE_DEMO)
                usuario.is_staff = False
                usuario.is_superuser = False
                usuario.save(update_fields=['password', 'is_staff', 'is_superuser'])

        self.stdout.write(self.style.SUCCESS(
            'Datos demo cargados: 13 cuentas. Contraseña de demostración: sistema123.'
        ))
