import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from django.db import close_old_connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from Login.models import Usuario
from Maestros.models import Alumno, HorarioClase, RegistroTarjeta
from Responsable.models import FichaMatricula, Matricula, Responsable, RevisionFicha
from .models import AsignacionBloqueMaestro, AsignacionMateria, CierrePeriodo, ConfiguracionPeriodo, GradoSeccion, Maestro, Materia
from .views import cerrar_matricula


class EscenarioPeriodo:
    def preparar(self):
        self.periodo = ConfiguracionPeriodo.objects.create(pk=1, anio_activo=2028, fase_actual='MATRICULA')
        self.directora = Usuario.objects.create_user(email='direccion@periodo.test', password='clave-segura', nombre='Ana', apellido='Dirección', rol='directora')
        self.usuario_maestro = Usuario.objects.create_user(email='maestro@periodo.test', password='clave-segura', nombre='Luis', apellido='Docente', rol='maestro')
        self.maestro = Maestro.objects.create(dui='11111111-1', nombre='Luis', apellido='Docente', especialidad='Matemática', telefono='70000001', id_usuario=self.usuario_maestro)
        self.seccion = GradoSeccion.objects.create(grado='3G', seccion='A', turno='Mañana', cupo_maximo=10, maestro_encargado=self.maestro)
        self.materia = Materia.objects.create(nombre='Matemática', nivel_aplicable='BASICA', bloques_semanales=1)
        self.bloque = AsignacionBloqueMaestro.objects.create(maestro=self.maestro, dia=1, bloque=1, turno='Mañana', anio_lectivo=2028)
        self.clase = HorarioClase.objects.create(docente=self.maestro, grado_seccion=self.seccion, materia=self.materia, dia=1, bloque=1, turno='Mañana', anio_lectivo=2028, estado='PUBLICADO')
        self.usuario_responsable = Usuario.objects.create_user(email='responsable@periodo.test', password='clave-segura', nombre='María', apellido='Responsable', rol='responsable')
        self.responsable = Responsable.objects.create(dui='22222222-2', nombre='María', apellido='Responsable', telefono='70000002', id_usuario=self.usuario_responsable)
        self.alumno = Alumno.objects.create(NIE='20280001', nombre='Alumno', apellido='Matriculado', fecha_nac=date(2018, 1, 1), sexo='M', grado_seccion=self.seccion)
        Matricula.objects.create(alumno=self.alumno, grado_seccion=self.seccion, anio_lectivo=2028)
        self.ficha = self.crear_ficha('20280001', 'APROBADA')
        self.client.force_login(self.directora)

    def crear_ficha(self, nie, estado='PENDIENTE'):
        return FichaMatricula.objects.create(
            responsable=self.responsable, grado_seccion=self.seccion, anio_lectivo=2028,
            nie=nie, nombres='Alumno', apellidos='Solicitud', fecha_nacimiento=date(2018, 1, 1),
            genero='M', parentesco_responsable='Madre', telefono_contacto='70000002', estado=estado,
        )

    def cerrar(self, **cambios):
        datos = {'anio_activo': '2028', 'confirmacion': 'CERRAR MATRICULA'}
        datos.update(cambios)
        return self.client.post(reverse('cerrar_matricula'), datos)

    def datos_envio(self):
        return {
            'anio_activo': '2028', 'nie': '20280002', 'nombre': 'Alumno', 'apellido': 'Corregido',
            'grado_solicitado': '3G', 'seccion_solicitada': 'A', 'genero': 'M',
            'fecha_nacimiento': '2018-01-01', 'parentesco_resp': 'Madre', 'telefono_resp': '70000002',
        }


