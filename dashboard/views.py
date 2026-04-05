# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import Event, DiaryEntry
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

TODO_SECTION_CONFIG = [
    ("planning", "Planning", "todo-section-planning"),
    ("next", "Next Up", "todo-section-next"),
    ("progress", "In Progress", "todo-section-progress"),
    ("review", "Review", "todo-section-review"),
    ("done", "Done", "todo-section-done"),
]

TODO_DAYS = [
    ("Monday", "todo-day-monday"),
    ("Tuesday", "todo-day-tuesday"),
    ("Wednesday", "todo-day-wednesday"),
    ("Thursday", "todo-day-thursday"),
    ("Friday", "todo-day-friday"),
    ("Saturday", "todo-day-saturday"),
    ("Sunday", "todo-day-sunday"),
]


def get_todo_sections(request):
    custom_titles = request.session.get("todo_section_titles", {})
    sections = []
    for key, default_title, class_name in TODO_SECTION_CONFIG:
        raw_title = custom_titles.get(key, default_title)
        title = raw_title.strip()[:30] if isinstance(raw_title, str) else default_title
        if not title:
            title = default_title

        sections.append(
            {
                "key": key,
                "title": title,
                "default_title": default_title,
                "class_name": class_name,
            }
        )

    return sections


def get_default_todo_seed():
    return {
        "Monday": {
            "planning": ["Draft sprint goals"],
            "next": ["Break feature into tasks"],
        },
        "Tuesday": {
            "planning": ["Review diary feedback"],
            "progress": ["Implement style refinements"],
        },
        "Wednesday": {
            "next": ["Run usability checks"],
            "review": ["Check color contrast"],
        },
        "Thursday": {
            "progress": ["Polish responsive layout"],
            "review": ["Validate edge cases"],
        },
        "Friday": {
            "review": ["Demo completed changes"],
            "done": ["Ship approved updates"],
        },
        "Saturday": {
            "planning": ["Personal planning"],
            "done": ["Weekly tidy-up"],
        },
        "Sunday": {
            "planning": ["Set priorities for Monday"],
            "done": ["Rest and reset"],
        },
    }


def get_todo_tasks_by_day(request):
    raw_tasks = request.session.get("todo_tasks")
    if not isinstance(raw_tasks, dict):
        raw_tasks = get_default_todo_seed()

    tasks_by_day = {}
    changed = False
    for day_name, _ in TODO_DAYS:
        tasks_by_day[day_name] = {}
        day_map = raw_tasks.get(day_name, {}) if isinstance(raw_tasks.get(day_name, {}), dict) else {}
        for section_key, _, _ in TODO_SECTION_CONFIG:
            section_tasks = day_map.get(section_key, [])
            if not isinstance(section_tasks, list):
                section_tasks = []
                changed = True

            cleaned_tasks = []
            for task in section_tasks:
                if isinstance(task, str) and task.strip():
                    cleaned_tasks.append(task.strip()[:180])

            if cleaned_tasks != section_tasks:
                changed = True

            tasks_by_day[day_name][section_key] = cleaned_tasks

    if changed or request.session.get("todo_tasks") is None:
        request.session["todo_tasks"] = tasks_by_day
        request.session.modified = True

    return tasks_by_day

@login_required
def dashboard_view(request):
    # Get upcoming diary entries for the current user
    diary_entries = DiaryEntry.objects.filter(user=request.user).order_by('date', 'start_time', 'created_at')[:5]

    todo_sections = get_todo_sections(request)
    tasks_by_day = get_todo_tasks_by_day(request)
    todo_columns = []
    for section in todo_sections:
        section_tasks = []
        for day_name, _ in TODO_DAYS:
            section_tasks.extend(tasks_by_day.get(day_name, {}).get(section["key"], []))

        if not section_tasks:
            section_tasks = ["No entries yet"]

        todo_columns.append(
            {
                "title": section["title"],
                "list_class": f"todo-list-{section['key']}",
                "tasks": section_tasks[:6],
            }
        )

    context = {
        'diary_entries': diary_entries,
        'todo_columns': todo_columns,
    }
    return render(request, 'dashboard/dashboard.html', context)

