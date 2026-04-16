# dashboard/models.py
import os

from django.db import models
from django.contrib.auth.models import User

class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    # optional: link to diary entry, user, etc.

    def __str__(self):
        return self.title

class DiaryEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, default='general')
    date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.date}"


class UserPreference(models.Model):
    THEME_CHOICES = [
        ('dark', 'Dark'),
        ('light', 'Light'),
        ('system', 'System'),
    ]

    NAV_LAYOUT_CHOICES = [
        ('sidebar', 'Sidebar'),
        ('tabs', 'Vertical tabs'),
        ('bottom', 'Bottom nav'),
    ]

    DIARY_VIEW_CHOICES = [
        ('month', 'Month'),
        ('week', 'Week'),
        ('day', 'Day'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='dark')
    nav_layout = models.CharField(max_length=10, choices=NAV_LAYOUT_CHOICES, default='sidebar')
    default_diary_view = models.CharField(max_length=10, choices=DIARY_VIEW_CHOICES, default='week')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class TodoSectionTitle(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_section_titles')
    section_key = models.CharField(max_length=20)
    title = models.CharField(max_length=30)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'section_key')

    def __str__(self):
        return f"{self.user.username} - {self.section_key}: {self.title}"


class TodoTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_tasks')
    task_id = models.CharField(max_length=80)
    title = models.CharField(max_length=120)
    notes = models.TextField(blank=True)
    checklist_data = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=10, default='medium')
    completed = models.BooleanField(default=False)
    section = models.CharField(max_length=20, default='planning')
    start_day = models.CharField(max_length=12, default='Monday')
    end_day = models.CharField(max_length=12, default='Monday')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=40, blank=True)
    source_week = models.CharField(max_length=10, blank=True)
    source_box_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'task_id')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class NotesCanvasWeek(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes_canvas_weeks')
    week_start = models.DateField()
    canvas_data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'week_start')

    def __str__(self):
        return f"{self.user.username} - {self.week_start.isoformat()}"


class NoteCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='note_categories')
    name = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class NoteEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='note_entries')
    category = models.ForeignKey(
        NoteCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='note_entries',
    )
    title = models.CharField(max_length=140)
    is_pinned = models.BooleanField(default=False)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"


def note_attachment_upload_to(instance, filename):
    safe_name = os.path.basename(str(filename or 'attachment')) or 'attachment'
    return f"note_attachments/user_{instance.note.user_id}/note_{instance.note_id}/{safe_name}"


class NoteAttachment(models.Model):
    note = models.ForeignKey(NoteEntry, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=note_attachment_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    def __str__(self):
        return self.filename
