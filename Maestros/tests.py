import json
from io import StringIO
from datetime import datetime

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from Directora.models import AsignacionBloqueMaestro, AsignacionMateria, GradoSeccion, Maestro, Materia
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


class NavegacionHorarioTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='nuevo-horario@cenalop.edu.sv', password='sistema123',
            nombre='Nuevo', apellido='Docente', rol='maestro'
        )
        self.maestro = Maestro.objects.create(
            dui='12345678-9', nombre='Nuevo', apellido='Docente',
            especialidad='Matemática', telefono='70001112', id_usuario=self.usuario
        )
        self.materia = Materia.objects.create(nombre='Matemática', codigo='MAT')
        self.client.force_login(self.usuario)

    def vista(self, nivel, turno):
        return self.client.get(reverse('horarios'), {'nivel': nivel, 'turno': turno})

    def test_docente_sin_carga_puede_ver_las_cuatro_combinaciones(self):
        for nivel in ('basica', 'tercer'):
            for turno in ('manana', 'tarde'):
                with self.subTest(nivel=nivel, turno=turno):
                    respuesta = self.vista(nivel, turno)
                    self.assertEqual(respuesta.context['nivel_actual'], nivel)
                    self.assertEqual(respuesta.context['turno_actual'], 'Tarde' if turno == 'tarde' else 'Mañana')
                    self.assertContains(respuesta, 'No tienes carga académica asignada para este nivel y turno')
                    self.assertNotContains(respuesta, 'id="btnEnviarDireccion"')
                    self.assertNotContains(respuesta, '>Guardar borrador</button>')
                    self.assertNotContains(respuesta, 'class="btn-asignar-bloque"')

    def test_basica_se_habilita_al_asignar_seccion_y_bloques(self):
        seccion = GradoSeccion.objects.create(
            grado='6G', seccion='B', turno='tarde', maestro_encargado=self.maestro
        )
        respuesta = self.vista('basica', 'tarde')
        self.assertTrue(respuesta.context['tiene_carga'])
        self.assertContains(respuesta, 'Necesitas bloques asignados por Dirección')
        self.assertNotContains(respuesta, 'class="btn-asignar-bloque"')
        AsignacionBloqueMaestro.objects.create(
            maestro=self.maestro, dia=1, bloque=1, turno='Tarde', anio_lectivo=datetime.now().year
        )
        respuesta = self.vista('basica', 'tarde')
        self.assertTrue(respuesta.context['puede_programar'])
        self.assertContains(respuesta, 'class="btn-asignar-bloque"')
        self.assertNotContains(respuesta, 'id="btnEnviarDireccion"')
        self.assertEqual(respuesta.context['materias_disponibles'][0]['grado_seccion'], seccion)

    def test_tercer_ciclo_en_turno_opuesto_y_propuesta_previa(self):
        GradoSeccion.objects.create(
            grado='5G', seccion='B', turno='mañana', maestro_encargado=self.maestro
        )
        tercer = GradoSeccion.objects.create(grado='7G', seccion='B', turno='tarde')
        AsignacionMateria.objects.create(
            grado_seccion=tercer, materia=self.materia,
            docente=self.maestro, anio_lectivo=datetime.now().year
        )
        AsignacionBloqueMaestro.objects.create(
            maestro=self.maestro, dia=1, bloque=1, turno='Tarde', anio_lectivo=datetime.now().year
        )
        respuesta = self.vista('tercer', 'tarde')
        self.assertEqual(respuesta.context['nivel_actual'], 'tercer')
        self.assertTrue(respuesta.context['puede_programar'])
        self.assertContains(respuesta, 'class="btn-asignar-bloque"')
        clase = HorarioClase.objects.create(
            docente=self.maestro, grado_seccion=tercer, materia=self.materia,
            dia=1, bloque=1, anio_lectivo=datetime.now().year,
            estado='RECHAZADO', observaciones='Cambiar distribución.'
        )
        AsignacionMateria.objects.filter(docente=self.maestro).delete()
        respuesta = self.vista('tercer', 'tarde')
        self.assertFalse(respuesta.context['tiene_carga'])
        self.assertContains(respuesta, 'Cambiar distribución.')
        self.assertContains(respuesta, 'RECHAZADO')
        self.assertNotContains(respuesta, 'id="btnEnviarDireccion"')
        clase.refresh_from_db()
        self.assertEqual(clase.estado, 'RECHAZADO')

    def test_tercer_ciclo_exige_turno_opuesto_y_especialidad(self):
        GradoSeccion.objects.create(
            grado='5G', seccion='C', turno='mañana', maestro_encargado=self.maestro
        )
        mismo_turno = GradoSeccion.objects.create(grado='7G', seccion='C', turno='mañana')
        opuesto = GradoSeccion.objects.create(grado='8G', seccion='C', turno='tarde')
        otra_materia = Materia.objects.create(nombre='Ciencias', codigo='CIE')
        for seccion, materia in ((mismo_turno, self.materia), (opuesto, otra_materia)):
            AsignacionMateria.objects.create(
                grado_seccion=seccion, materia=materia,
                docente=self.maestro, anio_lectivo=datetime.now().year
            )
        for turno in ('manana', 'tarde'):
            respuesta = self.vista('tercer', turno)
            self.assertFalse(respuesta.context['tiene_carga'])
            self.assertContains(respuesta, 'No tienes carga académica asignada')
        AsignacionMateria.objects.filter(grado_seccion=opuesto).update(materia=self.materia)
        respuesta = self.vista('tercer', 'tarde')
        self.assertTrue(respuesta.context['tiene_carga'])


@override_settings(DEBUG=True)
class DatosDemoTests(TestCase):
    def test_carga_escenarios_y_credenciales_en_base_vacia(self):
        from Directora.models import AsignacionBloqueMaestro, AsignacionMateria
        from .models import Alumno, RegistroTarjeta

        call_command('cargar_datos_demo', '--confirmar-demo', stdout=StringIO())
        self.assertEqual(Usuario.objects.count(), 13)
        self.assertEqual(GradoSeccion.objects.count(), 14)
        self.assertEqual(AsignacionMateria.objects.count(), 15)
        self.assertEqual(AsignacionBloqueMaestro.objects.count(), 180)
        self.assertEqual(HorarioClase.objects.count(), 90)
        self.assertEqual(Alumno.objects.count(), 52)
        self.assertEqual(RegistroTarjeta.objects.count(), 67)
        self.assertEqual(
            set(HorarioClase.objects.values_list('estado', flat=True)),
            {'ENVIADO', 'RECHAZADO', 'APROBADO', 'PUBLICADO'},
        )
        directora = Usuario.objects.get(email='directora@cenalop.edu.sv')
        self.assertTrue(directora.check_password('sistema123'))
        self.assertFalse(directora.is_superuser)
        self.assertTrue(self.client.login(email=directora.email, password='sistema123'))
        self.assertTrue(Usuario.objects.get(email='maestro20@cenalop.edu.sv').check_password('sistema123'))
        self.assertFalse(Usuario.objects.get(email='maestro1@cenalop.edu.sv').is_active)

    def test_rechaza_base_con_datos_sin_borrar_registros(self):
        Usuario.objects.create_user(
            email='existente@example.test', password='clave-larga',
            nombre='Existente', apellido='Local', rol='maestro',
        )
        with self.assertRaises(CommandError):
            call_command('cargar_datos_demo', '--confirmar-demo', stdout=StringIO())
        self.assertEqual(Usuario.objects.count(), 1)