@login_required
def events_api(request):
    # Return events for FullCalendar, including diary entries
    events = Event.objects.all()
    data = []
    for event in events:
        data.append({
            "id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat() if event.end else None,
            "allDay": False,
            "source": "event",
        })

    diary_entries = DiaryEntry.objects.filter(user=request.user)
    for entry in diary_entries:
        if entry.start_time:
            start_dt = datetime.combine(entry.date, entry.start_time)
            if entry.end_time:
                end_dt = datetime.combine(entry.date, entry.end_time)
                if end_dt <= start_dt:
                    end_dt = end_dt + timedelta(days=1)
            else:
                end_dt = start_dt + timedelta(hours=1)

            start_value = start_dt.isoformat()
            end_value = end_dt.isoformat()
            all_day = False
        else:
            range_end = entry.end_date if entry.end_date else entry.date
            start_value = entry.date.isoformat()
            end_value = (range_end + timedelta(days=1)).isoformat()
            all_day = True

        data.append({
            "id": f"diary-{entry.id}",
            "title": entry.title,
            "start": start_value,
            "end": end_value,
            "allDay": all_day,
            "source": "diary",
        })

    return JsonResponse(data, safe=False)

@login_required
def diary_api(request):
    # Return diary entries as events for FullCalendar
    diary_entries = DiaryEntry.objects.filter(user=request.user)
    data = []
    for entry in diary_entries:
        if entry.start_time:
            start_dt = datetime.combine(entry.date, entry.start_time)
            if entry.end_time:
                end_dt = datetime.combine(entry.date, entry.end_time)
                if end_dt <= start_dt:
                    end_dt = end_dt + timedelta(days=1)
            else:
                end_dt = start_dt + timedelta(hours=1)

            start_value = start_dt.isoformat()
            end_value = end_dt.isoformat()
            all_day = False
        else:
            range_end = entry.end_date if entry.end_date else entry.date
            start_value = entry.date.isoformat()
            end_value = (range_end + timedelta(days=1)).isoformat()
            all_day = True

        data.append({
            "id": entry.id,
            "title": entry.title,
            "start": start_value,
            "end": end_value,
            "allDay": all_day,
            "description": entry.content,
            "endDate": (entry.end_date.isoformat() if entry.end_date else entry.date.isoformat()) if all_day else '',
            "startTime": entry.start_time.strftime('%H:%M') if entry.start_time else '',
            "endTime": entry.end_time.strftime('%H:%M') if entry.end_time else '',
        })
    return JsonResponse(data, safe=False)

@login_required
def diary_view(request):
    # Diary page with week view
    diary_entries = DiaryEntry.objects.filter(user=request.user).order_by('-date', '-start_time', '-created_at')
    context = {
        "diary_entries": diary_entries,
    }
    return render(request, 'dashboard/diary.html', context)

