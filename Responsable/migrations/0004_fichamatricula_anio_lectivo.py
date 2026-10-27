from datetime import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Responsable', '0003_matricula'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichamatricula',
            name='anio_lectivo',
            field=models.PositiveIntegerField(default=datetime.now().year),
        ),
    ]
