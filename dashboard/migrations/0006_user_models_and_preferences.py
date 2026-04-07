from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0005_diaryentry_category'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NotesCanvasWeek',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField()),
                ('canvas_data', models.JSONField(default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='notes_canvas_weeks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'week_start')},
            },
        ),
        migrations.CreateModel(
            name='TodoSectionTitle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_key', models.CharField(max_length=20)),
                ('title', models.CharField(max_length=30)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='todo_section_titles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'section_key')},
            },
        ),
        migrations.CreateModel(
            name='TodoTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.CharField(max_length=80)),
                ('title', models.CharField(max_length=120)),
                ('notes', models.TextField(blank=True)),
                ('priority', models.CharField(default='medium', max_length=10)),
                ('completed', models.BooleanField(default=False)),
                ('section', models.CharField(default='planning', max_length=20)),
                ('start_day', models.CharField(default='Monday', max_length=12)),
                ('end_day', models.CharField(default='Monday', max_length=12)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('source', models.CharField(blank=True, max_length=40)),
                ('source_week', models.CharField(blank=True, max_length=10)),
                ('source_box_id', models.CharField(blank=True, max_length=80)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='todo_tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
                'unique_together': {('user', 'task_id')},
            },
        ),
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('theme', models.CharField(choices=[('dark', 'Dark'), ('light', 'Light'), ('system', 'System')], default='dark', max_length=10)),
                ('nav_layout', models.CharField(choices=[('sidebar', 'Sidebar'), ('tabs', 'Vertical tabs'), ('bottom', 'Bottom nav')], default='sidebar', max_length=10)),
                ('default_diary_view', models.CharField(choices=[('month', 'Month'), ('week', 'Week'), ('day', 'Day')], default='week', max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='preferences', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
