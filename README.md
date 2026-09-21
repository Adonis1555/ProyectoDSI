# ProyectoDSI

Sistema escolar desarrollado con Django y PostgreSQL.

## Preparar el proyecto

1. Instala las dependencias: `pip install -r requirements.txt`.
2. Crea la base PostgreSQL `ProyectoDSI` y ajusta `DATABASES['default']['PASSWORD']` en tu copia local de `Cenalop_DSI/settings.py` según tu instalación. No subas tu contraseña al repositorio.
3. Crea las tablas: `python manage.py migrate`.
4. Inicia el servidor: `python manage.py runserver`.

Para instalar las cuentas y escenarios de la defensa en una base nueva, sigue [Datos de demostración](DATOS_DEMO.md).
