from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Directora', '0011_asignacionbloquemaestro')]
    operations = [
        migrations.RemoveConstraint(model_name='asignacionbloquemaestro', name='bloque_unico_por_maestro_y_anio'),
        migrations.AddField(model_name='asignacionbloquemaestro', name='turno', field=models.CharField(choices=[('Mañana', 'Mañana'), ('Tarde', 'Tarde')], default='Mañana', max_length=10)),
        migrations.AddConstraint(model_name='asignacionbloquemaestro', constraint=models.UniqueConstraint(fields=('maestro', 'dia', 'bloque', 'turno', 'anio_lectivo'), name='bloque_unico_maestro_turno_anio')),
        migrations.AlterModelOptions(name='asignacionbloquemaestro', options={'ordering': ['maestro', 'turno', 'dia', 'bloque'], 'verbose_name': 'Asignación de bloque a maestro', 'verbose_name_plural': 'Asignaciones de bloques a maestros'}),
    ]