class CierreMatriculaTests(EscenarioPeriodo, TestCase):
    def setUp(self):
        self.preparar()

    def test_revision_no_modifica_fase_y_expone_requisitos(self):
        respuesta = self.client.get(reverse('revision_cierre_matricula'))
        self.assertTrue(respuesta.json()['puede_cerrar'])
        self.assertEqual(len(respuesta.json()['requisitos']), 4)
        self.periodo.refresh_from_db()
        self.assertEqual(self.periodo.fase_actual, 'MATRICULA')
        self.assertFalse(CierrePeriodo.objects.exists())

    def test_cierre_conserva_anio_datos_y_registra_autoria(self):
        self.assertEqual(self.cerrar().status_code, 200)
        self.periodo.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('CLASES', 2028))
        cierre = CierrePeriodo.objects.get()
        self.assertEqual(cierre.realizado_por, self.directora)
        self.assertEqual(cierre.fase_cerrada, 'MATRICULA')
        self.assertEqual(cierre.fase_abierta, 'CLASES')
        self.assertTrue(cierre.resumen['puede_cerrar'])
        self.clase.refresh_from_db()
        self.seccion.refresh_from_db()
        self.bloque.refresh_from_db()
        self.assertEqual(self.clase.estado, 'PUBLICADO')
        self.assertEqual(self.seccion.maestro_encargado, self.maestro)
        self.assertTrue(self.bloque.activo)
        self.assertEqual(Matricula.objects.count(), 1)

    def test_pendientes_y_subsanaciones_impiden_cierre(self):
        ficha = self.crear_ficha('20280002')
        for estado in ('PENDIENTE', 'RECHAZADA'):
            ficha.estado = estado
            ficha.save()
            with self.subTest(estado=estado):
                self.assertEqual(self.cerrar().status_code, 409)
                self.assertFalse(CierrePeriodo.objects.exists())

    def test_revalida_si_cambian_requisitos_despues_de_revision(self):
        self.assertTrue(self.client.get(reverse('revision_cierre_matricula')).json()['puede_cerrar'])
        self.crear_ficha('20280002')
        self.assertEqual(self.cerrar().status_code, 409)

    def test_bloquea_docente_ausente_o_inactivo(self):
        self.maestro.activo = False
        self.maestro.save()
        self.assertEqual(self.cerrar().status_code, 409)

    def test_bloquea_cupos_y_matriculas_inconsistentes(self):
        self.seccion.cupo_maximo = 0
        self.seccion.save()
        self.assertEqual(self.cerrar().status_code, 409)
        self.seccion.cupo_maximo = 10
        self.seccion.save()
        Matricula.objects.all().delete()
        self.assertEqual(self.cerrar().status_code, 409)

    def test_bloquea_horario_incompleto_no_publicado_y_sin_bloques(self):
        self.materia.bloques_semanales = 2
        self.materia.save()
        self.assertEqual(self.cerrar().status_code, 409)
        self.materia.bloques_semanales = 1
        self.materia.save()
        self.clase.estado = 'APROBADO'
        self.clase.save()
        self.assertEqual(self.cerrar().status_code, 409)
        self.clase.estado = 'PUBLICADO'
        self.clase.save()
        self.bloque.activo = False
        self.bloque.save()
        self.assertEqual(self.cerrar().status_code, 409)

    def test_tercer_ciclo_necesita_distribucion_especialidad_y_publicacion(self):
        usuario = Usuario.objects.create_user(email='especialista@periodo.test', nombre='Julia', apellido='Docente', rol='maestro')
        especialista = Maestro.objects.create(dui='33333333-3', nombre='Julia', apellido='Docente', especialidad='Matemática', telefono='70000003', id_usuario=usuario)
        seccion = GradoSeccion.objects.create(grado='7G', seccion='B', turno='Tarde', cupo_maximo=20, maestro_encargado=especialista)
        self.materia.nivel_aplicable = 'BASICA_Y_TERCER'
        self.materia.save()
        self.assertEqual(self.cerrar().status_code, 409)
        AsignacionMateria.objects.create(grado_seccion=seccion, materia=self.materia, docente=especialista, anio_lectivo=2028)
        AsignacionBloqueMaestro.objects.create(maestro=especialista, dia=1, bloque=1, turno='Tarde', anio_lectivo=2028)
        HorarioClase.objects.create(docente=especialista, grado_seccion=seccion, materia=self.materia, dia=1, bloque=1, anio_lectivo=2028, estado='PUBLICADO')
        especialista.especialidad = 'Ciencias'
        especialista.save()
        self.assertEqual(self.cerrar().status_code, 409)
        especialista.especialidad = 'Matemática'
        especialista.save()
        self.assertEqual(self.cerrar().status_code, 200)

    def test_solo_direccion_puede_revisar_y_cerrar(self):
        for usuario in (self.usuario_maestro, self.usuario_responsable):
            self.client.force_login(usuario)
            self.assertEqual(self.cerrar().status_code, 403)
            self.assertEqual(self.client.get(reverse('revision_cierre_matricula')).status_code, 403)

    def test_requiere_post_confirmacion_y_anio_actual(self):
        self.assertEqual(self.client.get(reverse('cerrar_matricula')).status_code, 405)
        self.assertEqual(self.cerrar(confirmacion='').status_code, 400)
        self.assertEqual(self.cerrar(anio_activo='2026').status_code, 400)

    def test_cierre_requiere_proteccion_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.directora)
        respuesta = cliente.post(reverse('cerrar_matricula'), {'anio_activo': '2028', 'confirmacion': 'CERRAR MATRICULA'})
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(CierrePeriodo.objects.exists())

    def test_un_error_revierte_fase_y_bitacora_juntas(self):
        with patch.object(ConfiguracionPeriodo, 'save', side_effect=RuntimeError('Fallo simulado')):
            with self.assertRaises(RuntimeError):
                self.cerrar()
        self.periodo.refresh_from_db()
        self.assertEqual(self.periodo.fase_actual, 'MATRICULA')
        self.assertFalse(CierrePeriodo.objects.exists())

    def test_doble_click_y_ruta_anterior_no_abren_otro_anio(self):
        self.assertEqual(self.cerrar().status_code, 200)
        self.assertEqual(self.cerrar().status_code, 409)
        self.assertEqual(self.client.post(reverse('alternar_periodo')).status_code, 409)
        self.periodo.refresh_from_db()
        self.assertEqual(self.periodo.anio_activo, 2028)
        self.assertEqual(CierrePeriodo.objects.count(), 1)


