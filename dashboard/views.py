# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from datetime import datetime, timedelta, time
from .models import Event, DiaryEntry
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from uuid import uuid4
import json

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

TODO_SECTION_COLORS = {
    "planning": "#38BDF8",
    "next": "#A3E635",
    "progress": "#FACC15",
    "review": "#FB7185",
    "done": "#34D399",
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

    parsed_start = None
    parsed_end = None
    start_date_raw = str(raw_item.get("start_date", "")).strip()
    end_date_raw = str(raw_item.get("end_date", "")).strip()
    if start_date_raw:
        try:
            parsed_start = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        except ValueError:
            parsed_start = None
    if end_date_raw:
        try:
            parsed_end = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
        except ValueError:
            parsed_end = None

    start_day = str(raw_item.get("start_day", default_day or "Monday")).strip()
    end_day = str(raw_item.get("end_day", start_day)).strip()

    if parsed_start and not parsed_end:
        parsed_end = parsed_start
    if parsed_end and not parsed_start:
        parsed_start = parsed_end

    if parsed_start and parsed_end and parsed_end < parsed_start:
        parsed_start, parsed_end = parsed_end, parsed_start

    if parsed_start and parsed_end:
        start_day = parsed_start.strftime("%A")
        end_day = parsed_end.strftime("%A")
    else:
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
        "start_date": parsed_start.isoformat() if parsed_start else "",
        "end_date": parsed_end.isoformat() if parsed_end else "",
        "source": str(raw_item.get("source", "")).strip()[:40],
        "source_week": str(raw_item.get("source_week", "")).strip()[:10],
        "source_box_id": str(raw_item.get("source_box_id", "")).strip()[:80],
    }


def get_todo_week_dates(request):
    query_date = request.GET.get("date", "").strip()
    try:
        anchor = datetime.strptime(query_date, "%Y-%m-%d").date() if query_date else datetime.today().date()
    except ValueError:
        anchor = datetime.today().date()

    week_start = anchor - timedelta(days=anchor.weekday())
    week_dates = []
    for offset, (day_name, _) in enumerate(TODO_DAYS):
        current = week_start + timedelta(days=offset)
        week_dates.append(
            {
                "name": day_name,
                "date": current,
                "date_iso": current.isoformat(),
                "date_label": current.strftime("%d %b"),
            }
        )

    return week_start, week_dates


def get_todo_return_url(request):
    return_date = request.POST.get("return_date", "").strip()
    if return_date:
        try:
            datetime.strptime(return_date, "%Y-%m-%d")
            return f"{reverse('todo')}?date={return_date}"
        except ValueError:
            pass

    return reverse('todo')


def diary_entry_to_calendar_values(entry):
    # Treat any entry with at least one time value as a timed event.
    if entry.start_time is not None or entry.end_time is not None:
        start_clock = entry.start_time or time(0, 0)
        start_dt = datetime.combine(entry.date, start_clock)

        if entry.end_time:
            end_dt = datetime.combine(entry.date, entry.end_time)
            if end_dt <= start_dt:
                end_dt = end_dt + timedelta(days=1)
        else:
            end_dt = start_dt + timedelta(hours=1)

        return start_dt.isoformat(), end_dt.isoformat(), False

    range_end = entry.end_date if entry.end_date else entry.date
    return entry.date.isoformat(), (range_end + timedelta(days=1)).isoformat(), True


def task_applies_to_day(task, day_name, day_date):
    start_raw = task.get("start_date", "")
    end_raw = task.get("end_date", "")
    if start_raw and end_raw:
        try:
            start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
            return start_date <= day_date <= end_date
        except ValueError:
            pass

    start_index = TODO_DAY_INDEX.get(task.get("start_day", ""), 0)
    end_index = TODO_DAY_INDEX.get(task.get("end_day", ""), start_index)
    day_index = TODO_DAY_INDEX.get(day_name, 0)
    if end_index < start_index:
        start_index, end_index = end_index, start_index
    return start_index <= day_index <= end_index


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


