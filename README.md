# ProyectoDSI

Sistema escolar desarrollado con Django y PostgreSQL.

## Preparar el proyecto

1. Instala las dependencias: `pip install -r requirements.txt`.
2. Configura la base PostgreSQL `ProyectoDSI` y la variable local `DB_PASSWORD`.
3. Crea las tablas: `python manage.py migrate`.
4. Inicia el servidor: `python manage.py runserver`.

Para instalar las cuentas y escenarios de la defensa en una base nueva, sigue [Datos de demostración](DATOS_DEMO.md).