class PermisosPeriodoTests(EscenarioPeriodo, TestCase):
    def setUp(self):
        self.preparar()

    def test_clases_rechaza_escrituras_de_planificacion_incluso_peticiones_directas(self):
        self.cerrar()
        for nombre in ('guardar_materia', 'actualizar_materia', 'eliminar_materia', 'guardar_bloques_maestro',
                       'asignar_materia_docente', 'asignar_grado_maestro', 'desasignar_grado_maestro',
                       'resolver_horario_tercer_ciclo', 'resolver_horario_niveles_basicos', 'publicar_horario'):
            with self.subTest(ruta=nombre):
                respuesta = self.client.post(reverse(nombre), '{}', content_type='application/json')
                self.assertEqual(respuesta.status_code, 403)
        self.client.force_login(self.usuario_maestro)
        for nombre in ('guardar_bloque_horario', 'eliminar_bloque_horario', 'enviar_horario_revision', 'registro_alumnos'):
            self.assertEqual(self.client.post(reverse(nombre)).status_code, 403)
        self.assertEqual(self.client.post(reverse('resolver_solicitud_matricula', args=[self.ficha.id]), {'accion': 'aceptar'}).status_code, 403)
        self.client.force_login(self.usuario_responsable)
        self.assertEqual(self.client.post(reverse('ficha_matricula'), self.datos_envio()).status_code, 403)

    def test_conducta_solo_en_clases_para_matriculados_del_anio_activo(self):
        self.client.force_login(self.usuario_maestro)
        url = reverse('registrar_demerito', args=[self.alumno.pk])
        datos = {'tipo_registro': 'D', 'escala': 'A', 'fecha': '2028-03-10'}
        self.assertEqual(self.client.post(url, json.dumps(datos), content_type='application/json').status_code, 403)
        self.periodo.fase_actual = 'CLASES'
        self.periodo.save()
        self.assertTrue(self.client.post(url, json.dumps(datos), content_type='application/json').json()['ok'])
        datos['fecha'] = '2027-03-10'
        self.assertEqual(self.client.post(url, json.dumps(datos), content_type='application/json').status_code, 400)
        datos['fecha'] = '2028-03-10'
        Matricula.objects.all().delete()
        self.assertEqual(self.client.post(url, json.dumps(datos), content_type='application/json').status_code, 400)
        self.assertEqual(RegistroTarjeta.objects.count(), 1)

    def test_anio_enviado_no_puede_modificar_historial(self):
        respuesta = self.client.post(reverse('guardar_bloques_maestro'), json.dumps({'anio_lectivo': 2026}), content_type='application/json')
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(AsignacionBloqueMaestro.objects.filter(pk=self.bloque.pk).exists())

    def test_ficha_antigua_no_se_puede_aceptar(self):
        ficha = self.crear_ficha('20280002')
        ficha.anio_lectivo = 2027
        ficha.save()
        self.client.force_login(self.usuario_maestro)
        self.assertEqual(self.client.post(reverse('resolver_solicitud_matricula', args=[ficha.id]), {'accion': 'aceptar'}).status_code, 409)

    def test_aceptar_no_sobrescribe_matricula_ni_excede_cupo(self):
        ficha = self.crear_ficha('20280002')
        self.client.force_login(self.usuario_maestro)
        url = reverse('resolver_solicitud_matricula', args=[ficha.pk])
        self.seccion.cupo_maximo = 1
        self.seccion.save()
        self.client.post(url, {'accion': 'aceptar'})
        ficha.refresh_from_db()
        self.assertEqual(ficha.estado, 'PENDIENTE')
        self.seccion.cupo_maximo = 10
        self.seccion.save()
        ficha.nie = self.alumno.pk
        ficha.save()
        self.client.post(url, {'accion': 'aceptar'})
        ficha.refresh_from_db()
        self.assertEqual(ficha.estado, 'PENDIENTE')
        self.assertEqual(Matricula.objects.count(), 1)

    def test_registro_manual_crea_matricula_del_anio_activo(self):
        self.client.force_login(self.usuario_maestro)
        respuesta = self.client.post(reverse('registro_alumnos'), {
            'nie': '20280002', 'nombre': 'Nuevo', 'apellido': 'Alumno', 'sexo': 'M',
            'grado': '3G', 'seccion': 'A', 'fecha_nac': '2017-01-01',
        })
        self.assertTrue(respuesta.json()['ok'])
        self.assertTrue(Matricula.objects.filter(alumno_id='20280002', anio_lectivo=2028).exists())

    def test_subsanar_reenviar_y_aceptar_conserva_historial(self):
        ficha = self.crear_ficha('20280002')
        self.client.force_login(self.usuario_maestro)
        resolver = reverse('resolver_solicitud_matricula', args=[ficha.id])
        self.client.post(resolver, {'accion': 'subsanar', 'observaciones': 'Completar dirección.'})
        self.client.force_login(self.usuario_responsable)
        url = reverse('corregir_ficha', args=[ficha.id])
        self.assertContains(self.client.get(url), 'Completar dirección.')
        datos = self.datos_envio()
        datos['direccion_exacta'] = 'Dirección corregida'
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['ok'])
        ficha.refresh_from_db()
        self.assertEqual(ficha.estado, 'PENDIENTE')
        self.assertEqual(FichaMatricula.objects.filter(nie=ficha.nie).count(), 1)
        self.assertEqual(list(ficha.revisiones.values_list('accion', flat=True)), ['SUBSANAR', 'REENVIAR'])
        self.assertEqual(ficha.revisiones.last().datos_anteriores['observaciones'], 'Completar dirección.')
        self.client.force_login(self.usuario_maestro)
        self.client.post(resolver, {'accion': 'aceptar'})
        ficha.refresh_from_db()
        self.assertEqual(ficha.estado, 'APROBADA')
        self.assertEqual(RevisionFicha.objects.filter(ficha=ficha).count(), 3)

    def test_subsanacion_ajena_o_ya_reenviada_no_se_puede_editar(self):
        ficha = self.crear_ficha('20280002', 'RECHAZADA')
        ajeno = Usuario.objects.create_user(email='ajeno@periodo.test', nombre='Otro', apellido='Responsable', rol='responsable')
        Responsable.objects.create(dui='99999999-9', nombre='Otro', apellido='Responsable', telefono='70000009', id_usuario=ajeno)
        self.client.force_login(ajeno)
        url = reverse('corregir_ficha', args=[ficha.pk])
        self.assertEqual(self.client.post(url, self.datos_envio()).status_code, 404)
        self.client.force_login(self.usuario_responsable)
        ficha.estado = 'PENDIENTE'
        ficha.save()
        self.assertEqual(self.client.post(url, self.datos_envio()).status_code, 403)

    def test_clases_conserva_consultas_y_oculta_acciones_docentes(self):
        self.cerrar()
        self.client.force_login(self.usuario_maestro)
        respuesta = self.client.get(reverse('control_alumnos'), {'vista': 'registrados'})
        self.assertContains(respuesta, 'Alumno Matriculado')
        self.assertNotContains(respuesta, '+ Registrar Alumno')
        respuesta = self.client.get(reverse('solicitud_matricula_detalle', args=[self.ficha.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Aceptar solicitud')
        self.assertNotContains(self.client.get(reverse('horarios')), 'id="btnEnviarDireccion"')

    def test_pantallas_de_direccion_siguen_abriendo_en_modo_consulta(self):
        self.cerrar()
        for ruta in ('grado_seccion_control', 'directora_materia', 'horarios_revision'):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(reverse(ruta))
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'planificación académica de solo lectura')
        respuesta = self.client.get(reverse('dashboard_directora'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="btnRevisarCierre"')
        self.assertNotContains(respuesta, 'id="btn_toggle_periodo"')


class CierreConcurrenteTests(EscenarioPeriodo, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def test_dos_confirmaciones_simultaneas_registran_un_solo_cierre(self):
        def confirmar(_):
            close_old_connections()
            try:
                solicitud = RequestFactory().post('/directora/periodo/cerrar-matricula/', {
                    'anio_activo': '2028', 'confirmacion': 'CERRAR MATRICULA',
                })
                solicitud.user = Usuario.objects.get(pk=self.directora.pk)
                return cerrar_matricula(solicitud).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(confirmar, range(2)))
        self.assertEqual(sorted(resultados), [200, 409])
        self.assertEqual(CierrePeriodo.objects.count(), 1)
        self.periodo.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('CLASES', 2028))

    def test_envio_simultaneo_no_puede_quedar_pendiente_despues_del_cierre(self):
        cliente_responsable = Client()
        cliente_responsable.force_login(self.usuario_responsable)

        def cerrar():
            close_old_connections()
            try:
                return self.cerrar().status_code
            finally:
                close_old_connections()

        def enviar():
            close_old_connections()
            try:
                return cliente_responsable.post(reverse('ficha_matricula'), self.datos_envio()).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futuro_cierre = pool.submit(cerrar)
            futuro_envio = pool.submit(enviar)
            resultados = (futuro_cierre.result(), futuro_envio.result())
        self.assertIn(resultados, [(200, 403), (409, 200)])
        self.periodo.refresh_from_db()
        if self.periodo.fase_actual == 'CLASES':
            self.assertFalse(FichaMatricula.objects.filter(estado='PENDIENTE').exists())