def get_todo_tasks_by_day(request, week_dates=None):
    if week_dates is None:
        _, week_dates = get_todo_week_dates(request)

    tasks_by_day = {}
    for day_name, _ in TODO_DAYS:
        tasks_by_day[day_name] = {}
        for section_key, _, _ in TODO_SECTION_CONFIG:
            tasks_by_day[day_name][section_key] = []

    for item in get_todo_task_items(request):
        for day_info in week_dates:
            if task_applies_to_day(item, day_info["name"], day_info["date"]):
                tasks_by_day[day_info["name"]][item["section"]].append(item)

    return tasks_by_day


def sync_notes_box_completed_state(request, task_item):
    if not isinstance(task_item, dict):
        return

    if task_item.get('source') != 'notes_canvas':
        return

    source_week = str(task_item.get('source_week', '')).strip()
    source_box_id = str(task_item.get('source_box_id', '')).strip()
    if not source_week or not source_box_id:
        return

    notes_canvas_by_week = request.session.get('notes_canvas_by_week', {})
    if not isinstance(notes_canvas_by_week, dict):
        return

    week_state = notes_canvas_by_week.get(source_week)
    if not isinstance(week_state, dict):
        return

    boxes = week_state.get('boxes', [])
    if not isinstance(boxes, list):
        return

    completed_value = bool(task_item.get('completed', False))
    changed = False
    for box in boxes:
        if not isinstance(box, dict):
            continue
        if str(box.get('id', '')).strip() != source_box_id:
            continue

        if bool(box.get('completed', False)) != completed_value:
            box['completed'] = completed_value
            changed = True
        break

    if changed:
        notes_canvas_by_week[source_week] = week_state
        request.session['notes_canvas_by_week'] = notes_canvas_by_week
        request.session.modified = True

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
        start_value, end_value, all_day = diary_entry_to_calendar_values(entry)

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
        start_value, end_value, all_day = diary_entry_to_calendar_values(entry)

        data.append({
            "id": entry.id,
            "title": entry.title,
            "start": start_value,
            "end": end_value,
            "allDay": all_day,
            "description": entry.content,
            "formEndDate": (entry.end_date.isoformat() if entry.end_date else entry.date.isoformat()) if all_day else '',
            "formStartTime": entry.start_time.strftime('%H:%M') if entry.start_time else '',
            "formEndTime": entry.end_time.strftime('%H:%M') if entry.end_time else '',
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
    week_start, week_dates = get_todo_week_dates(request)
    week_end = week_start + timedelta(days=6)
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    if request.method == 'POST' and request.POST.get('form_type') == 'update_section_titles':
        updated_titles = {}
        for section in todo_sections:
            raw_value = request.POST.get(f"section_{section['key']}", "")
            value = raw_value.strip()[:30]
            updated_titles[section['key']] = value if value else section['default_title']

        request.session['todo_section_titles'] = updated_titles
        request.session.modified = True
        return HttpResponseRedirect(get_todo_return_url(request))

    if request.method == 'POST' and request.POST.get('form_type') == 'add_todo_entry':
        task_title = request.POST.get('task_title', '').strip()
        task_start_date_raw = request.POST.get('task_start_date', '').strip()
        task_end_date_raw = request.POST.get('task_end_date', '').strip()
        task_section = request.POST.get('task_section', '').strip()
        task_notes = request.POST.get('task_notes', '').strip()
        task_priority = request.POST.get('task_priority', '').strip().lower()
        task_completed = request.POST.get('task_completed') == 'on'

        valid_days = {day_name for day_name, _ in TODO_DAYS}
        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_title:
            return HttpResponseRedirect(get_todo_return_url(request))

        if task_section not in valid_sections:
            return HttpResponseRedirect(get_todo_return_url(request))

        try:
            task_start_date = datetime.strptime(task_start_date_raw, "%Y-%m-%d").date()
            task_end_date = datetime.strptime(task_end_date_raw, "%Y-%m-%d").date()
        except ValueError:
            return HttpResponseRedirect(get_todo_return_url(request))

        if task_end_date < task_start_date:
            task_start_date, task_end_date = task_end_date, task_start_date

        task_start_day = task_start_date.strftime("%A")
        task_end_day = task_end_date.strftime("%A")

        if task_start_day not in valid_days or task_end_day not in valid_days:
            return HttpResponseRedirect(get_todo_return_url(request))

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
            "start_date": task_start_date.isoformat(),
            "end_date": task_end_date.isoformat(),
        }

        task_items = get_todo_task_items(request)
        task_items.append(normalize_todo_task_item(task_value, default_day=task_start_day, default_section=task_section))

        request.session['todo_task_items'] = task_items
        request.session.modified = True
        return HttpResponseRedirect(get_todo_return_url(request))

    if request.method == 'POST' and request.POST.get('form_type') in ('edit_todo_entry', 'delete_todo_entry', 'toggle_todo_completed'):
        form_type = request.POST.get('form_type')
        task_id = request.POST.get('task_id', '').strip()

        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_id:
            return HttpResponseRedirect(get_todo_return_url(request))

        task_items = get_todo_task_items(request)
        task_pos = next((index for index, item in enumerate(task_items) if item.get('id') == task_id), -1)
        if task_pos == -1:
            return HttpResponseRedirect(get_todo_return_url(request))

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
            existing_task = task_items[task_pos]
            updated_title = request.POST.get('task_title', '').strip()[:120]
            updated_notes = request.POST.get('task_notes', '').strip()[:180]
            updated_priority = request.POST.get('task_priority', '').strip().lower()
            updated_completed = request.POST.get('task_completed') == 'on'
            updated_section = request.POST.get('task_section', '').strip().lower()
            updated_start_date_raw = request.POST.get('task_start_date', '').strip()
            updated_end_date_raw = request.POST.get('task_end_date', '').strip()

            if updated_priority not in TODO_PRIORITY_CHOICES:
                updated_priority = 'medium'

            if updated_section not in valid_sections:
                updated_section = 'planning'

            try:
                updated_start_date = datetime.strptime(updated_start_date_raw, "%Y-%m-%d").date()
                updated_end_date = datetime.strptime(updated_end_date_raw, "%Y-%m-%d").date()
            except ValueError:
                return HttpResponseRedirect(get_todo_return_url(request))

            if updated_end_date < updated_start_date:
                updated_start_date, updated_end_date = updated_end_date, updated_start_date

            updated_start_day = updated_start_date.strftime("%A")
            updated_end_day = updated_end_date.strftime("%A")

            if not updated_title:
                return HttpResponseRedirect(get_todo_return_url(request))

            task_items[task_pos] = {
                "id": task_id,
                "title": updated_title,
                "notes": updated_notes,
                "priority": updated_priority,
                "completed": updated_completed,
                "section": updated_section,
                "start_day": updated_start_day,
                "end_day": updated_end_day,
                "start_date": updated_start_date.isoformat(),
                "end_date": updated_end_date.isoformat(),
                "source": existing_task.get('source', ''),
                "source_week": existing_task.get('source_week', ''),
                "source_box_id": existing_task.get('source_box_id', ''),
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

        if form_type in ('edit_todo_entry', 'toggle_todo_completed'):
            updated_item = next((item for item in normalized_items if item.get('id') == task_id), None)
            if updated_item:
                sync_notes_box_completed_state(request, updated_item)

        request.session['todo_task_items'] = normalized_items
        request.session.modified = True
        return HttpResponseRedirect(get_todo_return_url(request))

    todo_sections = get_todo_sections(request)
    tasks_by_day = get_todo_tasks_by_day(request, week_dates=week_dates)

    day_lists = []
    day_info_by_name = {item["name"]: item for item in week_dates}
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
                "date_iso": day_info_by_name[day_name]["date_iso"],
                "date_label": day_info_by_name[day_name]["date_label"],
                "sections": sections,
            }
        )

    return render(
        request,
        'dashboard/todo.html',
        {
            "day_lists": day_lists,
            "todo_sections": todo_sections,
            "week_start_iso": week_start.isoformat(),
            "week_range_label": f"{week_start.strftime('%d %b %Y')} to {week_end.strftime('%d %b %Y')}",
            "prev_week_iso": prev_week.isoformat(),
            "next_week_iso": next_week.isoformat(),
            "today_iso": datetime.today().date().isoformat(),
        },
    )


