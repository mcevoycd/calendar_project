# dashboard/models.py
from django.db import models

class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    # optional: link to diary entry, user, etc.

    def __str__(self):
        return self.title
