import json
from functools import wraps

from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse

from .models import (
    AsignacionBloqueMaestro, AsignacionMateria, ConfiguracionPeriodo,
    GradoSeccion, Materia, especialidad_coincide_con_materia, normalizar_turno,
)


def periodo_requerido(fase):
    """Serializa las escrituras con el cierre y verifica fase y año en el servidor."""
    def decorador(vista):
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            if request.method != 'POST':
                return vista(request, *args, **kwargs)
            ConfiguracionPeriodo.get_solo()
            with transaction.atomic():
                periodo = ConfiguracionPeriodo.objects.select_for_update().get(pk=1)
                if periodo.fase_actual != fase:
                    return JsonResponse({
                        'ok': False, 'success': False,
                        'error': 'Esta operación no está disponible durante el periodo activo.',
                    }, status=403)
                datos = request.POST
                if request.content_type == 'application/json':
                    try:
                        datos = json.loads(request.body)
                    except (ValueError, UnicodeDecodeError):
                        return JsonResponse({'ok': False, 'success': False, 'error': 'Solicitud inválida.'}, status=400)
                    if not isinstance(datos, dict):
                        return JsonResponse({'ok': False, 'success': False, 'error': 'Solicitud inválida.'}, status=400)
                for campo in ('anio_lectivo', 'anio_activo'):
                    if campo in datos and str(datos[campo]) != str(periodo.anio_activo):
                        return JsonResponse({
                            'ok': False, 'success': False,
                            'error': 'El año lectivo cambió. Actualiza la pantalla antes de continuar.',
                        }, status=409)
                request.periodo = periodo
                return vista(request, *args, **kwargs)
        return protegida
    return decorador


