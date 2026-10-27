import json
from types import SimpleNamespace

from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.utils.dateparse import parse_date, parse_datetime

from .models import AsignacionBloqueMaestro, AsignacionMateria, CierrePeriodo, GradoSeccion, Maestro, Materia


def construir_archivo_anual(anio):
    """Copia los datos del año antes de liberar la planificación del siguiente."""
    from Maestros.models import Alumno, HorarioClase, RegistroTarjeta
    from Responsable.models import FichaMatricula, Matricula, Responsable, RevisionFicha

    fichas = FichaMatricula.objects.filter(anio_lectivo=anio)
    matriculas = Matricula.objects.filter(anio_lectivo=anio)
    alumnos = Alumno.objects.filter(NIE__in=matriculas.values('alumno_id'))
    archivo = {
        'version': 1,
        'anio_lectivo': anio,
        'secciones': list(GradoSeccion.objects.order_by('grado', 'seccion').values()),
        'docentes': list(Maestro.objects.values('dui', 'nombre', 'apellido', 'especialidad', 'id_usuario_id')),
        'materias': list(Materia.objects.values()),
        'asignaciones': list(AsignacionMateria.objects.filter(anio_lectivo=anio).values()),
        'bloques': list(AsignacionBloqueMaestro.objects.filter(anio_lectivo=anio).values()),
        'horarios': list(HorarioClase.objects.filter(anio_lectivo=anio).order_by('dia', 'bloque').values()),
        'matriculas': list(matriculas.values()),
        'alumnos': list(alumnos.values()),
        'fichas': list(fichas.values()),
        'responsables': list(Responsable.objects.filter(pk__in=fichas.values('responsable_id')).values()),
        'revisiones': list(RevisionFicha.objects.filter(ficha__in=fichas).order_by('fecha', 'pk').values()),
        'conducta': list(RegistroTarjeta.objects.filter(fecha__year=anio, alumno__in=alumnos).order_by('fecha', 'pk').values()),
    }
    return json.loads(json.dumps(archivo, cls=DjangoJSONEncoder))


def cierre_anual(anio):
    return CierrePeriodo.objects.filter(anio_lectivo=anio, fase_cerrada='CLASES').first()


def filtrar_archivo(archivo, usuario):
    """Limita el historial con las relaciones guardadas al cerrar, no las actuales."""
    if usuario.es_directora():
        return archivo
    docentes = {d['dui']: d for d in archivo['docentes']}
    if usuario.es_maestro():
        docentes_propios = {d['dui'] for d in docentes.values() if d['id_usuario_id'] == usuario.pk}
        secciones_propias = {s['id'] for s in archivo['secciones'] if s['maestro_encargado_id'] in docentes_propios}
        horarios = [h for h in archivo['horarios'] if h['docente_id'] in docentes_propios]
        fichas = [f for f in archivo['fichas'] if f['grado_seccion_id'] in secciones_propias]
        matriculas = [m for m in archivo['matriculas'] if m['grado_seccion_id'] in secciones_propias]
        secciones_visibles = secciones_propias | {h['grado_seccion_id'] for h in horarios}
        bloques = [b for b in archivo['bloques'] if b['maestro_id'] in docentes_propios]
        asignaciones = [a for a in archivo['asignaciones'] if a['docente_id'] in docentes_propios]
        if not secciones_propias and not horarios:
            raise Http404
    elif usuario.es_responsable():
        responsables_propios = {r['dui'] for r in archivo['responsables'] if r['id_usuario_id'] == usuario.pk}
        fichas = [f for f in archivo['fichas'] if f['responsable_id'] in responsables_propios]
        if not fichas:
            raise Http404
        nies = {f['nie'] for f in fichas if f['estado'] == 'APROBADA'}
        matriculas = [m for m in archivo['matriculas'] if m['alumno_id'] in nies]
        secciones_visibles = {f['grado_seccion_id'] for f in fichas}
        horarios = [h for h in archivo['horarios'] if h['grado_seccion_id'] in {m['grado_seccion_id'] for m in matriculas}]
        bloques = []
        asignaciones = []
    else:
        raise Http404
    nies = {m['alumno_id'] for m in matriculas}
    responsables_visibles = {f['responsable_id'] for f in fichas}
    fichas_visibles = {f['id'] for f in fichas}
    return {
        **archivo,
        'secciones': [s for s in archivo['secciones'] if s['id'] in secciones_visibles],
        'docentes': [d for d in archivo['docentes'] if d['dui'] in (
            {h['docente_id'] for h in horarios} | {s['maestro_encargado_id'] for s in archivo['secciones'] if s['id'] in secciones_visibles}
        )],
        'materias': [m for m in archivo['materias'] if m['id'] in {h['materia_id'] for h in horarios}],
        'matriculas': matriculas,
        'alumnos': [a for a in archivo['alumnos'] if a['NIE'] in nies],
        'fichas': fichas,
        'responsables': [r for r in archivo['responsables'] if r['dui'] in responsables_visibles],
        'revisiones': [r for r in archivo['revisiones'] if r['ficha_id'] in fichas_visibles],
        'conducta': [r for r in archivo['conducta'] if r['alumno_id'] in nies],
        'horarios': horarios, 'bloques': bloques, 'asignaciones': asignaciones,
    }


