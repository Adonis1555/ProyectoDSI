from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone

from Directora.models import (
    ConfiguracionPeriodo,
    GradoSeccion,
    Maestro,
    Materia,
    AsignacionMateria,
    AsignacionBloqueMaestro,
    normalizar_turno,
)
from Maestros.models import Alumno, HorarioClase
from Responsable.models import Responsable, FichaMatricula, Matricula

Usuario = get_user_model()


class Command(BaseCommand):
    help = "Carga datos demostrativos con balance perfecto de materias, docentes y horarios sin choques"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando carga de datos demo con horarios concordantes..."))

        with transaction.atomic():
            # 1. Configurar Periodo Institucional Activo
            periodo = ConfiguracionPeriodo.get_solo()
            periodo.anio_activo = 2026
            periodo.fase_actual = 'MATRICULA'
            periodo.save()
            anio = periodo.anio_activo

            # 2. Cuenta de Directora General
            directora_email = "directora@gmail.com"
            directora_user, _ = Usuario.objects.get_or_create(
                email=directora_email,
                defaults={
                    "nombre": "Ana Lucía",
                    "apellido": "Martínez de Orellana",
                    "rol": "directora",
                    "is_staff": True,
                    "is_superuser": True,
                    "activo": True
                }
            )
            directora_user.set_password("demo1234")
            directora_user.rol = "directora"
            directora_user.is_staff = True
            directora_user.is_superuser = True
            directora_user.save()

            # 3. Creación de Docentes (Titulares de Básica y Especialistas de Tercer Ciclo)
            maestros_datos = [
                # Orientadores titulares exclusivos de Básica / Parvularia
                {"dui": "01000001-1", "nombre": "Carlos Manuel", "apellido": "Rivas", "esp": "Educación Inicial", "email": "crivas@cenalop.edu.sv"},
                {"dui": "01000002-2", "nombre": "Sonia Elizabeth", "apellido": "Aguilar", "esp": "Educación Inicial", "email": "saguilar@cenalop.edu.sv"},
                {"dui": "01000003-3", "nombre": "María Teresa", "apellido": "Gómez", "esp": "Educación Básica", "email": "mgomez@cenalop.edu.sv"},
                {"dui": "01000004-4", "nombre": "Roberto Carlos", "apellido": "Hernández", "esp": "Educación Básica", "email": "rhernandez@cenalop.edu.sv"},

                # Especialistas de Tercer Ciclo (Docentes que no son titulares de básica en la mañana)
                {"dui": "02000001-5", "nombre": "Francisco", "apellido": "Alvarenga", "esp": "Matemática", "email": "falvarenga@cenalop.edu.sv"},
                {"dui": "02000002-6", "nombre": "Claudia Beatriz", "apellido": "Mejía", "esp": "Lenguaje y Literatura", "email": "cmejia@cenalop.edu.sv"},
                {"dui": "02000003-7", "nombre": "José Santos", "apellido": "Pineda", "esp": "Ciencias Naturales", "email": "jpineda@cenalop.edu.sv"},
                {"dui": "02000004-8", "nombre": "Ana Silvia", "apellido": "Cruz", "esp": "Estudios Sociales", "email": "acruz@cenalop.edu.sv"},
                {"dui": "02000005-9", "nombre": "David Ernesto", "apellido": "Ramos", "esp": "Idioma Extranjero (Inglés)", "email": "dramos@cenalop.edu.sv"},
                {"dui": "02000006-0", "nombre": "Hugo Alexander", "apellido": "Pérez", "esp": "Educación Física", "email": "hperez@cenalop.edu.sv"},
            ]

            docentes = {}
            for m in maestros_datos:
                u, _ = Usuario.objects.get_or_create(
                    email=m["email"],
                    defaults={"nombre": m["nombre"], "apellido": m["apellido"], "rol": "maestro", "activo": True}
                )
                u.set_password("demo1234")
                u.rol = 'maestro'
                u.save()

                doc, _ = Maestro.objects.update_or_create(
                    dui=m["dui"],
                    defaults={
                        "nombre": m["nombre"],
                        "apellido": m["apellido"],
                        "especialidad": m["esp"],
                        "telefono": "7845-1200",
                        "id_usuario": u,
                        "activo": True
                    }
                )
                docentes[m["email"]] = doc

            # 4. Catálogo Oficial de Materias
            materias_datos = [
                # Parvularia (Suman 25 bloques semanales)
                ("Desarrollo Personal y Social", "DPS", "#F59E0B", 10, "PARVULARIA"),
                ("Expresión, Comunicación y Representación", "ECR", "#3B82F6", 10, "PARVULARIA"),
                ("Relación con el Entorno", "RE", "#10B981", 5, "PARVULARIA"),

                # Tercer Ciclo y Básica (Suman 25 bloques semanales)
                ("Matemática", "MAT", "#2E5299", 5, "BASICA_Y_TERCER"),
                ("Lenguaje y Literatura", "LENG", "#D97706", 5, "BASICA_Y_TERCER"),
                ("Ciencias Naturales", "CIEN", "#059669", 5, "BASICA_Y_TERCER"),
                ("Estudios Sociales", "SOC", "#DC2626", 5, "BASICA_Y_TERCER"),
                ("Idioma Extranjero (Inglés)", "ING", "#7C3AED", 3, "BASICA_Y_TERCER"),
                ("Educación Física", "EDF", "#0284C7", 2, "BASICA_Y_TERCER"),
            ]

            materias = {}
            for nom, cod, col, bloq, niv in materias_datos:
                mat, _ = Materia.objects.update_or_create(
                    nombre=nom,
                    defaults={"codigo": cod, "color": col, "bloques_semanales": bloq, "nivel_aplicable": niv}
                )
                materias[nom] = mat

            # 5. Creación de Aulas y Grados
            aulas = [
                ("PK5", "A", "Mañana", 30, docentes["crivas@cenalop.edu.sv"]),
                ("PK6", "A", "Mañana", 30, docentes["saguilar@cenalop.edu.sv"]),
                ("1G", "A", "Mañana", 35, docentes["mgomez@cenalop.edu.sv"]),
                ("2G", "A", "Mañana", 35, docentes["rhernandez@cenalop.edu.sv"]),
                ("7G", "A", "Mañana", 40, docentes["falvarenga@cenalop.edu.sv"]),
                ("8G", "A", "Mañana", 40, docentes["cmejia@cenalop.edu.sv"]),
                ("9G", "A", "Mañana", 40, docentes["jpineda@cenalop.edu.sv"]),
            ]

            secciones_map = {}
            for grado, sec, turno, cupo, orientador in aulas:
                s, _ = GradoSeccion.objects.update_or_create(
                    grado=grado, seccion=sec,
                    defaults={"turno": turno, "cupo_maximo": cupo, "maestro_encargado": orientador, "activo": True}
                )
                secciones_map[grado] = s

            # 6. Limpieza Total de Asignaciones y Horarios Previos del Ciclo
            AsignacionMateria.objects.filter(anio_lectivo=anio).delete()
            HorarioClase.objects.filter(anio_lectivo=anio).delete()
            AsignacionBloqueMaestro.objects.filter(anio_lectivo=anio).delete()

            # 7. Asignación Formal de Especialistas para Tercer Ciclo
            esp_mat = {
                "Matemática": docentes["falvarenga@cenalop.edu.sv"],
                "Lenguaje y Literatura": docentes["cmejia@cenalop.edu.sv"],
                "Ciencias Naturales": docentes["jpineda@cenalop.edu.sv"],
                "Estudios Sociales": docentes["acruz@cenalop.edu.sv"],
                "Idioma Extranjero (Inglés)": docentes["dramos@cenalop.edu.sv"],
                "Educación Física": docentes["hperez@cenalop.edu.sv"],
            }

            for grado_cod in ["7G", "8G", "9G"]:
                sec_obj = secciones_map[grado_cod]
                for nombre_mat, doc_esp in esp_mat.items():
                    AsignacionMateria.objects.create(
                        grado_seccion=sec_obj,
                        materia=materias[nombre_mat],
                        docente=doc_esp,
                        anio_lectivo=anio
                    )

            # 8. Generación de Horarios para Básica y Parvularia
            bloques_parvularia = (
                [materias["Desarrollo Personal y Social"]] * 10 +
                [materias["Expresión, Comunicación y Representación"]] * 10 +
                [materias["Relación con el Entorno"]] * 5
            )

            bloques_basica = (
                [materias["Matemática"]] * 5 +
                [materias["Lenguaje y Literatura"]] * 5 +
                [materias["Ciencias Naturales"]] * 5 +
                [materias["Estudios Sociales"]] * 5 +
                [materias["Idioma Extranjero (Inglés)"]] * 3 +
                [materias["Educación Física"]] * 2
            )

            for grado_cod, lista_mats in [("PK5", bloques_parvularia), ("PK6", bloques_parvularia), ("1G", bloques_basica), ("2G", bloques_basica)]:
                sec_obj = secciones_map[grado_cod]
                doc_titular = sec_obj.maestro_encargado
                turno_s = normalizar_turno(sec_obj.turno)

                idx = 0
                for d in range(1, 6):
                    for b in range(1, 6):
                        mat_slot = lista_mats[idx]
                        idx += 1

                        AsignacionBloqueMaestro.objects.update_or_create(
                            maestro=doc_titular, dia=d, bloque=b, turno=turno_s, anio_lectivo=anio, defaults={"activo": True}
                        )
                        HorarioClase.objects.create(
                            grado_seccion=sec_obj, docente=doc_titular, materia=mat_slot,
                            dia=d, bloque=b, turno=turno_s, anio_lectivo=anio,
                            estado="PUBLICADO", fecha_publicacion=timezone.now(),
                            observaciones="Horario oficial publicado."
                        )

            # 9. Matriz de Horarios de Tercer Ciclo (Cuadrado Latino Balanceado Diario)
            # Para cada día (Lunes a Viernes), cada aula tiene las mismas 5 materias pero rotadas.
            # Lunes, Miércoles, Viernes: MAT, LENG, CIEN, SOC, ING (1 de c/u por aula)
            # Martes, Jueves: MAT, LENG, CIEN, SOC, EDF (1 de c/u por aula)
            # Total semanal por sección: MAT=5, LENG=5, CIEN=5, SOC=5, ING=3, EDF=2.
            dias_con_ing = ["Matemática", "Lenguaje y Literatura", "Ciencias Naturales", "Estudios Sociales", "Idioma Extranjero (Inglés)"]
            dias_con_edf = ["Matemática", "Lenguaje y Literatura", "Ciencias Naturales", "Estudios Sociales", "Educación Física"]

            grilla_dias = [
                (1, dias_con_ing),  # Lunes
                (2, dias_con_edf),  # Martes
                (3, dias_con_ing),  # Miércoles
                (4, dias_con_edf),  # Jueves
                (5, dias_con_ing),  # Viernes
            ]

            secciones_tercer = [secciones_map["7G"], secciones_map["8G"], secciones_map["9G"]]

            for dia_num, materias_del_dia in grilla_dias:
                for b in range(1, 6):  # Bloques 1 a 5
                    # Desplazamiento horario por aula:
                    # En el bloque b, 7°A toma índice (b-1), 8°A toma (b), 9°A toma (b+1)
                    idx_7g = (b - 1) % 5
                    idx_8g = (b) % 5
                    idx_9g = (b + 1) % 5

                    asignaciones_bloque = [
                        (secciones_tercer[0], materias_del_dia[idx_7g]),
                        (secciones_tercer[1], materias_del_dia[idx_8g]),
                        (secciones_tercer[2], materias_del_dia[idx_9g]),
                    ]

                    for sec_obj, nom_mat in asignaciones_bloque:
                        mat_obj = materias[nom_mat]
                        doc_obj = esp_mat[nom_mat]
                        turno_s = normalizar_turno(sec_obj.turno)

                        # Autorizar bloque al especialista
                        AsignacionBloqueMaestro.objects.update_or_create(
                            maestro=doc_obj, dia=dia_num, bloque=b, turno=turno_s, anio_lectivo=anio, defaults={"activo": True}
                        )

                        # Registrar clase oficial publicada
                        HorarioClase.objects.create(
                            grado_seccion=sec_obj,
                            docente=doc_obj,
                            materia=mat_obj,
                            dia=dia_num,
                            bloque=b,
                            turno=turno_s,
                            anio_lectivo=anio,
                            estado="PUBLICADO",
                            fecha_publicacion=timezone.now(),
                            observaciones="Horario oficial publicado y validado."
                        )

            # 10. Responsable y Ficha de Matrícula Demo (8° Grado Sección A)
            u_resp, _ = Usuario.objects.get_or_create(
                email="mflores@correo.com",
                defaults={"nombre": "María Teresa", "apellido": "Flores", "rol": "responsable", "activo": True}
            )
            u_resp.set_password("demo1234")
            u_resp.save()

            resp, _ = Responsable.objects.update_or_create(
                dui="04829105-3",
                defaults={
                    "nombre": "María Teresa", "apellido": "Flores", "telefono": "7845-1290",
                    "direccion": "Col. Escalón, Pasaje 3", "parentesco": "MADRE", "id_usuario": u_resp
                }
            )

            sec_8a = secciones_map["8G"]
            FichaMatricula.objects.update_or_create(
                nie="8572940",
                anio_lectivo=anio,
                defaults={
                    "nombres": "Sofía Valentina", "apellidos": "Gómez Flores",
                    "fecha_nacimiento": date(2012, 3, 14), "genero": "F",
                    "nacionalidad": "Salvadoreña", "responsable": resp,
                    "parentesco_responsable": "MADRE", "telefono_contacto": "7845-1290",
                    "grado_seccion": sec_8a, "estado": "PENDIENTE",
                    "direccion_exacta": "San Salvador"
                }
            )

        self.stdout.write(self.style.SUCCESS("✓ Demo generado con éxito: bloques, materias y docentes 100% concordantes y sin choques."))