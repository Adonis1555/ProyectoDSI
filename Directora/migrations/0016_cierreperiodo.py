from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Directora', '0015_configuracionperiodo'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='CierrePeriodo',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('anio_lectivo', models.PositiveIntegerField()),
            ('fase_cerrada', models.CharField(choices=[('MATRICULA', 'Periodo de Matrícula'), ('CLASES', 'Periodo de Clases')], max_length=20)),
            ('fase_abierta', models.CharField(choices=[('MATRICULA', 'Periodo de Matrícula'), ('CLASES', 'Periodo de Clases')], max_length=20)),
            ('fecha', models.DateTimeField(auto_now_add=True)),
            ('resumen', models.JSONField(default=dict)),
            ('realizado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-fecha'], 'constraints': [models.UniqueConstraint(fields=('anio_lectivo', 'fase_cerrada'), name='cierre_unico_anio_fase')]},
    )]
