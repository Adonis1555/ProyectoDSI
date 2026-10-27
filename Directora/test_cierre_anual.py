import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

from django.db import close_old_connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from Login.models import Usuario
from Maestros.models import Alumno, HorarioClase, RegistroTarjeta
from Responsable.models import FichaMatricula, Matricula, Responsable
from .models import AsignacionBloqueMaestro, AsignacionMateria, CierrePeriodo, ConfiguracionPeriodo, GradoSeccion, Maestro
from .test_periodos import EscenarioPeriodo
from .views import cerrar_clases, eliminar_grado_seccion


class EscenarioCierreAnual(EscenarioPeriodo):
    def iniciar_clases(self):
        self.preparar()
        self.assertEqual(self.cerrar().status_code, 200)
        self.periodo.refresh_from_db()

    def cerrar_anio(self, **cambios):
        datos = {'anio_activo': '2028', 'confirmacion': 'CERRAR CLASES'}
        datos.update(cambios)
        return self.client.post(reverse('cerrar_clases'), datos)


class CierreAnualTests(EscenarioCierreAnual, TestCase):
    def setUp(self):
        self.iniciar_clases()

    def test_revision_solo_consulta_y_no_exige_resultados_academicos(self):
        respuesta = self.client.get(reverse('revision_cierre_clases'))
        self.assertTrue(respuesta.json()['puede_cerrar'])
        self.assertEqual(respuesta.json()['anio_siguiente'], 2029)
        self.periodo.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('CLASES', 2028))
        self.assertEqual(CierrePeriodo.objects.count(), 1)

    def test_cierre_archiva_y_abre_sin_promover_ni_borrar_registros(self):
        AsignacionMateria.objects.create(grado_seccion=self.seccion, materia=self.materia, docente=self.maestro, anio_lectivo=2028)
        RegistroTarjeta.objects.create(alumno=self.alumno, fecha=date(2028, 5, 2), tipo='D', sub_letra='A', maestro_registra=self.usuario_maestro)
        respuesta = self.cerrar_anio()
        self.assertEqual(respuesta.status_code, 200)
        self.periodo.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('MATRICULA', 2029))
        cierre = CierrePeriodo.objects.get(anio_lectivo=2028, fase_cerrada='CLASES')
        self.assertEqual(cierre.realizado_por, self.directora)
        self.assertEqual(cierre.fase_abierta, 'MATRICULA')
        archivo = cierre.resumen['archivo']
        self.assertEqual(archivo['secciones'][0]['maestro_encargado_id'], self.maestro.pk)
        self.assertEqual(archivo['bloques'][0]['activo'], True)
        self.assertEqual(archivo['conducta'][0]['tipo'], 'D')
        self.seccion.refresh_from_db()
        self.bloque.refresh_from_db()
        self.alumno.refresh_from_db()
        self.assertIsNone(self.seccion.maestro_encargado)
        self.assertFalse(self.bloque.activo)
        self.assertEqual(self.alumno.grado_seccion, self.seccion)
        self.assertTrue(self.alumno.activo)
        self.assertEqual(Matricula.objects.get(alumno=self.alumno, anio_lectivo=2028).estado, 'ACTIVO')
        self.assertEqual(HorarioClase.objects.get(pk=self.clase.pk).estado, 'PUBLICADO')
        self.assertEqual(AsignacionMateria.objects.count(), 1)
        self.assertEqual(FichaMatricula.objects.count(), 1)
        self.assertEqual(RegistroTarjeta.objects.count(), 1)
        self.assertFalse(Matricula.objects.filter(anio_lectivo=2029).exists())
        self.assertFalse(HorarioClase.objects.filter(anio_lectivo=2029).exists())

    def test_bloquea_ano_sin_inicio_clases_registrado(self):
        CierrePeriodo.objects.all().delete()
        self.assertEqual(self.cerrar_anio().status_code, 409)

    def test_limite_del_calendario_se_informa_como_requisito_pendiente(self):
        self.periodo.anio_activo = 9999
        self.periodo.save()
        respuesta = self.client.get(reverse('revision_cierre_clases'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['puede_cerrar'])

    def test_bloquea_solicitudes_o_matriculas_inconsistentes(self):
        pendiente = self.crear_ficha('20280002')
        self.assertEqual(self.cerrar_anio().status_code, 409)
        pendiente.delete()
        Matricula.objects.all().delete()
        self.assertEqual(self.cerrar_anio().status_code, 409)

    def test_bloquea_y_conserva_cualquier_dato_del_ano_entrante(self):
        casos = [
            (Matricula, {'alumno': self.alumno, 'grado_seccion': self.seccion}),
            (AsignacionMateria, {'grado_seccion': self.seccion, 'materia': self.materia, 'docente': self.maestro}),
            (AsignacionBloqueMaestro, {'maestro': self.maestro, 'dia': 1, 'bloque': 1, 'turno': 'Mañana'}),
            (HorarioClase, {'docente': self.maestro, 'grado_seccion': self.seccion, 'materia': self.materia, 'dia': 1, 'bloque': 1}),
            (CierrePeriodo, {'fase_cerrada': 'MATRICULA', 'fase_abierta': 'CLASES', 'realizado_por': self.directora}),
        ]
        for modelo, datos in casos:
            with self.subTest(modelo=modelo.__name__):
                existente = modelo.objects.create(anio_lectivo=2029, **datos)
                self.assertEqual(self.cerrar_anio().status_code, 409)
                self.assertTrue(modelo.objects.filter(pk=existente.pk).exists())
                existente.delete()
        ficha = self.crear_ficha('20280002')
        ficha.anio_lectivo = 2029
        ficha.save()
        self.assertEqual(self.cerrar_anio().status_code, 409)
        ficha.refresh_from_db()
        self.assertEqual(ficha.anio_lectivo, 2029)
        ficha.delete()
        conducta = RegistroTarjeta.objects.create(alumno=self.alumno, fecha=date(2029, 1, 1), tipo='D', sub_letra='A')
        self.assertEqual(self.cerrar_anio().status_code, 409)
        self.assertTrue(RegistroTarjeta.objects.filter(pk=conducta.pk).exists())

    def test_revalida_despues_de_la_revision(self):
        self.assertTrue(self.client.get(reverse('revision_cierre_clases')).json()['puede_cerrar'])
        self.crear_ficha('20280002')
        self.assertEqual(self.cerrar_anio().status_code, 409)

    def test_requiere_direccion_post_anio_y_confirmacion(self):
        self.assertEqual(self.client.get(reverse('cerrar_clases')).status_code, 405)
        self.assertEqual(self.cerrar_anio(confirmacion='').status_code, 400)
        self.assertEqual(self.cerrar_anio(anio_activo='2027').status_code, 400)
        for usuario in (self.usuario_maestro, self.usuario_responsable):
            self.client.force_login(usuario)
            self.assertEqual(self.cerrar_anio().status_code, 403)
            self.assertEqual(self.client.get(reverse('revision_cierre_clases')).status_code, 403)

    def test_proteccion_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.directora)
        respuesta = cliente.post(reverse('cerrar_clases'), {'anio_activo': '2028', 'confirmacion': 'CERRAR CLASES'})
        self.assertEqual(respuesta.status_code, 403)

    def test_doble_click_no_incrementa_dos_veces_y_la_ruta_antigua_no_lo_elude(self):
        self.assertEqual(self.cerrar_anio().status_code, 200)
        self.assertEqual(self.cerrar_anio().status_code, 409)
        self.client.post(reverse('alternar_periodo'), {'anio_activo': '2028', 'confirmacion': 'CERRAR MATRICULA'})
        self.periodo.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('MATRICULA', 2029))
        self.assertEqual(CierrePeriodo.objects.filter(fase_cerrada='CLASES').count(), 1)

    def test_error_revierte_archivo_desasignacion_y_periodo(self):
        with patch.object(ConfiguracionPeriodo, 'save', side_effect=RuntimeError('Fallo simulado')):
            with self.assertRaises(RuntimeError):
                self.cerrar_anio()
        self.periodo.refresh_from_db()
        self.seccion.refresh_from_db()
        self.bloque.refresh_from_db()
        self.assertEqual((self.periodo.fase_actual, self.periodo.anio_activo), ('CLASES', 2028))
        self.assertEqual(self.seccion.maestro_encargado, self.maestro)
        self.assertTrue(self.bloque.activo)
        self.assertFalse(CierrePeriodo.objects.filter(fase_cerrada='CLASES').exists())

    def test_nuevo_ciclo_no_muestra_alumnos_anteriores_como_inscritos(self):
        self.cerrar_anio()
        self.seccion.maestro_encargado = self.maestro
        self.seccion.save()
        self.client.force_login(self.usuario_maestro)
        self.assertNotContains(self.client.get(reverse('control_alumnos'), {'vista': 'registrados'}), 'Alumno Matriculado')
        self.assertNotContains(self.client.get(reverse('control_alumnos'), {'vista': 'solicitudes'}), 'Alumno Solicitud')
        self.client.force_login(self.directora)
        dashboard = self.client.get(reverse('dashboard_directora'))
        self.assertEqual(dashboard.context['total_alumnos'], 0)
        self.assertEqual(self.client.post(reverse('guardar_bloques_maestro'), json.dumps({'anio_lectivo': 2028}), content_type='application/json').status_code, 409)
        revision = self.client.get(reverse('revision_cierre_matricula')).json()
        matriculas = next(r for r in revision['requisitos'] if r['codigo'] == 'matriculas')
        self.assertTrue(matriculas['cumplido'])

    def test_nuevo_ciclo_permite_solicitudes_y_aceptaciones_nuevas_sin_alterar_el_anterior(self):
        self.cerrar_anio()
        self.seccion.maestro_encargado = self.maestro
        self.seccion.save()
        self.client.force_login(self.usuario_responsable)
        datos = self.datos_envio()
        datos.update(anio_activo='2029', nie='20290002')
        respuesta = self.client.post(reverse('ficha_matricula'), datos)
        self.assertTrue(respuesta.json()['ok'])
        ficha = FichaMatricula.objects.get(nie='20290002')
        self.assertEqual(ficha.anio_lectivo, 2029)
        self.client.force_login(self.usuario_maestro)
        self.client.post(reverse('resolver_solicitud_matricula', args=[ficha.pk]), {'accion': 'aceptar'})
        self.assertTrue(Matricula.objects.filter(alumno_id='20290002', anio_lectivo=2029).exists())
        self.assertEqual(Matricula.objects.get(alumno=self.alumno, anio_lectivo=2028).estado, 'ACTIVO')
        listado = self.client.get(reverse('control_alumnos'), {'vista': 'registrados'})
        self.assertContains(listado, 'Alumno Corregido')
        self.assertNotContains(listado, 'Alumno Matriculado')
        respuesta = self.client.post(reverse('registrar_demerito', args=['20290002']), json.dumps({'tipo_registro': 'D', 'escala': 'A', 'fecha': '2029-03-01'}), content_type='application/json')
        self.assertEqual(respuesta.status_code, 403)

    def test_ano_nuevo_no_deduce_promocion_de_una_matricula_anterior(self):
        self.cerrar_anio()
        self.client.force_login(self.usuario_responsable)
        datos = self.datos_envio()
        datos.update(anio_activo='2029', nie=self.alumno.NIE, grado_solicitado='4G')
        self.assertEqual(self.client.post(reverse('ficha_matricula'), datos).status_code, 400)
        self.assertFalse(Matricula.objects.filter(alumno=self.alumno, anio_lectivo=2029).exists())