def archivos_accesibles(usuario):
    archivos = []
    for cierre in CierrePeriodo.objects.filter(fase_cerrada='CLASES').order_by('-anio_lectivo'):
        archivo = cierre.resumen.get('archivo')
        if not archivo:
            continue
        try:
            filtrar_archivo(archivo, usuario)
        except Http404:
            continue
        archivos.append(cierre)
    return archivos


def alumnos_del_anio(seccion, anio):
    from django.db.models import Q
    from Maestros.models import Alumno

    filtro = Q(matriculas__anio_lectivo=anio, matriculas__estado='ACTIVO', matriculas__grado_seccion=seccion)
    if not CierrePeriodo.objects.filter(fase_cerrada='CLASES', anio_lectivo__lt=anio).exists():
        filtro |= Q(matriculas__isnull=True)
    return Alumno.objects.filter(filtro, activo=True, grado_seccion=seccion).distinct()


class SeccionArchivada(SimpleNamespace):
    def get_grado_display(self):
        return dict((codigo, nombre) for _, opciones in GradoSeccion.GRADOS_EL_SALVADOR for codigo, nombre in opciones).get(self.grado, self.grado)

    def __str__(self):
        return f'{self.get_grado_display()} - Sección {self.seccion}'


def contexto_archivo(archivo):
    from Maestros.models import HorarioClase, RegistroTarjeta
    from Responsable.models import Matricula
    secciones = {s['id']: SeccionArchivada(**s) for s in archivo['secciones']}
    docentes = {d['dui']: f'{d["nombre"]} {d["apellido"]}' for d in archivo['docentes']}
    alumnos = {a['NIE']: f'{a["nombre"]} {a["apellido"]}' for a in archivo['alumnos']}
    materias = {m['id']: m['nombre'] for m in archivo['materias']}
    for seccion in secciones.values():
        seccion.docente_nombre = docentes.get(seccion.maestro_encargado_id, 'Sin asignar')
    return {
        'secciones': list(secciones.values()),
        'matriculas': [{**m, 'nombre': alumnos.get(m['alumno_id'], m['alumno_id']), 'seccion': secciones[m['grado_seccion_id']], 'estado_nombre': dict(Matricula.ESTADOS).get(m['estado'], m['estado'])} for m in archivo['matriculas']],
        'fichas': [{**f, 'seccion': secciones[f['grado_seccion_id']]} for f in archivo['fichas']],
        'horarios': [{**h, 'seccion': secciones[h['grado_seccion_id']], 'materia': materias.get(h['materia_id'], 'Materia'), 'docente': docentes.get(h['docente_id'], 'Docente'), 'dia_nombre': dict(HorarioClase.DIAS_SEMANA).get(h['dia'], h['dia']), 'estado_nombre': dict(HorarioClase.ESTADOS).get(h['estado'], h['estado'])} for h in archivo['horarios']],
        'conducta': [{**r, 'nombre': alumnos.get(r['alumno_id'], r['alumno_id']), 'fecha': parse_date(r['fecha']), 'tipo_nombre': dict(RegistroTarjeta.TIPO_CASO_CHOICES).get(r['tipo'], r['tipo'])} for r in archivo['conducta']],
    }


