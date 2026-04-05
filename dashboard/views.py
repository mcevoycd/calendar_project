# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime, timedelta
from .models import Event, DiaryEntry
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from uuid import uuid4

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

TODO_DAY_ORDER = [day_name for day_name, _ in TODO_DAYS]
TODO_DAY_INDEX = {day_name: index for index, day_name in enumerate(TODO_DAY_ORDER)}

TODO_PRIORITY_CHOICES = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


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


def normalize_todo_task(raw_task):
    if isinstance(raw_task, dict):
        title = str(raw_task.get("title", "")).strip()[:120]
        notes = str(raw_task.get("notes", "")).strip()[:180]
        priority = str(raw_task.get("priority", "medium")).strip().lower()
        completed = bool(raw_task.get("completed", False))
    elif isinstance(raw_task, str):
        value = raw_task.strip()
        if not value:
            return None

        if " - " in value:
            title, notes = value.split(" - ", 1)
            title = title.strip()[:120]
            notes = notes.strip()[:180]
        else:
            title = value[:120]
            notes = ""
        priority = "medium"
        completed = False
    else:
        return None

    if not title:
        return None

    if priority not in TODO_PRIORITY_CHOICES:
        priority = "medium"

    return {
        "title": title,
        "notes": notes,
        "priority": priority,
        "priority_label": TODO_PRIORITY_CHOICES[priority],
        "completed": completed,
    }


def normalize_todo_task_item(raw_item, default_day=None, default_section="planning"):
    if not isinstance(raw_item, dict):
        return None

    title = str(raw_item.get("title", "")).strip()[:120]
    if not title:
        return None

    notes = str(raw_item.get("notes", "")).strip()[:180]
    priority = str(raw_item.get("priority", "medium")).strip().lower()
    if priority not in TODO_PRIORITY_CHOICES:
        priority = "medium"

    section = str(raw_item.get("section", default_section)).strip().lower()
    valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}
    if section not in valid_sections:
        section = default_section if default_section in valid_sections else "planning"

    start_day = str(raw_item.get("start_day", default_day or "Monday")).strip()
    end_day = str(raw_item.get("end_day", start_day)).strip()
    if start_day not in TODO_DAY_INDEX:
        start_day = default_day if default_day in TODO_DAY_INDEX else "Monday"
    if end_day not in TODO_DAY_INDEX:
        end_day = start_day

    start_index = TODO_DAY_INDEX[start_day]
    end_index = TODO_DAY_INDEX[end_day]
    if end_index < start_index:
        start_day, end_day = end_day, start_day

    task_id = str(raw_item.get("id", "")).strip() or str(uuid4())

    return {
        "id": task_id,
        "title": title,
        "notes": notes,
        "priority": priority,
        "priority_label": TODO_PRIORITY_CHOICES[priority],
        "completed": bool(raw_item.get("completed", False)),
        "section": section,
        "start_day": start_day,
        "end_day": end_day,
    }


def get_todo_task_items(request):
    raw_items = request.session.get("todo_task_items")
    changed = False
    task_items = []

    if isinstance(raw_items, list):
        for raw_item in raw_items:
            normalized = normalize_todo_task_item(raw_item)
            if normalized:
                task_items.append(normalized)
            else:
                changed = True
    else:
        legacy_tasks = request.session.get("todo_tasks")
        source = legacy_tasks if isinstance(legacy_tasks, dict) else get_default_todo_seed()
        changed = True

        for day_name, section_map in source.items():
            if day_name not in TODO_DAY_INDEX or not isinstance(section_map, dict):
                continue

            for section_key, tasks in section_map.items():
                if not isinstance(tasks, list):
                    continue

                for raw_task in tasks:
                    normalized_task = normalize_todo_task(raw_task)
                    if not normalized_task:
                        continue

                    normalized_item = normalize_todo_task_item(
                        {
                            "id": str(uuid4()),
                            "title": normalized_task["title"],
                            "notes": normalized_task["notes"],
                            "priority": normalized_task["priority"],
                            "completed": normalized_task["completed"],
                            "section": section_key,
                            "start_day": day_name,
                            "end_day": day_name,
                        },
                        default_day=day_name,
                        default_section=section_key,
                    )

                    if normalized_item:
                        task_items.append(normalized_item)

    if changed:
        request.session["todo_task_items"] = task_items
        request.session.modified = True

    return task_items


def get_todo_tasks_by_day(request):
    tasks_by_day = {}
    for day_name, _ in TODO_DAYS:
        tasks_by_day[day_name] = {}
        for section_key, _, _ in TODO_SECTION_CONFIG:
            tasks_by_day[day_name][section_key] = []

    for item in get_todo_task_items(request):
        start_index = TODO_DAY_INDEX[item["start_day"]]
        end_index = TODO_DAY_INDEX[item["end_day"]]
        for day_index in range(start_index, end_index + 1):
            day_name = TODO_DAY_ORDER[day_index]
            tasks_by_day[day_name][item["section"]].append(item)

    return tasks_by_day

