# dashboard/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from .models import Event

def dashboard_view(request):
    return render(request, 'dashboard/dashboard.html')

def events_api(request):
    # FullCalendar will send start/end params; you can filter if you want
    events = Event.objects.all()
    data = []
    for e in events:
        data.append({
            "id": e.id,
            "title": e.title,
            "start": e.start.isoformat(),
            "end": e.end.isoformat() if e.end else None,
        })
    return JsonResponse(data, safe=False)

def diary_view(request, date=None, event_id=None):
    # You can branch on date vs event_id later
    context = {
        "date": date,
        "event_id": event_id,
    }
    return render(request, 'dashboard/diary.html', context)