def matriz_conducta_archivada(archivo, mes):
    claves = ['mat_m', 'mat_h', 'mat_total', 'd_m', 'd_h', 'd_total_sexo', 'd_a', 'd_b', 'd_c', 'd_d',
              'd_total_causal', 'r_m', 'r_h', 'r_total_sexo', 'r_a', 'r_b', 'r_c', 'r_total_opcion', 'rc_m', 'rc_h', 'rc_total']
    totales = dict.fromkeys(claves, 0)
    alumnos = {a['NIE']: a for a in archivo['alumnos']}
    matriz = []
    for seccion in archivo['secciones']:
        matriculas = [m for m in archivo['matriculas'] if m['grado_seccion_id'] == seccion['id']]
        if not seccion['activo'] and not matriculas:
            continue
        inscritos = [alumnos[m['alumno_id']] for m in matriculas if m['estado'] == 'ACTIVO']
        nies = {m['alumno_id'] for m in matriculas}
        registros = [r for r in archivo['conducta'] if r['alumno_id'] in nies and parse_date(r['fecha']).month == mes]
        fila = dict.fromkeys(claves, 0)
        fila['seccion_obj'] = SeccionArchivada(**seccion)
        fila['mat_m'] = sum(a['sexo'] == 'F' for a in inscritos)
        fila['mat_h'] = sum(a['sexo'] == 'M' for a in inscritos)
        fila['mat_total'] = len(inscritos)
        for prefijo, tipo in [('d', 'D'), ('r', 'R'), ('rc', 'RC')]:
            seleccionados = [r for r in registros if r['tipo'] == tipo]
            fila[f'{prefijo}_m'] = sum(alumnos[r['alumno_id']]['sexo'] == 'F' for r in seleccionados)
            fila[f'{prefijo}_h'] = sum(alumnos[r['alumno_id']]['sexo'] == 'M' for r in seleccionados)
            total = len(seleccionados)
            fila['rc_total' if prefijo == 'rc' else f'{prefijo}_total_sexo'] = total
            if prefijo != 'rc':
                for letra in ('a', 'b', 'c', 'd') if prefijo == 'd' else ('a', 'b', 'c'):
                    fila[f'{prefijo}_{letra}'] = sum(r['sub_letra'] == letra.upper() for r in seleccionados)
                fila['d_total_causal' if prefijo == 'd' else 'r_total_opcion'] = sum(
                    fila[f'{prefijo}_{letra}'] for letra in (('a', 'b', 'c', 'd') if prefijo == 'd' else ('a', 'b', 'c')))
        matriz.append(fila)
        for clave in claves:
            totales[clave] += fila[clave]
    return matriz, totales


def ficha_desde_archivo(archivo, ficha_id):
    from Responsable.models import FichaMatricula, RevisionFicha
    datos = next((f for f in archivo['fichas'] if f['id'] == ficha_id), None)
    if not datos:
        raise Http404
    ficha = SimpleNamespace(**datos)
    ficha.fecha_nacimiento = parse_date(ficha.fecha_nacimiento)
    ficha.fecha_envio = parse_datetime(ficha.fecha_envio)
    ficha.grado_seccion = SeccionArchivada(**next(s for s in archivo['secciones'] if s['id'] == ficha.grado_seccion_id))
    ficha.responsable = SimpleNamespace(**next(r for r in archivo['responsables'] if r['dui'] == ficha.responsable_id))
    ficha.get_estado_display = lambda: dict(FichaMatricula.ESTADOS).get(ficha.estado, ficha.estado)
    ficha.get_genero_display = lambda: {'M': 'Masculino', 'F': 'Femenino'}.get(ficha.genero, ficha.genero)
    revisiones = []
    for revision in archivo['revisiones']:
        if revision['ficha_id'] == ficha_id:
            revisiones.append(SimpleNamespace(
                fecha=parse_datetime(revision['fecha']), motivo=revision['motivo'],
                get_accion_display=dict(RevisionFicha._meta.get_field('accion').choices).get(revision['accion'], revision['accion']),
            ))
    ficha.revisiones = SimpleNamespace(all=lambda: revisiones)
    return ficha