@login_required
def notes_view(request):
    today = datetime.today().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_key = week_start.isoformat()
    todo_sections = get_todo_sections(request)

    note_type_options = ['Note']
    note_type_colors = {'Note': '#F6C35C'}
    seen_titles = {'Note'.casefold()}
    for section in todo_sections:
        title = section.get('title', '')
        section_key = section.get('key', '')
        if not isinstance(title, str):
            continue
        title = title.strip()[:30]
        if not title:
            continue

        title_key = title.casefold()
        if title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        note_type_options.append(title)
        note_type_colors[title] = TODO_SECTION_COLORS.get(section_key, '#00C2FF')

    allowed_note_types = set(note_type_options)
    section_title_to_key = {
        str(section.get('title', '')).strip().casefold(): section.get('key')
        for section in todo_sections
        if isinstance(section.get('title'), str) and section.get('title', '').strip()
    }

    notes_canvas_by_week = request.session.get('notes_canvas_by_week', {})
    if not isinstance(notes_canvas_by_week, dict):
        notes_canvas_by_week = {}

    def get_default_canvas_state():
        return {
            'boxes': [
                {
                    'id': str(uuid4()),
                    'x': 70,
                    'y': 70,
                    'w': 360,
                    'h': 150,
                    'type': 'Note',
                    'note_date': week_start.isoformat(),
                    'completed': False,
                    'text': '',
                }
            ],
            'links': [],
        }

    def sanitize_canvas_state(raw_value):
        default_state = get_default_canvas_state()
        if not isinstance(raw_value, dict):
            return default_state

        raw_boxes = raw_value.get('boxes', [])
        raw_links = raw_value.get('links', [])
        if not isinstance(raw_boxes, list):
            raw_boxes = []
        if not isinstance(raw_links, list):
            raw_links = []

        boxes = []
        box_ids = set()
        for item in raw_boxes[:60]:
            if not isinstance(item, dict):
                continue

            box_id = str(item.get('id', '')).strip()
            if not box_id:
                box_id = str(uuid4())
            if box_id in box_ids:
                continue

            try:
                x = int(float(item.get('x', 0)))
                y = int(float(item.get('y', 0)))
                w = int(float(item.get('w', 360)))
                h = int(float(item.get('h', 150)))
            except (TypeError, ValueError):
                continue

            x = max(0, min(x, 2400))
            y = max(0, min(y, 2400))
            w = max(320, min(w, 700))
            h = max(120, min(h, 520))

            text = item.get('text', '')
            if not isinstance(text, str):
                text = ''
            text = text[:1200]

            box_type = item.get('type', 'Note')
            if not isinstance(box_type, str):
                box_type = 'Note'
            box_type = box_type.strip()[:30]
            if box_type not in allowed_note_types:
                box_type = 'Note'

            completed = bool(item.get('completed', False))

            note_date_value = str(item.get('note_date', '')).strip()
            parsed_note_date = None
            if note_date_value:
                try:
                    parsed_note_date = datetime.strptime(note_date_value, '%Y-%m-%d').date()
                except ValueError:
                    parsed_note_date = None
            if parsed_note_date is None or parsed_note_date < week_start or parsed_note_date > week_end:
                parsed_note_date = week_start

            box_ids.add(box_id)
            boxes.append(
                {
                    'id': box_id,
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'type': box_type,
                    'note_date': parsed_note_date.isoformat(),
                    'completed': completed,
                    'text': text,
                }
            )

        if not boxes:
            boxes = default_state['boxes']
            box_ids = {boxes[0]['id']}

        links = []
        seen_links = set()
        for item in raw_links[:160]:
            if not isinstance(item, dict):
                continue

            from_id = str(item.get('from', '')).strip()
            to_id = str(item.get('to', '')).strip()
            if from_id == to_id:
                continue
            if from_id not in box_ids or to_id not in box_ids:
                continue

            key = (from_id, to_id)
            if key in seen_links:
                continue
            seen_links.add(key)
            links.append({'from': from_id, 'to': to_id})

        return {'boxes': boxes, 'links': links}

    def build_weekly_note_tasks(canvas_state):
        generated_items = []
        for box in canvas_state.get('boxes', []):
            if not isinstance(box, dict):
                continue

            box_type = str(box.get('type', 'Note')).strip()
            if not box_type or box_type == 'Note':
                continue

            section_key = section_title_to_key.get(box_type.casefold())
            if not section_key:
                continue

            raw_text = box.get('text', '')
            if not isinstance(raw_text, str):
                continue

            clean_text = raw_text.strip()
            if not clean_text:
                continue

            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
            if not lines:
                continue

            title = lines[0][:120]
            notes = ' '.join(lines[1:])[:180]
            if not title:
                continue

            note_date_raw = str(box.get('note_date', '')).strip()
            try:
                note_date = datetime.strptime(note_date_raw, '%Y-%m-%d').date()
            except ValueError:
                note_date = week_start
            if note_date < week_start or note_date > week_end:
                note_date = week_start

            raw_item = {
                'id': str(uuid4()),
                'title': title,
                'notes': notes,
                'priority': 'medium',
                'completed': bool(box.get('completed', False)),
                'section': section_key,
                'start_day': note_date.strftime('%A'),
                'end_day': note_date.strftime('%A'),
                'start_date': note_date.isoformat(),
                'end_date': note_date.isoformat(),
                'source': 'notes_canvas',
                'source_week': week_key,
                'source_box_id': str(box.get('id', '')).strip()[:80],
            }

            normalized = normalize_todo_task_item(raw_item, default_day=week_start.strftime('%A'), default_section=section_key)
            if normalized:
                generated_items.append(normalized)

        return generated_items

    if request.method == 'POST':
        canvas_raw = request.POST.get('canvas_data', '').strip()
        try:
            parsed = json.loads(canvas_raw) if canvas_raw else None
        except json.JSONDecodeError:
            parsed = None

        current_canvas_state = sanitize_canvas_state(parsed)
        notes_canvas_by_week[week_key] = current_canvas_state
        request.session['notes_canvas_by_week'] = notes_canvas_by_week

        task_items = get_todo_task_items(request)
        retained_items = []
        for item in task_items:
            if not isinstance(item, dict):
                continue

            is_notes_week_item = (
                item.get('source') == 'notes_canvas'
                and item.get('source_week') == week_key
            )
            if not is_notes_week_item:
                retained_items.append(item)

        retained_items.extend(build_weekly_note_tasks(current_canvas_state))
        request.session['todo_task_items'] = retained_items

        request.session.modified = True
        return HttpResponseRedirect(reverse('notes'))

    current_state = sanitize_canvas_state(notes_canvas_by_week.get(week_key))
    context = {
        'canvas_data_json': json.dumps(current_state),
        'note_type_options_json': json.dumps(note_type_options),
        'note_type_colors_json': json.dumps(note_type_colors),
        'week_start_iso': week_start.isoformat(),
        'week_end_iso': week_end.isoformat(),
        'week_range_label': f"{week_start.strftime('%d %b %Y')} to {week_end.strftime('%d %b %Y')}",
    }
    return render(request, 'dashboard/notes.html', context)

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
                if parsed_end and not parsed_start:
                    parsed_start = time(0, 0)
            except ValueError:
                messages.error(request, 'Invalid date/time format. Please check your values.')
                return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

            if parsed_end_date and parsed_end_date < parsed_date:
                messages.error(request, 'End date must be on or after start date.')
                return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")

            # Multi-day range applies to all-day entries only.
            # If end date is blank, default to the same day (single-day all-day entry).
            effective_end_date = (parsed_end_date or parsed_date) if (not parsed_start and not parsed_end) else None

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
                # For timed entries with a date range, create one entry per day in the range.
                if (parsed_start or parsed_end) and parsed_end_date and parsed_end_date > parsed_date:
                    current_date = parsed_date
                    created_count = 0
                    while current_date <= parsed_end_date:
                        DiaryEntry.objects.create(
                            user=request.user,
                            title=title,
                            date=current_date,
                            end_date=None,
                            start_time=parsed_start,
                            end_time=parsed_end,
                            content=content or ''
                        )
                        created_count += 1
                        current_date = current_date + timedelta(days=1)

                    messages.success(request, f'{created_count} diary entries added successfully!')
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


@login_required
def delete_diary_entry(request):
    if request.method != 'POST':
        return HttpResponseRedirect(reverse('diary'))

    entry_id = request.POST.get('entry_id', '').strip()
    redirect_date = request.POST.get('redirect_date', '').strip()

    if not redirect_date:
        redirect_date = datetime.today().date().isoformat()

    diary_entry = DiaryEntry.objects.filter(id=entry_id, user=request.user).first()
    if diary_entry:
        if diary_entry.date:
            redirect_date = diary_entry.date.isoformat()
        diary_entry.delete()
        messages.success(request, 'Diary entry deleted successfully!')
    else:
        messages.error(request, 'Diary entry not found.')

    return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")
