import json

from django.test import TestCase
from django.urls import reverse

from Login.models import Usuario
from Maestros.models import HorarioClase
from .models import AsignacionBloqueMaestro, AsignacionMateria, GradoSeccion, Maestro, Materia


class AsignacionBloquesMaestroTests(TestCase):
    def setUp(self):
        self.directora = Usuario.objects.create_user(
            email='directora@test.local',
            password='clave-segura',
            nombre='Ana',
            apellido='López',
            rol='directora',
        )
        usuario_maestro = Usuario.objects.create_user(
            email='maestro@test.local',
            password='clave-segura',
            nombre='Mario',
            apellido='Pérez',
            rol='maestro',
        )
        self.maestro = Maestro.objects.create(
            dui='01234567-8',
            nombre='Mario',
            apellido='Pérez',
            especialidad='Matemática',
            telefono='70000000',
            id_usuario=usuario_maestro,
        )
        self.client.force_login(self.directora)

    def guardar(self, bloques):
        return self.client.post(
            reverse('guardar_bloques_maestro'),
            data=json.dumps({
                'dui_maestro': self.maestro.dui,
                'anio_lectivo': 2026,
                'bloques': bloques,
            }),
            content_type='application/json',
        )

    def test_directora_puede_guardar_y_consultar_bloques(self):
        respuesta = self.guardar([
            {'dia': 1, 'bloque': 1},
            {'dia': 3, 'bloque': 4},
        ])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(AsignacionBloqueMaestro.objects.count(), 2)

        consulta = self.client.get(
            reverse('obtener_bloques_maestro', args=[self.maestro.dui]),
            {'anio': 2026},
        )
        self.assertEqual(consulta.status_code, 200)
        self.assertEqual(len(consulta.json()['bloques']), 2)

    def test_pantalla_muestra_la_pestana_y_cuadricula_de_bloques(self):
        respuesta = self.client.get(reverse('directora_materia'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Bloques Docentes')
        self.assertContains(respuesta, 'Asignación de bloques docentes')
        self.assertContains(respuesta, 'selector-maestro-bloques')
        self.assertContains(respuesta, 'Guardar asignación')

    def test_guardar_reemplaza_la_asignacion_anterior(self):
        self.guardar([{'dia': 1, 'bloque': 1}, {'dia': 2, 'bloque': 2}])
        respuesta = self.guardar([{'dia': 5, 'bloque': 5}])

        self.assertEqual(respuesta.status_code, 200)
        bloques = AsignacionBloqueMaestro.objects.values_list('dia', 'bloque')
        self.assertEqual(list(bloques), [(5, 5)])

    def test_rechaza_dias_o_bloques_inexistentes(self):
        respuesta = self.guardar([{'dia': 6, 'bloque': 9}])

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(AsignacionBloqueMaestro.objects.count(), 0)

    def test_maestro_no_puede_administrar_bloques(self):
        self.client.force_login(self.maestro.id_usuario)
        respuesta = self.guardar([{'dia': 1, 'bloque': 1}])

        self.assertEqual(respuesta.status_code, 403)


class AprobacionHorarioTercerCicloTests(TestCase):
    def setUp(self):
        self.directora = Usuario.objects.create_user(
            email='direccion@test.local', password='clave-segura',
            nombre='Laura', apellido='Gómez', rol='directora'
        )
        usuario_maestro = Usuario.objects.create_user(
            email='docente@test.local', password='clave-segura',
            nombre='Carlos', apellido='Martínez', rol='maestro'
        )
        self.maestro = Maestro.objects.create(
            dui='12345678-9', nombre='Carlos', apellido='Martínez',
            especialidad='Ciencias', telefono='71111111', id_usuario=usuario_maestro
        )
        self.tercer_ciclo = GradoSeccion.objects.create(
            grado='7G', seccion='A', cupo_maximo=30, turno='mañana'
        )
        self.basica = GradoSeccion.objects.create(
            grado='5G', seccion='A', cupo_maximo=30, turno='mañana'
        )
        self.materia = Materia.objects.create(nombre='Ciencias', codigo='CIE')
        self.clase_tercer_ciclo = HorarioClase.objects.create(
            docente=self.maestro, grado_seccion=self.tercer_ciclo,
            materia=self.materia, dia=1, bloque=1, anio_lectivo=2026,
            estado='ENVIADO'
        )
        self.clase_basica = HorarioClase.objects.create(
            docente=self.maestro, grado_seccion=self.basica,
            materia=self.materia, dia=2, bloque=2, anio_lectivo=2026,
            estado='ENVIADO'
        )
        self.client.force_login(self.directora)

    def resolver(self, accion, observaciones=''):
        return self.client.post(
            reverse('resolver_horario_tercer_ciclo'),
            data=json.dumps({
                'dui_maestro': self.maestro.dui,
                'anio_lectivo': 2026,
                'accion': accion,
                'observaciones': observaciones,
            }),
            content_type='application/json',
        )

    def test_pantalla_muestra_solo_horario_de_tercer_ciclo(self):
        respuesta = self.client.get(
            reverse('horarios_revision'),
            {'maestro': self.maestro.dui},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Revisión de horarios escolares')
        self.assertContains(respuesta, '7° Grado')
        self.assertNotContains(respuesta, '5° Grado')

    def test_directora_aprueba_solo_clases_de_tercer_ciclo(self):
        respuesta = self.resolver('aprobar')

        self.assertEqual(respuesta.status_code, 200)
        self.clase_tercer_ciclo.refresh_from_db()
        self.clase_basica.refresh_from_db()
        self.assertEqual(self.clase_tercer_ciclo.estado, 'APROBADO')
        self.assertEqual(self.clase_basica.estado, 'ENVIADO')

    def test_rechazo_requiere_y_guarda_observaciones(self):
        invalida = self.resolver('rechazar')
        self.assertEqual(invalida.status_code, 400)

        respuesta = self.resolver('rechazar', 'Corregir el choque del lunes.')
        self.assertEqual(respuesta.status_code, 200)
        self.clase_tercer_ciclo.refresh_from_db()
        self.assertEqual(self.clase_tercer_ciclo.estado, 'RECHAZADO')
        self.assertEqual(self.clase_tercer_ciclo.observaciones, 'Corregir el choque del lunes.')

    def test_maestro_no_puede_resolver_horarios(self):
        self.client.force_login(self.maestro.id_usuario)
        respuesta = self.resolver('aprobar')

        self.assertEqual(respuesta.status_code, 403)

    def resolver_basica(self, accion, observaciones=''):
        return self.client.post(
            reverse('resolver_horario_niveles_basicos'),
            data=json.dumps({
                'dui_maestro': self.maestro.dui,
                'anio_lectivo': 2026,
                'accion': accion,
                'observaciones': observaciones,
            }),
            content_type='application/json',
        )

    def test_pestana_basica_muestra_solo_niveles_basicos(self):
        respuesta = self.client.get(
            reverse('horarios_revision'),
            {'nivel': 'basica', 'maestro': self.maestro.dui},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Niveles básicos')
        self.assertContains(respuesta, '5° Grado')
        self.assertNotContains(respuesta, '7° Grado')

    def test_directora_aprueba_basica_sin_modificar_tercer_ciclo(self):
        respuesta = self.resolver_basica('aprobar')

        self.assertEqual(respuesta.status_code, 200)
        self.clase_tercer_ciclo.refresh_from_db()
        self.clase_basica.refresh_from_db()
        self.assertEqual(self.clase_basica.estado, 'APROBADO')
        self.assertEqual(self.clase_tercer_ciclo.estado, 'ENVIADO')

    def test_rechazo_de_basica_requiere_observaciones(self):
        invalida = self.resolver_basica('rechazar')
        self.assertEqual(invalida.status_code, 400)

        respuesta = self.resolver_basica('rechazar', 'Completar los bloques del viernes.')
        self.assertEqual(respuesta.status_code, 200)
        self.clase_basica.refresh_from_db()
        self.assertEqual(self.clase_basica.estado, 'RECHAZADO')
        self.assertEqual(self.clase_basica.observaciones, 'Completar los bloques del viernes.')

    def publicar(self, nivel):
        return self.client.post(
            reverse('publicar_horario'),
            data=json.dumps({
                'dui_maestro': self.maestro.dui,
                'anio_lectivo': 2026,
                'nivel': nivel,
            }),
            content_type='application/json',
        )

    def test_solo_se_puede_publicar_un_horario_aprobado(self):
        respuesta = self.publicar('tercer')

        self.assertEqual(respuesta.status_code, 400)
        self.clase_tercer_ciclo.refresh_from_db()
        self.assertEqual(self.clase_tercer_ciclo.estado, 'ENVIADO')

    def test_publicacion_afecta_solo_el_nivel_seleccionado(self):
        self.clase_basica.estado = 'APROBADO'
        self.clase_basica.save(update_fields=['estado'])

        respuesta = self.publicar('basica')

        self.assertEqual(respuesta.status_code, 200)
        self.clase_basica.refresh_from_db()
        self.clase_tercer_ciclo.refresh_from_db()
        self.assertEqual(self.clase_basica.estado, 'PUBLICADO')
        self.assertIsNotNone(self.clase_basica.fecha_publicacion)
        self.assertEqual(self.clase_tercer_ciclo.estado, 'ENVIADO')

    def test_pantalla_ofrece_publicar_cuando_esta_aprobado(self):
        self.clase_tercer_ciclo.estado = 'APROBADO'
        self.clase_tercer_ciclo.save(update_fields=['estado'])

        respuesta = self.client.get(
            reverse('horarios_revision'),
            {'nivel': 'tercer', 'maestro': self.maestro.dui},
        )

        self.assertContains(respuesta, 'Publicar horario')

    def test_maestro_no_puede_modificar_una_clase_publicada(self):
        self.clase_tercer_ciclo.estado = 'PUBLICADO'
        self.clase_tercer_ciclo.save(update_fields=['estado'])
        self.client.force_login(self.maestro.id_usuario)

        respuesta_guardar = self.client.post(
            reverse('guardar_bloque_horario'),
            data=json.dumps({
                'dia': 3,
                'bloque': 3,
                'grado_seccion_id': self.tercer_ciclo.id,
                'materia_id': self.materia.id,
                'anio_lectivo': 2026,
            }),
            content_type='application/json',
        )
        respuesta_eliminar = self.client.post(
            reverse('eliminar_bloque_horario'),
            data=json.dumps({'dia': 1, 'bloque': 1, 'anio_lectivo': 2026}),
            content_type='application/json',
        )

        self.assertEqual(respuesta_guardar.status_code, 400)
        self.assertEqual(respuesta_eliminar.status_code, 400)
        self.assertTrue(HorarioClase.objects.filter(id=self.clase_tercer_ciclo.id).exists())


class ReglasCargaAcademicaTests(TestCase):
    def setUp(self):
        self.directora = Usuario.objects.create_user(
            email='direccion-reglas@test.local', password='clave-segura',
            nombre='Laura', apellido='Gómez', rol='directora'
        )
        usuario_mate = Usuario.objects.create_user(
            email='mate@test.local', password='clave-segura',
            nombre='Elena', apellido='Castillo', rol='maestro'
        )
        usuario_info = Usuario.objects.create_user(
            email='info@test.local', password='clave-segura',
            nombre='Ricardo', apellido='Vásquez', rol='maestro'
        )
        self.matematica = Materia.objects.create(nombre='Matemática', codigo='MA115')
        self.informatica = Materia.objects.create(nombre='Informática', codigo='IN115')
        self.docente_mate = Maestro.objects.create(
            dui='10000001-1', nombre='Elena', apellido='Castillo',
            especialidad='Matemática', telefono='70000001', id_usuario=usuario_mate
        )
        self.docente_info = Maestro.objects.create(
            dui='10000002-2', nombre='Ricardo', apellido='Vásquez',
            especialidad='Informática', telefono='70000002', id_usuario=usuario_info
        )
        self.basica = GradoSeccion.objects.create(
            grado='2G', seccion='A', cupo_maximo=30, turno='mañana',
            maestro_encargado=self.docente_mate
        )
        self.otra_basica = GradoSeccion.objects.create(
            grado='3G', seccion='A', cupo_maximo=30, turno='mañana'
        )
        self.tercer = GradoSeccion.objects.create(
            grado='7G', seccion='A', cupo_maximo=35, turno='Tarde'
        )
        AsignacionBloqueMaestro.objects.create(
            maestro=self.docente_mate, dia=1, bloque=1,
            turno='Mañana', anio_lectivo=2026
        )
        AsignacionBloqueMaestro.objects.create(
            maestro=self.docente_mate, dia=1, bloque=1,
            turno='Tarde', anio_lectivo=2026
        )

    def test_distribucion_rechaza_el_turno_de_su_titularidad_basica(self):
        tercer_manana = GradoSeccion.objects.create(
            grado='8G', seccion='A', cupo_maximo=35, turno='Mañana'
        )
        self.client.force_login(self.directora)
        respuesta = self.client.post(reverse('asignar_materia_docente'), data=json.dumps({
            'grado_seccion_id': tercer_manana.id,
            'materia_id': self.matematica.id,
            'dui_maestro': self.docente_mate.dui,
            'anio_lectivo': 2026,
        }), content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)

    def asignar_materia(self, docente, materia):
        return self.client.post(reverse('asignar_materia_docente'), data=json.dumps({
            'grado_seccion_id': self.tercer.id,
            'materia_id': materia.id,
            'dui_maestro': docente.dui,
            'anio_lectivo': 2026,
        }), content_type='application/json')

    def guardar_clase(self, grado, materia):
        return self.client.post(reverse('guardar_bloque_horario'), data=json.dumps({
            'dia': 1, 'bloque': 1, 'grado_seccion_id': grado.id,
            'materia_id': materia.id, 'anio_lectivo': 2026,
        }), content_type='application/json')

    def test_maestro_no_puede_usar_un_bloque_no_asignado(self):
        self.client.force_login(self.docente_mate.id_usuario)
        respuesta = self.client.post(reverse('guardar_bloque_horario'), data=json.dumps({
            'dia': 1, 'bloque': 2, 'grado_seccion_id': self.basica.id,
            'materia_id': self.matematica.id, 'anio_lectivo': 2026,
        }), content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('no está asignado', respuesta.json()['error'])

    def test_direccion_no_puede_retirar_un_bloque_ocupado(self):
        HorarioClase.objects.create(
            docente=self.docente_mate, grado_seccion=self.basica,
            materia=self.matematica, dia=1, bloque=1, anio_lectivo=2026
        )
        self.client.force_login(self.directora)
        respuesta = self.client.post(reverse('guardar_bloques_maestro'), data=json.dumps({
            'dui_maestro': self.docente_mate.dui, 'turno': 'Mañana',
            'anio_lectivo': 2026, 'bloques': [],
        }), content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(AsignacionBloqueMaestro.objects.filter(
            maestro=self.docente_mate, turno='Mañana', dia=1, bloque=1
        ).exists())

    def test_distribucion_rechaza_especialidad_incompatible(self):
        self.client.force_login(self.directora)
        respuesta = self.asignar_materia(self.docente_info, self.matematica)
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(AsignacionMateria.objects.exists())

    def test_distribucion_acepta_especialidad_compatible(self):
        self.client.force_login(self.directora)
        respuesta = self.asignar_materia(self.docente_mate, self.matematica)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(AsignacionMateria.objects.filter(docente=self.docente_mate).exists())

    def test_titular_basica_puede_usar_todas_las_materias_solo_en_su_grado(self):
        self.client.force_login(self.docente_mate.id_usuario)
        permitida = self.guardar_clase(self.basica, self.informatica)
        denegada = self.guardar_clase(self.otra_basica, self.matematica)
        self.assertEqual(permitida.status_code, 200)
        self.assertEqual(denegada.status_code, 400)

    def test_especialista_tercer_ciclo_necesita_distribucion(self):
        self.client.force_login(self.docente_mate.id_usuario)
        sin_asignacion = self.guardar_clase(self.tercer, self.matematica)
        self.assertEqual(sin_asignacion.status_code, 400)
        AsignacionMateria.objects.create(
            grado_seccion=self.tercer, materia=self.matematica,
            docente=self.docente_mate, anio_lectivo=2026
        )
        con_asignacion = self.guardar_clase(self.tercer, self.matematica)
        self.assertEqual(con_asignacion.status_code, 200)

    def test_orientador_tercer_ciclo_debe_estar_sin_otro_grado(self):
        self.client.force_login(self.directora)
        respuesta = self.client.post(reverse('asignar_grado_maestro'), data=json.dumps({
            'maestro_dui': self.docente_mate.dui,
            'grado_id': self.tercer.id,
        }), content_type='application/json')
        self.assertFalse(respuesta.json()['ok'])

        respuesta_valida = self.client.post(reverse('asignar_grado_maestro'), data=json.dumps({
            'maestro_dui': self.docente_info.dui,
            'grado_id': self.tercer.id,
        }), content_type='application/json')
        self.assertTrue(respuesta_valida.json()['ok'])
