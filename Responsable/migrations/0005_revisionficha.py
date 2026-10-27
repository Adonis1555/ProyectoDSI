from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Responsable', '0004_fichamatricula_anio_lectivo'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='RevisionFicha',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('accion', models.CharField(choices=[('ACEPTAR', 'Aceptada'), ('SUBSANAR', 'Subsanación solicitada'), ('REENVIAR', 'Corrección reenviada')], max_length=12)),
            ('motivo', models.TextField(blank=True)),
            ('datos_anteriores', models.JSONField(default=dict, encoder=DjangoJSONEncoder)),
            ('fecha', models.DateTimeField(auto_now_add=True)),
            ('ficha', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='revisiones', to='Responsable.fichamatricula')),
            ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['fecha', 'pk']},
    )]
