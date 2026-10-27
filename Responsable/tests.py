from datetime import date

from django.test import TestCase
from django.urls import reverse

from Directora.models import ConfiguracionPeriodo, GradoSeccion, Maestro
from Login.models import Usuario
from .models import FichaMatricula, Responsable


class FichaMatriculaResponsableTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='responsable-flujo@example.com', password='sistema123',
            nombre='Rosa', apellido='Pérez', rol='responsable', activo=True,
        )
        self.responsable = Responsable.objects.create(
            dui='33333333-3', nombre='Rosa', apellido='Pérez',
            telefono='7000-0000', id_usuario=self.usuario,
        )
        usuario_maestro = Usuario.objects.create_user(
            email='maestro-ficha@example.com', password='sistema123',
            nombre='Mario', apellido='López', rol='maestro',
        )
        maestro = Maestro.objects.create(
            dui='44444444-4', nombre='Mario', apellido='López',
            especialidad='Educación Básica', telefono='70000001',
            id_usuario=usuario_maestro,
        )
        self.seccion = GradoSeccion.objects.create(
            grado='3G', seccion='A', turno='mañana', activo=True,
            maestro_encargado=maestro,
        )
        ConfiguracionPeriodo.objects.update_or_create(
            id=1, defaults={'fase_actual': 'MATRICULA', 'anio_activo': 2026}
        )
        self.client.force_login(self.usuario)

    def test_abre_formulario_durante_periodo_de_matricula(self):
        respuesta = self.client.get(reverse('ficha_matricula'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ficha de Inscripción y Matrícula 2026')
        self.assertContains(respuesta, '3° Grado')

    def test_envia_solicitud_con_anio_lectivo_activo(self):
        respuesta = self.client.post(reverse('ficha_matricula'), {
            'nie': '20269999',
            'grado_solicitado': '3G',
            'seccion_solicitada': 'A',
            'nombre': 'Estudiante',
            'apellido': 'Prueba',
            'fecha_nacimiento': date(2017, 5, 10).isoformat(),
            'genero': 'F',
            'parentesco_resp': 'Madre',
            'telefono_resp': '70000000',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['ok'])
        ficha = FichaMatricula.objects.get(nie='20269999')
        self.assertEqual(ficha.anio_lectivo, 2026)
        self.assertEqual(ficha.responsable, self.responsable)
        self.assertEqual(ficha.estado, 'PENDIENTE')

# Create your tests here.
