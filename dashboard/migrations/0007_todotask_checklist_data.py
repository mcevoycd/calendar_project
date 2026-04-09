from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0006_user_models_and_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="todotask",
            name="checklist_data",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
