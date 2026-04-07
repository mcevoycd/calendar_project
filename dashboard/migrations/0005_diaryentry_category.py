from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_diaryentry_end_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='diaryentry',
            name='category',
            field=models.CharField(default='general', max_length=20),
        ),
    ]