class ArchivoAnualTests(EscenarioCierreAnual, TestCase):
    def setUp(self):
        self.iniciar_clases()
        self.ficha.direccion_exacta = 'Dirección original del año'
        self.ficha.save()
        RegistroTarjeta.objects.create(alumno=self.alumno, fecha=date(2028, 6, 1), tipo='RC', sub_letra='A')
        self.assertEqual(self.cerrar_anio().status_code, 200)

    def test_archivo_no_cambia_si_cambian_seccion_docente_materia_o_alumno(self):
        self.seccion.grado = '4G'
        self.seccion.seccion = 'D'
        self.seccion.turno = 'Tarde'
        self.seccion.save()
        self.materia.nombre = 'Materia renombrada'
        self.materia.save()
        self.alumno.nombre = 'Nombre actualizado'
        self.alumno.save()
        self.ficha.direccion_exacta = 'Dirección posterior'
        self.ficha.save()
        respuesta = self.client.get(reverse('archivo_anual', args=[2028]))
        self.assertContains(respuesta, '3° Grado - Sección A')
        self.assertContains(respuesta, 'Matemática')
        self.assertContains(respuesta, 'Alumno Matriculado')
        self.assertContains(respuesta, 'Luis Docente')
        self.assertNotContains(respuesta, 'Materia renombrada')
        self.assertNotContains(respuesta, 'Nombre actualizado')
        detalle = self.client.get(reverse('ficha_archivada', args=[2028, self.ficha.pk]))
        self.assertContains(detalle, 'Dirección original del año')
        self.assertNotContains(detalle, 'Dirección posterior')
        self.assertNotContains(detalle, 'Aceptar solicitud')

    def test_docente_original_y_responsable_conservan_consulta_y_comprobantes(self):
        for usuario in (self.usuario_maestro, self.usuario_responsable):
            self.client.force_login(usuario)
            self.assertContains(self.client.get(reverse('historial_anual')), 'Año lectivo 2028')
            self.assertContains(self.client.get(reverse('archivo_anual', args=[2028])), 'Alumno Matriculado')
            self.assertContains(self.client.get(reverse('ficha_archivada', args=[2028, self.ficha.pk])), 'Dirección original del año')
        self.client.force_login(self.usuario_maestro)
        self.assertRedirects(self.client.get(reverse('solicitud_matricula_detalle', args=[self.ficha.pk])), reverse('ficha_archivada', args=[2028, self.ficha.pk]))
        self.client.force_login(self.usuario_responsable)
        self.assertRedirects(self.client.get(reverse('comprobante_ficha', args=[self.ficha.pk])), reverse('ficha_archivada', args=[2028, self.ficha.pk]))

    def test_docente_nuevo_de_la_misma_seccion_no_hereda_fichas_antiguas(self):
        usuario = Usuario.objects.create_user(email='nuevo@anual.test', nombre='Nuevo', apellido='Docente', rol='maestro')
        docente = Maestro.objects.create(dui='44444444-4', nombre='Nuevo', apellido='Docente', especialidad='Matemática', telefono='70000004', id_usuario=usuario)
        self.seccion.maestro_encargado = docente
        self.seccion.save()
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('archivo_anual', args=[2028])).status_code, 404)
        self.assertEqual(self.client.get(reverse('ficha_archivada', args=[2028, self.ficha.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('solicitud_matricula_detalle', args=[self.ficha.pk])).status_code, 404)

    def test_responsable_ajeno_no_accede_al_archivo(self):
        usuario = Usuario.objects.create_user(email='ajeno@anual.test', nombre='Otro', apellido='Responsable', rol='responsable')
        Responsable.objects.create(dui='55555555-5', nombre='Otro', apellido='Responsable', telefono='70000005', id_usuario=usuario)
        self.client.force_login(usuario)
        self.assertNotContains(self.client.get(reverse('historial_anual')), 'Año lectivo 2028')
        self.assertEqual(self.client.get(reverse('archivo_anual', args=[2028])).status_code, 404)
        self.assertEqual(self.client.get(reverse('ficha_archivada', args=[2028, self.ficha.pk])).status_code, 404)

    def test_archivos_son_solo_lectura_incluso_con_post_directo(self):
        for ruta, args in [('historial_anual', []), ('archivo_anual', [2028]), ('ficha_archivada', [2028, self.ficha.pk])]:
            self.assertEqual(self.client.post(reverse(ruta, args=args), {'estado': 'APROBADA'}).status_code, 405)
        solicitud = RequestFactory().post('/seccion/eliminar/')
        solicitud.user = self.directora
        self.assertEqual(eliminar_grado_seccion(solicitud, self.seccion.pk).status_code, 400)
        self.assertEqual(FichaMatricula.objects.get(pk=self.ficha.pk).estado, 'APROBADA')

    def test_consolidado_y_exportacion_historicos_usan_los_datos_conservados(self):
        self.seccion.grado = '4G'
        self.seccion.seccion = 'D'
        self.seccion.save()
        self.alumno.sexo = 'F'
        self.alumno.save()
        respuesta = self.client.get(reverse('control_demerito_directora'), {'anio': 2028, 'mes': 6})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['totales_globales']['mat_h'], 1)
        self.assertEqual(respuesta.context['totales_globales']['mat_m'], 0)
        self.assertEqual(respuesta.context['totales_globales']['rc_total'], 1)
        self.assertContains(respuesta, '3° Grado')
        exportacion = self.client.get(reverse('exportar_excel_conducta'), {'anio': 2028, 'mes': 6})
        self.assertEqual(exportacion.status_code, 200)
        self.assertIn('3° Grado', exportacion.content.decode())


class PrivacidadArchivoAnualTests(EscenarioCierreAnual, TestCase):
    def setUp(self):
        self.iniciar_clases()
        self.otro_usuario = Usuario.objects.create_user(email='otro@privacidad.test', nombre='Otro', apellido='Docente', rol='maestro')
        otro_docente = Maestro.objects.create(dui='66666666-6', nombre='Otro', apellido='Docente', especialidad='Matemática', telefono='70000006', id_usuario=self.otro_usuario)
        otra_seccion = GradoSeccion.objects.create(grado='4G', seccion='B', turno='Tarde', cupo_maximo=10, maestro_encargado=otro_docente)
        otro_usuario_responsable = Usuario.objects.create_user(email='otro-resp@privacidad.test', nombre='Otra', apellido='Responsable', rol='responsable')
        otro_responsable = Responsable.objects.create(dui='77777777-7', nombre='Otra', apellido='Responsable', telefono='70000007', id_usuario=otro_usuario_responsable)
        otro_alumno = Alumno.objects.create(NIE='20280003', nombre='Estudiante', apellido='Reservado', fecha_nac=date(2017, 1, 1), sexo='F', grado_seccion=otra_seccion)
        Matricula.objects.create(alumno=otro_alumno, grado_seccion=otra_seccion, anio_lectivo=2028)
        self.otra_ficha = FichaMatricula.objects.create(
            responsable=otro_responsable, grado_seccion=otra_seccion, anio_lectivo=2028, nie=otro_alumno.NIE,
            nombres='Estudiante', apellidos='Reservado', fecha_nacimiento=date(2017, 1, 1), genero='F',
            parentesco_responsable='Madre', telefono_contacto='70000007', estado='APROBADA', tiene_problemas_salud=True, detalle_salud='Dato reservado de salud',
        )
        RegistroTarjeta.objects.create(alumno=otro_alumno, fecha=date(2028, 5, 1), tipo='D', sub_letra='B')
        self.assertEqual(self.cerrar_anio().status_code, 200)

    def test_docente_y_responsable_solo_ven_su_parte_del_mismo_archivo(self):
        for usuario in (self.usuario_maestro, self.usuario_responsable):
            self.client.force_login(usuario)
            respuesta = self.client.get(reverse('archivo_anual', args=[2028]))
            self.assertContains(respuesta, 'Alumno Matriculado')
            self.assertNotContains(respuesta, 'Estudiante Reservado')
            self.assertNotContains(respuesta, 'Dato reservado de salud')
            self.assertEqual(self.client.get(reverse('ficha_archivada', args=[2028, self.otra_ficha.pk])).status_code, 404)

    def test_direccion_puede_consultar_el_archivo_completo(self):
        respuesta = self.client.get(reverse('archivo_anual', args=[2028]))
        self.assertContains(respuesta, 'Alumno Matriculado')
        self.assertContains(respuesta, 'Estudiante Reservado')
        self.assertContains(self.client.get(reverse('ficha_archivada', args=[2028, self.otra_ficha.pk])), 'Dato reservado de salud')


class CierreAnualConcurrenteTests(EscenarioCierreAnual, TransactionTestCase):
    def setUp(self):
        self.iniciar_clases()

    def test_confirmaciones_simultaneas_archivan_y_avanzan_una_sola_vez(self):
        def confirmar(_):
            close_old_connections()
            try:
                solicitud = RequestFactory().post('/directora/periodo/cerrar-clases/', {'anio_activo': '2028', 'confirmacion': 'CERRAR CLASES'})
                solicitud.user = Usuario.objects.get(pk=self.directora.pk)
                return cerrar_clases(solicitud).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(confirmar, range(2)))
        self.assertEqual(sorted(resultados), [200, 409])
        self.assertEqual(CierrePeriodo.objects.filter(fase_cerrada='CLASES').count(), 1)
        self.periodo.refresh_from_db()
        self.assertEqual(self.periodo.anio_activo, 2029)

    def test_conducta_simultanea_queda_archivada_o_es_rechazada(self):
        cliente_docente = Client()
        cliente_docente.force_login(self.usuario_maestro)

        def cerrar():
            close_old_connections()
            try:
                return self.cerrar_anio().status_code
            finally:
                close_old_connections()

        def registrar():
            close_old_connections()
            try:
                return cliente_docente.post(reverse('registrar_demerito', args=[self.alumno.pk]), json.dumps({'tipo_registro': 'D', 'escala': 'A', 'fecha': '2028-08-01'}), content_type='application/json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            cierre = pool.submit(cerrar)
            conducta = pool.submit(registrar)
            self.assertEqual(cierre.result(), 200)
            self.assertIn(conducta.result(), [200, 403])
        archivo = CierrePeriodo.objects.get(fase_cerrada='CLASES').resumen['archivo']
        self.assertEqual(len(archivo['conducta']), RegistroTarjeta.objects.count())
