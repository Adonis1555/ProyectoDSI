from django.db import migrations, models


def copiar_turno(apps, schema_editor):
    HorarioClase = apps.get_model('Maestros', 'HorarioClase')
    for clase in HorarioClase.objects.select_related('grado_seccion'):
        clase.turno = 'Tarde' if str(clase.grado_seccion.turno).strip().lower() == 'tarde' else 'Mañana'
        clase.save(update_fields=['turno'])


class Migration(migrations.Migration):
    dependencies = [('Directora', '0012_asignacionbloquemaestro_turno'), ('Maestros', '0012_horarioclase_fecha_publicacion_alter_horarioclase_estado')]
    operations = [
        migrations.AddField(model_name='horarioclase', name='turno', field=models.CharField(choices=[('Mañana', 'Mañana'), ('Tarde', 'Tarde')], default='Mañana', max_length=10)),
        migrations.RunPython(copiar_turno, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(name='horarioclase', unique_together={('docente', 'dia', 'bloque', 'turno', 'anio_lectivo'), ('grado_seccion', 'dia', 'bloque', 'turno', 'anio_lectivo')}),
    ]