@login_required
def dashboard_view(request):
    # Get upcoming diary entries for the current user
    diary_entries = DiaryEntry.objects.filter(user=request.user).order_by('date', 'start_time', 'created_at')[:5]

    todo_sections = get_todo_sections(request)
    task_items = get_todo_task_items(request)
    todo_columns = []
    for section in todo_sections:
        section_tasks = [item for item in task_items if item["section"] == section["key"]]

        display_tasks = []
        for task in section_tasks[:6]:
            task_line = f"[{task['priority_label']}] {task['title']}"
            if task.get("notes"):
                task_line = f"{task_line} - {task['notes']}"
            if task["start_day"] != task["end_day"]:
                task_line = f"{task_line} ({task['start_day']} to {task['end_day']})"
            if task.get("completed"):
                task_line = f"[Done] {task_line}"
            display_tasks.append(task_line)

        if not display_tasks:
            display_tasks = ["No entries yet"]

        todo_columns.append(
            {
                "title": section["title"],
                "list_class": f"todo-list-{section['key']}",
                "tasks": display_tasks,
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
        task_start_day = request.POST.get('task_start_day', '').strip() or request.POST.get('task_day', '').strip()
        task_end_day = request.POST.get('task_end_day', '').strip() or task_start_day
        task_section = request.POST.get('task_section', '').strip()
        task_notes = request.POST.get('task_notes', '').strip()
        task_priority = request.POST.get('task_priority', '').strip().lower()
        task_completed = request.POST.get('task_completed') == 'on'

        valid_days = {day_name for day_name, _ in TODO_DAYS}
        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_title:
            return HttpResponseRedirect(reverse('todo'))

        if task_start_day not in valid_days or task_end_day not in valid_days or task_section not in valid_sections:
            return HttpResponseRedirect(reverse('todo'))

        if TODO_DAY_INDEX[task_end_day] < TODO_DAY_INDEX[task_start_day]:
            task_start_day, task_end_day = task_end_day, task_start_day

        if task_priority not in TODO_PRIORITY_CHOICES:
            task_priority = 'medium'

        task_title = task_title[:120]
        task_notes = task_notes[:180]
        task_value = {
            "id": str(uuid4()),
            "title": task_title,
            "notes": task_notes,
            "priority": task_priority,
            "completed": task_completed,
            "section": task_section,
            "start_day": task_start_day,
            "end_day": task_end_day,
        }

        task_items = get_todo_task_items(request)
        task_items.append(normalize_todo_task_item(task_value, default_day=task_start_day, default_section=task_section))

        request.session['todo_task_items'] = task_items
        request.session.modified = True
        return HttpResponseRedirect(reverse('todo'))

    if request.method == 'POST' and request.POST.get('form_type') in ('edit_todo_entry', 'delete_todo_entry', 'toggle_todo_completed'):
        form_type = request.POST.get('form_type')
        task_id = request.POST.get('task_id', '').strip()

        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_id:
            return HttpResponseRedirect(reverse('todo'))

        task_items = get_todo_task_items(request)
        task_pos = next((index for index, item in enumerate(task_items) if item.get('id') == task_id), -1)
        if task_pos == -1:
            return HttpResponseRedirect(reverse('todo'))

        if form_type == 'delete_todo_entry':
            del task_items[task_pos]
        elif form_type == 'toggle_todo_completed':
            current_task = task_items[task_pos]
            current_task['completed'] = not bool(current_task.get('completed', False))
            task_items[task_pos] = normalize_todo_task_item(
                current_task,
                default_day=current_task.get('start_day', 'Monday'),
                default_section=current_task.get('section', 'planning'),
            )
        else:
            updated_title = request.POST.get('task_title', '').strip()[:120]
            updated_notes = request.POST.get('task_notes', '').strip()[:180]
            updated_priority = request.POST.get('task_priority', '').strip().lower()
            updated_completed = request.POST.get('task_completed') == 'on'
            updated_section = request.POST.get('task_section', '').strip().lower()
            updated_start_day = request.POST.get('task_start_day', '').strip() or request.POST.get('task_day', '').strip()
            updated_end_day = request.POST.get('task_end_day', '').strip() or updated_start_day

            if updated_priority not in TODO_PRIORITY_CHOICES:
                updated_priority = 'medium'

            if updated_section not in valid_sections:
                updated_section = 'planning'

            if updated_start_day not in TODO_DAY_INDEX:
                updated_start_day = 'Monday'
            if updated_end_day not in TODO_DAY_INDEX:
                updated_end_day = updated_start_day

            if TODO_DAY_INDEX[updated_end_day] < TODO_DAY_INDEX[updated_start_day]:
                updated_start_day, updated_end_day = updated_end_day, updated_start_day

            if not updated_title:
                return HttpResponseRedirect(reverse('todo'))

            task_items[task_pos] = {
                "id": task_id,
                "title": updated_title,
                "notes": updated_notes,
                "priority": updated_priority,
                "completed": updated_completed,
                "section": updated_section,
                "start_day": updated_start_day,
                "end_day": updated_end_day,
            }

        normalized_items = []
        for item in task_items:
            normalized = normalize_todo_task_item(
                item,
                default_day=item.get('start_day', 'Monday') if isinstance(item, dict) else 'Monday',
                default_section=item.get('section', 'planning') if isinstance(item, dict) else 'planning',
            )
            if normalized:
                normalized_items.append(normalized)

        request.session['todo_task_items'] = normalized_items
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
