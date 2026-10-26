# Periodos escolares

## Cierre de matrícula

Dirección utiliza el apartado rojo al final del dashboard. «Revisar y cerrar matrícula» muestra los requisitos y sus pendientes. El cierre requiere una segunda confirmación y vuelve a comprobar todos los requisitos en el servidor.

Se exige:

- Secciones activas con docentes encargados activos.
- Ninguna solicitud del año activo pendiente o por subsanar.
- Fichas aprobadas con matrícula activa coincidente, sin duplicados ni exceso de cupo.
- Alumnos activos de las secciones con matrícula del año activo.
- Materias del nivel con distribución válida, bloques autorizados y el número de clases publicadas configurado para cada materia.
- Especialidad compatible en tercer ciclo y ausencia de titularidad de básica en el mismo turno.

El cierre conserva el año lectivo, matrículas, encargados, horarios y bloques. Cambia la fase a clases y registra la fecha, la cuenta de Dirección y los requisitos verificados. Dos confirmaciones simultáneas no producen dos cierres.

El indicador superior del periodo es informativo. La ruta anterior de alternancia aplica las mismas comprobaciones y no permite iniciar otro año.

## Operaciones por fase

| Operación | Matrícula | Clases |
| --- | --- | --- |
| Enviar, corregir o revisar solicitudes del año activo | Permitida | Cerrada |
| Registrar alumnos y su matrícula anual | Permitida | Cerrada |
| Distribuir docentes, grados, materias y bloques | Permitida | Solo consulta |
| Elaborar, revisar y publicar horarios | Permitida; publicados de solo lectura | Solo consulta |
| Registrar conducta | Cerrada | Permitida con matrícula activa y fecha del año activo |
| Consultar fichas, expedientes e historial | Según rol y sección | Según rol y sección |

El servidor verifica los permisos aunque la petición proceda de una pestaña abierta antes del cambio. Las escrituras de estos flujos se coordinan con el cierre mediante el bloqueo de la configuración institucional.

## Subsanación

El docente indica el motivo. El responsable accede a «Corregir solicitud» en su panel, modifica su propia ficha y la reenvía. Se conserva la misma ficha y NIE, con historial de las decisiones y los datos anteriores. La ficha vuelve a pendiente y puede revisarla el docente de la sección solicitada. Los comprobantes siguen siendo de solo lectura.

## Instalación y pruebas

Aplicar `python manage.py migrate` para crear el historial de cierres y revisiones. No es necesario recargar datos demo. Los registros existentes no se eliminan ni se completan automáticamente para forzar un cierre.

Ejecutar `python manage.py test Directora.test_periodos Maestros.tests.ControlAlumnosMatriculaTests Responsable.tests.FichaMatriculaResponsableTests`.

El cierre de clases, la apertura del siguiente año y las reglas de promoción o repetición corresponden a una segunda entrega. La progresión no se deduce de una matrícula sin resultado académico confirmado.