@login_required
def todo_view(request):
    todo_sections = get_todo_sections(request)

    if request.method == 'POST' and request.POST.get('form_type') == 'update_section_titles':
        updated_titles = {}
        for section in todo_sections:
            raw_value = request.POST.get(f"section_{section['key']}", "")
            value = raw_value.strip()[:30]
            updated_titles[section['key']] = value if value else section['default_title']

        request.session['todo_section_titles'] = updated_titles
        request.session.modified = True
        return HttpResponseRedirect(reverse('todo'))

    if request.method == 'POST' and request.POST.get('form_type') == 'add_todo_entry':
        task_title = request.POST.get('task_title', '').strip()
        task_day = request.POST.get('task_day', '').strip()
        task_section = request.POST.get('task_section', '').strip()
        task_notes = request.POST.get('task_notes', '').strip()

        valid_days = {day_name for day_name, _ in TODO_DAYS}
        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_title:
            return HttpResponseRedirect(reverse('todo'))

        if task_day not in valid_days or task_section not in valid_sections:
            return HttpResponseRedirect(reverse('todo'))

        task_title = task_title[:120]
        task_notes = task_notes[:180]
        task_value = f"{task_title} - {task_notes}" if task_notes else task_title

        tasks_by_day = get_todo_tasks_by_day(request)
        tasks_by_day[task_day][task_section].append(task_value)

        request.session['todo_tasks'] = tasks_by_day
        request.session.modified = True
        return HttpResponseRedirect(reverse('todo'))

    if request.method == 'POST' and request.POST.get('form_type') in ('edit_todo_entry', 'delete_todo_entry'):
        form_type = request.POST.get('form_type')
        task_day = request.POST.get('task_day', '').strip()
        task_section = request.POST.get('task_section', '').strip()
        task_index_raw = request.POST.get('task_index', '').strip()

        valid_days = {day_name for day_name, _ in TODO_DAYS}
        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        try:
            task_index = int(task_index_raw)
        except ValueError:
            task_index = -1

        if task_day not in valid_days or task_section not in valid_sections or task_index < 0:
            return HttpResponseRedirect(reverse('todo'))

        tasks_by_day = get_todo_tasks_by_day(request)
        section_tasks = tasks_by_day.get(task_day, {}).get(task_section, [])

        if task_index >= len(section_tasks):
            return HttpResponseRedirect(reverse('todo'))

        if form_type == 'delete_todo_entry':
            del section_tasks[task_index]
        else:
            updated_value = request.POST.get('task_value', '').strip()[:180]
            if not updated_value:
                updated_title = request.POST.get('task_title', '').strip()[:120]
                updated_notes = request.POST.get('task_notes', '').strip()[:180]
                updated_value = f"{updated_title} - {updated_notes}" if updated_notes else updated_title

            if not updated_value:
                return HttpResponseRedirect(reverse('todo'))

            section_tasks[task_index] = updated_value

        tasks_by_day[task_day][task_section] = section_tasks
        request.session['todo_tasks'] = tasks_by_day
        request.session.modified = True
        return HttpResponseRedirect(reverse('todo'))

    todo_sections = get_todo_sections(request)
    tasks_by_day = get_todo_tasks_by_day(request)

    day_lists = []
    for day_name, class_name in TODO_DAYS:
        sections = []
        day_seed = tasks_by_day.get(day_name, {})
        for section in todo_sections:
            sections.append(
                {
                    "name": section["title"],
                    "key": section["key"],
                    "class_name": section["class_name"],
                    "tasks": day_seed.get(section["key"], []),
                }
            )

        day_lists.append(
            {
                "name": day_name,
                "class_name": class_name,
                "sections": sections,
            }
        )

    return render(
        request,
        'dashboard/todo.html',
        {
            "day_lists": day_lists,
            "todo_sections": todo_sections,
        },
    )

@login_required
def add_diary_entry(request):
    if request.method == 'POST':
        entry_id = request.POST.get('entry_id')
        title = request.POST.get('title')
        date = request.POST.get('date')
        end_date = request.POST.get('end_date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        content = request.POST.get('content')
        redirect_date = datetime.today().date().isoformat()

        if date:
            try:
                redirect_date = datetime.strptime(date, '%Y-%m-%d').date().isoformat()
            except ValueError:
                pass

        if title:
            parsed_start = None
            parsed_end = None
            parsed_date = None
            parsed_end_date = None

            try:
                parsed_date = datetime.strptime(date, '%Y-%m-%d').date() if date else datetime.today().date()
                redirect_date = parsed_date.isoformat()
                if end_date:
                    parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_time:
                    parsed_start = datetime.strptime(start_time, '%H:%M').time()
                if end_time:
                    parsed_end = datetime.strptime(end_time, '%H:%M').time()
            except ValueError:
                messages.error(request, 'Invalid date/time format. Please check your values.')
                return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

            if parsed_end_date and parsed_end_date < parsed_date:
                messages.error(request, 'End date must be on or after start date.')
                return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

            # Multi-day range applies to all-day entries only.
            effective_end_date = parsed_end_date if (not parsed_start and not parsed_end) else None

            if entry_id:
                diary_entry = DiaryEntry.objects.filter(id=entry_id, user=request.user).first()
                if not diary_entry:
                    messages.error(request, 'Diary entry not found.')
                    return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

                diary_entry.title = title
                diary_entry.date = parsed_date
                diary_entry.end_date = effective_end_date
                diary_entry.start_time = parsed_start
                diary_entry.end_time = parsed_end
                diary_entry.content = content or ''
                diary_entry.save()
                messages.success(request, 'Diary entry updated successfully!')
            else:
                DiaryEntry.objects.create(
                    user=request.user,
                    title=title,
                    date=parsed_date,
                    end_date=effective_end_date,
                    start_time=parsed_start,
                    end_time=parsed_end,
                    content=content or ''
                )
                messages.success(request, 'Diary entry added successfully!')
        else:
            messages.error(request, 'Please provide a diary entry title.')
        return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

    return HttpResponseRedirect(reverse('diary'))
