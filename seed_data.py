import os
import django
import random
from datetime import date, timedelta

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cenalop_DSI.settings')
django.setup()

from Login.models import Usuario
from Directora.models import Maestro, GradoSeccion
from Maestros.models import Alumno, RegistroTarjeta

def clean_database():
    print("Limpiando registros de tarjetas y alumnos para regenerar datos...")
    RegistroTarjeta.objects.all().delete()
    Alumno.objects.all().delete()

def seed_maestros_and_grados():
    print("Creando maestros y grados...")
    
    # Asegurar que existan los usuarios de maestros
    maestros_data = [
        {"email": "maestro1@gmail.com", "nombre": "Juan", "apellido": "Pérez", "dui": "01234567-9", "tel": "7111-1111", "esp": "Matemáticas"},
        {"email": "maestro2@gmail.com", "nombre": "María", "apellido": "Gómez", "dui": "02345678-8", "tel": "7222-2222", "esp": "Lenguaje"},
        {"email": "maestro3@gmail.com", "nombre": "Carlos", "apellido": "López", "dui": "03456789-7", "tel": "7333-3333", "esp": "Ciencias"},
    ]
    
    maestros_instances = []
    
    for m in maestros_data:
        user, created = Usuario.objects.get_or_create(
            email=m["email"],
            defaults={
                "nombre": m["nombre"],
                "apellido": m["apellido"],
                "rol": "maestro",
                "activo": True
            }
        )
        if created:
            user.set_password("sistema123")
            user.save()
            
        maestro, created = Maestro.objects.get_or_create(
            dui=m["dui"],
            defaults={
                "nombre": m["nombre"],
                "apellido": m["apellido"],
                "fecha_nac": date(1985, 5, 15),
                "especialidad": m["esp"],
                "telefono": m["tel"],
                "id_usuario": user,
                "activo": True
            }
        )
        maestros_instances.append(maestro)

    # Crear Grados y Secciones
    grados_data = [
        {"grado": "1G", "seccion": "A", "cupos": 35, "encargado": maestros_instances[0]},
        {"grado": "2G", "seccion": "A", "cupos": 30, "encargado": maestros_instances[1]},
        {"grado": "9G", "seccion": "A", "cupos": 25, "encargado": maestros_instances[2]},
    ]
    
    grados_instances = []
    for g in grados_data:
        gs, created = GradoSeccion.objects.get_or_create(
            grado=g["grado"],
            seccion=g["seccion"],
            defaults={
                "cupo_maximo": g["cupos"],
                "maestro_encargado": g["encargado"]
            }
        )
        grados_instances.append(gs)
        
    return grados_instances, maestros_instances

def seed_alumnos(grados):
    print("Creando alumnos...")
    nombres_hombres = ["José", "Luis", "Manuel", "Francisco", "Javier", "Miguel", "David", "Ángel", "Carlos", "Daniel"]
    nombres_mujeres = ["María", "Ana", "Carmen", "Josefa", "Isabel", "Francisca", "Marta", "Dolores", "Lucía", "Sofía"]
    apellidos = ["Morales", "Flores", "Hernández", "Martínez", "Rivas", "Alvarado", "Mejía", "Castro", "Vasquez", "Portillo"]
    
    alumnos_instances = []
    nie_base = 20260001
    
    for gr in grados:
        # Determinar rango de edad sugerido
        if gr.grado == "1G":
            edad_min, edad_max = 6, 8
        elif gr.grado == "2G":
            edad_min, edad_max = 7, 9
        else: # 9G
            edad_min, edad_max = 14, 16
            
        # Crear 10 alumnos por grado (5 hombres y 5 mujeres)
        for i in range(10):
            es_mujer = (i % 2 == 0)
            nombre = random.choice(nombres_mujeres) if es_mujer else random.choice(nombres_hombres)
            apellido = f"{random.choice(apellidos)} {random.choice(apellidos)}"
            sexo = "F" if es_mujer else "M"
            
            # Fecha nac
            edad = random.randint(edad_min, edad_max)
            fecha_nac = date.today() - timedelta(days=(edad * 365 + random.randint(0, 360)))
            
            nie = str(nie_base)
            nie_base += 1
            
            alumno = Alumno.objects.create(
                NIE=nie,
                nombre=nombre,
                apellido=apellido,
                fecha_nac=fecha_nac,
                sexo=sexo,
                grado_seccion=gr,
                activo=True
            )
            alumnos_instances.append(alumno)
            
    return alumnos_instances

def seed_incidencias(alumnos, maestros):
    print("Creando incidencias (Tarjetas) en Mayo y Junio de 2026...")
    
    # Definir fechas en Mayo y Junio 2026
    fechas_mayo = [date(2026, 5, i) for i in [4, 7, 12, 18, 20, 25, 29]]
    fechas_junio = [date(2026, 6, i) for i in [2, 5, 9, 11, 16, 22, 26]]
    
    # Crear demeritos (D), redenciones (R) y reconocimientos (RC)
    tipo_choices = ["D", "D", "D", "R", "RC"] # Mayoría deméritos para las gráficas
    sub_letras_choices = ["A", "B", "C", "D"]
    
    for f in fechas_mayo + fechas_junio:
        # Crear 2 a 4 tarjetas en cada una de estas fechas
        for _ in range(random.randint(2, 4)):
            alumno = random.choice(alumnos)
            maestro = random.choice(maestros)
            tipo = random.choice(tipo_choices)
            
            # Las redenciones solo tienen A, B, C como sub_letras
            sub_letra = random.choice(["A", "B", "C"]) if tipo == "R" else random.choice(sub_letras_choices)
            
            card = RegistroTarjeta.objects.create(
                alumno=alumno,
                tipo=tipo,
                sub_letra=sub_letra,
                maestro_registra=maestro.id_usuario
            )
            # Forzar la fecha ya que auto_now_add=True la pisa al crear
            RegistroTarjeta.objects.filter(pk=card.pk).update(fecha=f)
            
    print("Semilla de incidencias completada con éxito.")

if __name__ == "__main__":
    clean_database()
    grados, maestros = seed_maestros_and_grados()
    alumnos = seed_alumnos(grados)
    seed_incidencias(alumnos, maestros)
    print("Proceso de siembra finalizado exitosamente.")
