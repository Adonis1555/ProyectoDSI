# Datos de demostración

El proyecto utiliza PostgreSQL. `db.sqlite3` está vacío. Las migraciones crean las tablas y `cargar_datos_demo` agrega las cuentas y los registros usados para probar el sistema.

## Instalación en una base nueva

1. Instala las dependencias con `pip install -r requirements.txt` y crea la base PostgreSQL `ProyectoDSI`. Ajusta `DATABASES['default']['PASSWORD']` en tu copia local de `Cenalop_DSI/settings.py` según tu instalación; no subas ese cambio.
2. Ejecuta `python manage.py migrate`.
3. Ejecuta `python manage.py cargar_datos_demo --confirmar-demo`.
4. Inicia el sistema con `python manage.py runserver`.

El comando requiere `DEBUG=True` y una base sin registros de la aplicación. Si encuentra datos, se detiene sin borrarlos. No uses `seed_data.py` para esta carga: elimina alumnos e incidencias y no incluye los horarios actuales.

## Cuentas para la defensa

| Rol | Usuario | Contraseña | Estado |
| --- | --- | --- | --- |
| Dirección | `directora@cenalop.edu.sv` | `sistema123` | Activa |
| Docentes | `maestro2@cenalop.edu.sv`, `maestro3@cenalop.edu.sv`, `maestro5@cenalop.edu.sv` a `maestro11@cenalop.edu.sv`, `maestro20@cenalop.edu.sv` | `sistema123` | Activas |
| Docentes | `maestro1@cenalop.edu.sv`, `maestro4@cenalop.edu.sv` | `sistema123` | Inactivas; no pueden iniciar sesión |

El comando guarda las contraseñas con el hash de Django. El archivo JSON no contiene hashes de la base local. El repositorio es público: usa estas cuentas únicamente en una instalación local de prueba.

La carga incluye 13 cuentas, 12 docentes, 14 secciones, 6 materias, 15 asignaciones de materias, 180 bloques, 90 clases con sus estados y observaciones, 52 alumnos ficticios y 67 registros de tarjeta. Los teléfonos y fechas de nacimiento de los docentes se sustituyeron por valores neutros.

El registro normal no cambia: al crear un docente nuevo, el sistema genera su contraseña y la envía por correo. Dirección debe asignarle la carga académica y los bloques antes de que pueda programar clases.