def revisar_cierre_matricula(periodo):
    from Maestros.models import HorarioClase
    from Responsable.models import FichaMatricula, Matricula

    anio = periodo.anio_activo
    requisitos = []

    def agregar(codigo, titulo, problemas, ruta):
        requisitos.append({
            'codigo': codigo, 'titulo': titulo, 'cumplido': not problemas,
            'problemas': problemas, 'url': reverse(ruta),
        })

    secciones = list(GradoSeccion.objects.filter(activo=True).select_related('maestro_encargado__id_usuario'))
    problemas = [] if secciones else ['No existen secciones activas.']
    for seccion in secciones:
        docente = seccion.maestro_encargado
        if not docente or not docente.activo or not docente.id_usuario.is_active or not docente.id_usuario.activo:
            problemas.append(f'{seccion}: necesita un docente encargado activo.')
    agregar('secciones', 'Secciones y docentes encargados', problemas, 'grado_seccion_control')

    fichas = FichaMatricula.objects.filter(anio_lectivo=anio)
    pendientes = fichas.filter(estado__in=['PENDIENTE', 'RECHAZADA']).count()
    agregar('solicitudes', 'Solicitudes revisadas y subsanadas',
            [f'Hay {pendientes} solicitud(es) pendiente(s) o por subsanar.'] if pendientes else [], 'grado_seccion_control')

    problemas = []
    matriculas = list(Matricula.objects.filter(anio_lectivo=anio, estado='ACTIVO').select_related('grado_seccion', 'alumno'))
    for duplicada in fichas.filter(estado='APROBADA').values('nie').annotate(total=Count('pk')).filter(total__gt=1):
        problemas.append(f'NIE {duplicada["nie"]}: hay más de una ficha aprobada para este año.')
    for matricula in matriculas:
        if not matricula.grado_seccion.activo or not matricula.alumno.activo or matricula.alumno.grado_seccion_id != matricula.grado_seccion_id:
            problemas.append(f'NIE {matricula.alumno_id}: matrícula y sección actual inconsistentes.')
    for ficha in fichas.filter(estado='APROBADA'):
        if not any(m.alumno_id == ficha.nie and m.grado_seccion_id == ficha.grado_seccion_id for m in matriculas):
            problemas.append(f'NIE {ficha.nie}: la ficha aprobada no tiene matrícula activa coincidente.')
    for seccion in secciones:
        ocupados = sum(m.grado_seccion_id == seccion.id for m in matriculas)
        if ocupados > seccion.cupo_maximo:
            problemas.append(f'{seccion}: {ocupados} matrículas exceden el cupo de {seccion.cupo_maximo}.')
        sin_matricula = seccion.alumnos.filter(activo=True).exclude(NIE__in=[m.alumno_id for m in matriculas])
        if sin_matricula.exists():
            problemas.append(f'{seccion}: {sin_matricula.count()} alumno(s) activo(s) sin matrícula del año {anio}.')
    agregar('matriculas', 'Matrículas, secciones y cupos', problemas, 'grado_seccion_control')

    problemas = []
    materias = list(Materia.objects.all())
    combinaciones_validas = set()
    for seccion in secciones:
        niveles = ['PARVULARIA'] if seccion.grado in ['PK', 'PK5', 'PK6'] else (
            ['TERCER', 'BASICA_Y_TERCER'] if seccion.es_tercer_ciclo else ['BASICA', 'BASICA_Y_TERCER'])
        esperadas = [m for m in materias if m.nivel_aplicable in niveles]
        if not esperadas:
            problemas.append(f'{seccion}: no hay materias configuradas para su nivel.')
        for materia in esperadas:
            docente = seccion.maestro_encargado
            if seccion.es_tercer_ciclo:
                asignacion = AsignacionMateria.objects.filter(
                    grado_seccion=seccion, materia=materia, anio_lectivo=anio,
                ).select_related('docente__id_usuario').first()
                docente = asignacion.docente if asignacion else None
                if docente and not especialidad_coincide_con_materia(docente, materia):
                    problemas.append(f'{seccion} / {materia.nombre}: especialidad incompatible.')
                if docente and any(not s.es_tercer_ciclo and normalizar_turno(s.turno) == normalizar_turno(seccion.turno)
                                   for s in docente.grados_a_cargo.filter(activo=True)):
                    problemas.append(f'{seccion} / {materia.nombre}: el docente es titular de básica en el mismo turno.')
            if not docente or not docente.activo or not docente.id_usuario.is_active or not docente.id_usuario.activo:
                problemas.append(f'{seccion} / {materia.nombre}: falta docente válido para la materia.')
                continue
            combinaciones_validas.add((seccion.pk, materia.pk, docente.pk))
            clases = list(HorarioClase.objects.filter(
                grado_seccion=seccion, materia=materia, anio_lectivo=anio,
            ))
            if len(clases) != materia.bloques_semanales or any(
                c.estado != 'PUBLICADO' or c.docente_id != docente.pk or
                c.turno != normalizar_turno(seccion.turno) for c in clases
            ):
                problemas.append(f'{seccion} / {materia.nombre}: requiere {materia.bloques_semanales} bloques publicados con el docente asignado.')
            for clase in clases:
                if not AsignacionBloqueMaestro.objects.filter(
                    maestro_id=clase.docente_id, anio_lectivo=anio, activo=True,
                    dia=clase.dia, bloque=clase.bloque, turno=clase.turno,
                ).exists():
                    problemas.append(f'{seccion} / {materia.nombre}: hay bloques sin autorización docente vigente.')
    if HorarioClase.objects.filter(anio_lectivo=anio, grado_seccion__activo=True).exclude(estado='PUBLICADO').exists():
        problemas.append('Hay clases del año activo que todavía no están publicadas.')
    for clase in HorarioClase.objects.filter(anio_lectivo=anio, grado_seccion__activo=True).select_related('grado_seccion', 'materia'):
        if (clase.grado_seccion_id, clase.materia_id, clase.docente_id) not in combinaciones_validas:
            problemas.append(f'{clase.grado_seccion} / {clase.materia.nombre}: clase fuera de la distribución válida.')
    agregar('planificacion', 'Distribución académica y horarios publicados', problemas, 'horarios_revision')
    return {
        'anio_activo': anio, 'fase_actual': periodo.fase_actual,
        'puede_cerrar': periodo.fase_actual == 'MATRICULA' and all(r['cumplido'] for r in requisitos),
        'requisitos': requisitos,
    }
