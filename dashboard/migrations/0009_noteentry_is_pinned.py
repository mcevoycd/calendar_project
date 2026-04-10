from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_note_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='noteentry',
            name='is_pinned',
            field=models.BooleanField(default=False),
        ),
    ]
