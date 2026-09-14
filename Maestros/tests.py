import json
from datetime import datetime

from django.test import TestCase
from django.urls import reverse

from Directora.models import GradoSeccion, Maestro, Materia
from Login.models import Usuario
from .models import HorarioClase


class EstadosPropuestasHorarioTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='maestro-nuevo@cenalop.edu.sv', password='sistema123',
            nombre='Diego', apellido='Navarro', rol='maestro'
        )
        self.maestro = Maestro.objects.create(
            dui='98765432-1', nombre='Diego', apellido='Navarro',
            especialidad='Matemática', telefono='70001111', id_usuario=self.usuario
        )
        self.basica = GradoSeccion.objects.create(
            grado='6G', seccion='A', cupo_maximo=30, turno='mañana',
            maestro_encargado=self.maestro,
        )
        self.tercer = GradoSeccion.objects.create(
            grado='7G', seccion='A', cupo_maximo=30, turno='mañana'
        )
        self.materia = Materia.objects.create(nombre='Matemática', codigo='MA115')
        self.anio = datetime.now().year
        self.clase_basica = HorarioClase.objects.create(
            docente=self.maestro, grado_seccion=self.basica, materia=self.materia,
            dia=1, bloque=1, anio_lectivo=self.anio, estado='RECHAZADO',
            observaciones='Reorganizar el bloque del lunes.'
        )
        self.clase_tercer = HorarioClase.objects.create(
            docente=self.maestro, grado_seccion=self.tercer, materia=self.materia,
            dia=2, bloque=2, anio_lectivo=self.anio, estado='APROBADO'
        )
        self.client.force_login(self.usuario)

    def test_muestra_motivo_de_rechazo_solo_en_la_propuesta_rechazada(self):
        respuesta_basica = self.client.get(reverse('horarios'), {
            'nivel': 'basica', 'turno': 'manana'
        })
        respuesta_tercer = self.client.get(reverse('horarios'), {
            'nivel': 'tercer', 'turno': 'manana'
        })

        self.assertContains(respuesta_basica, 'Corrección solicitada')
        self.assertContains(respuesta_basica, 'Reorganizar el bloque del lunes.')
        self.assertNotContains(respuesta_tercer, 'Reorganizar el bloque del lunes.')

    def test_muestra_estados_independientes_por_nivel_y_turno(self):
        respuesta = self.client.get(reverse('horarios'), {
            'nivel': 'basica', 'turno': 'manana'
        })

        self.assertContains(respuesta, 'Estado de mis propuestas')
        self.assertContains(respuesta, 'Niveles básicos · Mañana')
        self.assertContains(respuesta, 'Tercer ciclo · Mañana')
        self.assertContains(respuesta, 'RECHAZADO')
        self.assertContains(respuesta, 'APROBADO')

    def test_reenvio_modifica_solo_nivel_y_turno_seleccionados(self):
        respuesta = self.client.post(
            reverse('enviar_horario_revision'),
            data=json.dumps({'nivel': 'basica', 'turno': 'Mañana'}),
            content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 200)
        self.clase_basica.refresh_from_db()
        self.clase_tercer.refresh_from_db()
        self.assertEqual(self.clase_basica.estado, 'ENVIADO')
        self.assertEqual(self.clase_basica.observaciones, '')
        self.assertEqual(self.clase_tercer.estado, 'APROBADO')

    def test_rechaza_envio_sin_nivel_identificado(self):
        respuesta = self.client.post(
            reverse('enviar_horario_revision'),
            data=json.dumps({'turno': 'Mañana'}),
            content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.clase_basica.estado, 'RECHAZADO')

# Create your tests here.
