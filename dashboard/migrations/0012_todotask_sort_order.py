from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0011_savedcanvas'),
    ]

    operations = [
        migrations.AddField(
            model_name='todotask',
            name='sort_order',
            field=models.IntegerField(db_index=True, default=1000000),
        ),
        migrations.AlterModelOptions(
            name='todotask',
            options={'ordering': ['sort_order', 'created_at']},
        ),
    ]
