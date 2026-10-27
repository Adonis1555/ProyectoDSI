# Periodos escolares

## Cierre de matrícula

Dirección utiliza el apartado rojo al final del dashboard. «Revisar y cerrar matrícula» muestra los requisitos y sus pendientes. El cierre requiere una segunda confirmación y vuelve a comprobar todos los requisitos en el servidor.

Se exige:

- Secciones activas con docentes encargados activos.
- Ninguna solicitud del año activo pendiente o por subsanar.
- Fichas aprobadas con matrícula activa coincidente, sin duplicados ni exceso de cupo.
- Alumnos activos de las secciones con matrícula del año activo.
- Materias del nivel con distribución válida, bloques autorizados y el número de clases publicadas configurado para cada materia.
- Asignación académica expresa en tercer ciclo y ausencia de titularidad de básica en el mismo turno.

Por la disponibilidad de personal del centro escolar, Dirección puede asignar una materia a un docente de otra especialidad. La especialidad del perfil es informativa y no impide programar ni cerrar el periodo cuando la asignación y los demás requisitos son válidos. La pantalla de distribución conserva su confirmación para esas asignaciones.

El cierre conserva el año lectivo, matrículas, encargados, horarios y bloques. Cambia la fase a clases y registra la fecha, la cuenta de Dirección y los requisitos verificados. Dos confirmaciones simultáneas no producen dos cierres.

El indicador superior del periodo es informativo. La ruta anterior de alternancia aplica las mismas comprobaciones del cierre de matrícula y no permite eludir la confirmación del cierre anual.

## Cierre de clases y apertura del siguiente año

Dirección utiliza «Revisar y cerrar clases» en el mismo apartado rojo. Se verifica que exista el cierre de matrícula que inició las clases, que no queden solicitudes por resolver, que las fichas aprobadas tengan matrícula coincidente y que el año siguiente no contenga registros previos que puedan sobrescribirse.

Al confirmar el cierre:

- Se guarda una copia del año completo dentro del registro de cierre: secciones y encargados, alumnos y matrículas, fichas y revisiones, distribución de materias, bloques, horarios y conducta.
- Se conservan los registros originales y se desactivan los bloques del año saliente.
- Se liberan los encargados actuales de las secciones para realizar una nueva distribución. La asignación anterior permanece en el archivo de su año.
- Se incrementa el año en uno y se abre matrícula. Las nuevas matrículas, materias distribuidas, bloques y horarios se preparan expresamente para el nuevo año.
- Los estudiantes anteriores no aparecen como inscritos en el año nuevo hasta que tengan matrícula de ese año.

El cierre no asigna promociones, repeticiones, retiros ni graduaciones y no crea matrículas automáticamente. Las reglas para determinar el grado del siguiente año quedan pendientes de definición; la continuidad de un alumno existente requiere un resultado académico confirmado.

El archivo y el cambio de año se realizan en una única transacción. Un error revierte todas las operaciones; una confirmación repetida no vuelve a incrementar el año.

## Consulta del historial

«Consultar historial de años cerrados» está disponible en el dashboard de Dirección y en los paneles de alumnos del maestro y del responsable. Las pantallas son de solo lectura y usan los valores conservados al cierre, aunque después se cambie el nombre de un estudiante, materia, docente o sección.

Dirección consulta el año completo. El docente consulta las secciones que tenía a cargo y sus horarios de ese año. El responsable consulta sus fichas, estudiantes asociados y horarios correspondientes. Un nuevo encargado no hereda acceso a las fichas de años anteriores por recibir la misma sección.

Las fichas archivadas permiten consultar todos sus datos e imprimirlos. Las decisiones de aceptación y subsanación permanecen cerradas para esos años.

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

Ejecutar `python manage.py test Directora.test_cierre_anual Directora.test_periodos Maestros.tests.ControlAlumnosMatriculaTests Responsable.tests.FichaMatriculaResponsableTests`.

La segunda entrega utiliza el campo de archivo del historial de cierres existente y no necesita nuevas tablas ni migraciones. No se ejecutan cierres ni se cambian datos demo al instalar el código.
