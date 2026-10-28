#!/usr/bin/env bash
# Detener la ejecución si ocurre cualquier error
set -o errexit

# Instalar librerías de producción
pip install -r requirements.txt

# Empaquetar y comprimir archivos estáticos (CSS, JS, imágenes)
python manage.py collectstatic --no-input

# Aplicar las migraciones a la base de datos PostgreSQL de Render
python manage.py migrate