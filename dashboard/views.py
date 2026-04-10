# dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from datetime import datetime, timedelta, time
from .models import Event, DiaryEntry, UserPreference, TodoSectionTitle, TodoTask, NotesCanvasWeek, NoteCategory, NoteEntry
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings
from uuid import uuid4
import json
import re
from types import SimpleNamespace

from .forms import SignUpForm, SettingsForm, AccountEmailForm

TODO_SECTION_CONFIG = [
    ("planning", "Planning", "todo-section-planning"),
    ("next", "Next Up", "todo-section-next"),
    ("progress", "In Progress", "todo-section-progress"),
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

TODO_MAX_NOTES_LENGTH = 2000
TODO_MAX_CHECKLIST_ITEMS = 30
TODO_MAX_CHECKLIST_TEXT_LENGTH = 120

TODO_SECTION_COLORS = {
    "planning": "#38BDF8",
    "next": "#A3E635",
    "progress": "#FACC15",
    "done": "#34D399",
}

DIARY_CATEGORY_CONFIG = [
    ("general", "General", "#38BDF8"),
    ("work", "Work", "#A3E635"),
    ("personal", "Personal", "#FACC15"),
    ("health", "Health", "#FB7185"),
    ("travel", "Travel", "#34D399"),
]

DIARY_CATEGORY_LABELS = {key: label for key, label, _ in DIARY_CATEGORY_CONFIG}
DIARY_CATEGORY_COLORS = {key: color for key, _, color in DIARY_CATEGORY_CONFIG}
DIARY_DEFAULT_CATEGORY = "general"


def normalize_nav_layout(value):
    candidate = str(value or '').strip().lower()
    if candidate == 'bottom':
        return 'bottom'
    return 'top'


def normalize_diary_category(value):
    candidate = str(value or "").strip().lower()
    return candidate if candidate in DIARY_CATEGORY_LABELS else DIARY_DEFAULT_CATEGORY


def get_diary_category_options():
    return [
        {
            "key": key,
            "label": label,
            "color": color,
        }
        for key, label, color in DIARY_CATEGORY_CONFIG
    ]


def get_todo_sections(request):
    try:
        custom_titles = {
            row.section_key: row.title
            for row in TodoSectionTitle.objects.filter(user=request.user)
        }
    except (OperationalError, ProgrammingError):
        custom_titles = {}

    if not custom_titles:
        session_titles = request.session.get("todo_section_titles", {})
        if isinstance(session_titles, dict):
            try:
                for section_key, title in session_titles.items():
                    if not isinstance(title, str):
                        continue
                    TodoSectionTitle.objects.update_or_create(
                        user=request.user,
                        section_key=section_key,
                        defaults={"title": title.strip()[:30]},
                    )
                custom_titles = {
                    row.section_key: row.title
                    for row in TodoSectionTitle.objects.filter(user=request.user)
                }
            except (OperationalError, ProgrammingError):
                custom_titles = {
                    key: str(value).strip()[:30]
                    for key, value in session_titles.items()
                    if isinstance(value, str)
                }

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


def set_todo_section_titles(request, titles_by_key):
    valid_section_keys = {key for key, _, _ in TODO_SECTION_CONFIG}
    session_titles = request.session.get('todo_section_titles', {})
    if not isinstance(session_titles, dict):
        session_titles = {}

    for section_key, title in titles_by_key.items():
        if section_key not in valid_section_keys:
            continue

        clean_title = str(title).strip()[:30]
        session_titles[section_key] = clean_title
        try:
            TodoSectionTitle.objects.update_or_create(
                user=request.user,
                section_key=section_key,
                defaults={"title": clean_title},
            )
        except (OperationalError, ProgrammingError):
            continue

    request.session['todo_section_titles'] = session_titles
    request.session.modified = True


def get_default_todo_seed():
    return {}


def normalize_todo_task(raw_task):
    if isinstance(raw_task, dict):
        title = str(raw_task.get("title", "")).strip()[:120]
        notes = str(raw_task.get("notes", "")).strip()[:TODO_MAX_NOTES_LENGTH]
        priority = str(raw_task.get("priority", "medium")).strip().lower()
        completed = bool(raw_task.get("completed", False))
        checklist = sanitize_task_checklist(raw_task.get("checklist", []))
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
        checklist = []
    else:
        return None

    if not title:
        return None

    if priority not in TODO_PRIORITY_CHOICES:
        priority = "medium"

    return {
        "title": title,
        "notes": notes,
        "checklist": checklist,
        "priority": priority,
        "priority_label": TODO_PRIORITY_CHOICES[priority],
        "completed": completed,
    }


def sanitize_task_checklist(raw_value):
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except (TypeError, ValueError):
            raw_value = []

    if not isinstance(raw_value, list):
        return []

    cleaned_items = []
    for item in raw_value[:TODO_MAX_CHECKLIST_ITEMS]:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            completed = bool(item.get("completed", False))
        else:
            text = str(item).strip()
            completed = False

        if not text:
            continue

        cleaned_items.append(
            {
                "text": text[:TODO_MAX_CHECKLIST_TEXT_LENGTH],
                "completed": completed,
            }
        )

    return cleaned_items


def normalize_todo_task_item(raw_item, default_day=None, default_section="planning"):
    if not isinstance(raw_item, dict):
        return None

    title = str(raw_item.get("title", "")).strip()[:120]
    if not title:
        return None

    notes = str(raw_item.get("notes", "")).strip()[:TODO_MAX_NOTES_LENGTH]
    checklist = sanitize_task_checklist(raw_item.get("checklist", []))
    priority = str(raw_item.get("priority", "medium")).strip().lower()
    if priority not in TODO_PRIORITY_CHOICES:
        priority = "medium"

    section = str(raw_item.get("section", default_section)).strip().lower()
    valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}
    if section == "review":
        section = "progress"
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
        "checklist": checklist,
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


def parse_task_date(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def format_task_date_range(start_date, end_date):
    if start_date and end_date:
        if start_date == end_date:
            return start_date.strftime("%d %b %Y")
        return f"{start_date.strftime('%d %b')} to {end_date.strftime('%d %b %Y')}"
    if start_date:
        return start_date.strftime("%d %b %Y")
    if end_date:
        return end_date.strftime("%d %b %Y")
    return "No date"


def sync_todo_task_diary_entry(request, task_item, diary_category=None):
    if not isinstance(task_item, dict):
        return task_item

    if task_item.get('source') == 'notes_canvas':
        return task_item

    start_date = parse_task_date(task_item.get('start_date'))
    end_date = parse_task_date(task_item.get('end_date'))
    if start_date and not end_date:
        end_date = start_date
    if end_date and not start_date:
        start_date = end_date

    if not start_date:
        return task_item

    if end_date and end_date < start_date:
        start_date, end_date = end_date, start_date

    title = str(task_item.get('title', '')).strip()[:200]
    if not title:
        return task_item

    content = str(task_item.get('notes', '')).strip()
    checklist_items = sanitize_task_checklist(task_item.get('checklist', []))
    if checklist_items:
        checklist_lines = [
            f"- [{'x' if item.get('completed') else ' '}] {item.get('text', '')}".rstrip()
            for item in checklist_items
        ]
        checklist_block = "Checklist:\n" + "\n".join(checklist_lines)
        content = f"{content}\n\n{checklist_block}".strip() if content else checklist_block
    category_key = normalize_diary_category(diary_category)
    diary_id_raw = str(task_item.get('source_box_id', '')).strip()
    diary_entry = None

    if task_item.get('source') == 'todo_diary' and diary_id_raw.isdigit():
        diary_entry = DiaryEntry.objects.filter(user=request.user, id=int(diary_id_raw)).first()

    if diary_entry:
        diary_entry.title = title
        diary_entry.category = category_key
        diary_entry.date = start_date
        diary_entry.end_date = end_date
        diary_entry.start_time = None
        diary_entry.end_time = None
        diary_entry.content = content
        diary_entry.save()
        diary_id = diary_entry.id
    else:
        diary_entry = DiaryEntry.objects.create(
            user=request.user,
            title=title,
            category=category_key,
            date=start_date,
            end_date=end_date,
            start_time=None,
            end_time=None,
            content=content,
        )
        diary_id = diary_entry.id

    task_item['source'] = 'todo_diary'
    task_item['source_week'] = ''
    task_item['source_box_id'] = str(diary_id)
    return normalize_todo_task_item(task_item)


def remove_todo_task_diary_entry(request, task_item):
    if not isinstance(task_item, dict):
        return

    if task_item.get('source') != 'todo_diary':
        return

    diary_id_raw = str(task_item.get('source_box_id', '')).strip()
    if not diary_id_raw.isdigit():
        return

    DiaryEntry.objects.filter(user=request.user, id=int(diary_id_raw)).delete()


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
    return_task_id = request.POST.get("return_task_id", "").strip()

    query_parts = []
    if return_date:
        try:
            datetime.strptime(return_date, "%Y-%m-%d")
            query_parts.append(f"date={return_date}")
        except ValueError:
            pass

    if return_task_id:
        query_parts.append(f"task_id={return_task_id}")

    if query_parts:
        return f"{reverse('todo')}?{'&'.join(query_parts)}"

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
    db_available = False
    try:
        db_items = TodoTask.objects.filter(user=request.user).order_by('created_at')
        db_available = True
        if db_items.exists():
            task_items = []
            for row in db_items:
                task_items.append(
                    normalize_todo_task_item(
                        {
                            "id": row.task_id,
                            "title": row.title,
                            "notes": row.notes,
                            "checklist": row.checklist_data,
                            "priority": row.priority,
                            "completed": row.completed,
                            "section": row.section,
                            "start_day": row.start_day,
                            "end_day": row.end_day,
                            "start_date": row.start_date.isoformat() if row.start_date else "",
                            "end_date": row.end_date.isoformat() if row.end_date else "",
                            "source": row.source,
                            "source_week": row.source_week,
                            "source_box_id": row.source_box_id,
                        }
                    )
                )
            return [item for item in task_items if item]
    except (OperationalError, ProgrammingError):
        pass

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
                            "checklist": normalized_task.get("checklist", []),
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

    # If DB is reachable but empty, backfill from session so logout does not erase To Do data.
    should_persist = changed or (db_available and bool(task_items))
    if should_persist:
        set_todo_task_items(request, task_items)

    return task_items


def set_todo_task_items(request, task_items):
    normalized_items = []
    for item in task_items:
        normalized = normalize_todo_task_item(item)
        if normalized:
            normalized_items.append(normalized)

    try:
        TodoTask.objects.filter(user=request.user).delete()
    except (OperationalError, ProgrammingError):
        request.session['todo_task_items'] = normalized_items
        request.session.modified = True
        return
    create_rows = []
    for item in normalized_items:
        start_date_value = None
        end_date_value = None
        if item.get('start_date'):
            try:
                start_date_value = datetime.strptime(item['start_date'], '%Y-%m-%d').date()
            except ValueError:
                start_date_value = None
        if item.get('end_date'):
            try:
                end_date_value = datetime.strptime(item['end_date'], '%Y-%m-%d').date()
            except ValueError:
                end_date_value = None

        create_rows.append(
            TodoTask(
                user=request.user,
                task_id=item['id'],
                title=item['title'],
                notes=item['notes'],
                checklist_data=item.get('checklist', []),
                priority=item['priority'],
                completed=item['completed'],
                section=item['section'],
                start_day=item['start_day'],
                end_day=item['end_day'],
                start_date=start_date_value,
                end_date=end_date_value,
                source=item.get('source', ''),
                source_week=item.get('source_week', ''),
                source_box_id=item.get('source_box_id', ''),
            )
        )

    if create_rows:
        try:
            TodoTask.objects.bulk_create(create_rows)
        except (OperationalError, ProgrammingError):
            request.session['todo_task_items'] = normalized_items
            request.session.modified = True
            return

    request.session['todo_task_items'] = normalized_items
    request.session.modified = True


def get_notes_canvas_by_week(request):
    try:
        rows = NotesCanvasWeek.objects.filter(user=request.user)
        if rows.exists():
            return {
                row.week_start.isoformat(): row.canvas_data
                for row in rows
                if isinstance(row.canvas_data, dict)
            }
    except (OperationalError, ProgrammingError):
        pass

    session_map = request.session.get('notes_canvas_by_week', {})
    notes_canvas_by_week = session_map if isinstance(session_map, dict) else {}
    for week_key, canvas in notes_canvas_by_week.items():
        if not isinstance(canvas, dict):
            continue
        try:
            parsed_week = datetime.strptime(str(week_key), '%Y-%m-%d').date()
        except ValueError:
            continue
        try:
            NotesCanvasWeek.objects.update_or_create(
                user=request.user,
                week_start=parsed_week,
                defaults={'canvas_data': canvas},
            )
        except (OperationalError, ProgrammingError):
            break

    return notes_canvas_by_week


def set_notes_canvas_week(request, week_key, canvas_state):
    try:
        parsed_week = datetime.strptime(str(week_key), '%Y-%m-%d').date()
    except ValueError:
        return

    try:
        NotesCanvasWeek.objects.update_or_create(
            user=request.user,
            week_start=parsed_week,
            defaults={'canvas_data': canvas_state},
        )
    except (OperationalError, ProgrammingError):
        session_map = request.session.get('notes_canvas_by_week', {})
        if not isinstance(session_map, dict):
            session_map = {}
        session_map[str(week_key)] = canvas_state
        request.session['notes_canvas_by_week'] = session_map
        request.session.modified = True


def get_user_preferences(request):
    try:
        preferences, _ = UserPreference.objects.get_or_create(user=request.user)
        normalized_layout = normalize_nav_layout(getattr(preferences, 'nav_layout', 'top'))
        if preferences.nav_layout != normalized_layout:
            preferences.nav_layout = normalized_layout
            try:
                preferences.save(update_fields=['nav_layout', 'updated_at'])
            except (OperationalError, ProgrammingError):
                pass
        return preferences
    except (OperationalError, ProgrammingError):
        session_prefs = request.session.get('user_preferences', {})
        if not isinstance(session_prefs, dict):
            session_prefs = {}
        nav_layout = normalize_nav_layout(session_prefs.get('nav_layout', 'top'))
        if session_prefs.get('nav_layout') != nav_layout:
            session_prefs['nav_layout'] = nav_layout
            request.session['user_preferences'] = session_prefs
            request.session.modified = True
        return SimpleNamespace(
            theme=session_prefs.get('theme', 'dark'),
            nav_layout=nav_layout,
            default_diary_view=session_prefs.get('default_diary_view', 'week'),
        )


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

    notes_canvas_by_week = get_notes_canvas_by_week(request)

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
        set_notes_canvas_week(request, source_week, week_state)

@login_required
def dashboard_view(request):
    preferences = get_user_preferences(request)
    # Keep "Up & Coming" focused on future and not-yet-finished entries.
    now = datetime.now()
    today = now.date()
    current_time = now.time()

    base_queryset = (
        DiaryEntry.objects.filter(user=request.user)
        .filter(Q(end_date__gte=today) | Q(end_date__isnull=True, date__gte=today))
        .order_by('date', 'start_time', 'created_at')
    )

    upcoming_entries = []
    for entry in base_queryset:
        entry_end_date = entry.end_date if entry.end_date else entry.date
        if entry_end_date > today:
            upcoming_entries.append(entry)
            continue

        if entry.start_time is None and entry.end_time is None:
            # Keep all-day items for today in the upcoming list.
            upcoming_entries.append(entry)
            continue

        effective_end_time = entry.end_time if entry.end_time else entry.start_time
        if effective_end_time and effective_end_time >= current_time:
            upcoming_entries.append(entry)

    diary_entries = upcoming_entries[:6]
    for entry in diary_entries:
        category_key = normalize_diary_category(getattr(entry, 'category', DIARY_DEFAULT_CATEGORY))
        entry.category_key = category_key
        entry.category_label = DIARY_CATEGORY_LABELS.get(category_key, DIARY_CATEGORY_LABELS[DIARY_DEFAULT_CATEGORY])
        entry.category_color = DIARY_CATEGORY_COLORS.get(category_key, DIARY_CATEGORY_COLORS[DIARY_DEFAULT_CATEGORY])

    todo_sections = get_todo_sections(request)
    task_items = get_todo_task_items(request)
    todo_columns = []
    for section in todo_sections:
        section_tasks = [
            item
            for item in task_items
            if item["section"] == section["key"] and item.get("priority") in {"high", "medium"}
        ]

        display_tasks = []
        for task in section_tasks[:6]:
            display_tasks.append(
                {
                    "id": task.get("id", ""),
                    "title": task.get("title", ""),
                    "completed": bool(task.get("completed", False)),
                    "is_placeholder": False,
                }
            )

        if not display_tasks:
            display_tasks = [
                {
                    "id": "",
                    "title": "No entries yet",
                    "completed": False,
                    "is_placeholder": True,
                }
            ]

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
        'nav_layout': preferences.nav_layout,
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
        category_key = normalize_diary_category(getattr(entry, 'category', DIARY_DEFAULT_CATEGORY))
        category_color = DIARY_CATEGORY_COLORS.get(category_key, DIARY_CATEGORY_COLORS[DIARY_DEFAULT_CATEGORY])

        data.append({
            "id": f"diary-{entry.id}",
            "title": entry.title,
            "start": start_value,
            "end": end_value,
            "allDay": all_day,
            "source": "diary",
            "backgroundColor": category_color,
            "borderColor": category_color,
            "textColor": "#06111E",
        })

    return JsonResponse(data, safe=False)

@login_required
def diary_api(request):
    # Return diary entries as events for FullCalendar
    diary_entries = DiaryEntry.objects.filter(user=request.user)
    data = []
    for entry in diary_entries:
        start_value, end_value, all_day = diary_entry_to_calendar_values(entry)
        category_key = normalize_diary_category(getattr(entry, 'category', DIARY_DEFAULT_CATEGORY))
        category_color = DIARY_CATEGORY_COLORS.get(category_key, DIARY_CATEGORY_COLORS[DIARY_DEFAULT_CATEGORY])

        data.append({
            "id": entry.id,
            "title": entry.title,
            "start": start_value,
            "end": end_value,
            "allDay": all_day,
            "description": entry.content,
            "category": category_key,
            "formCategory": category_key,
            "categoryLabel": DIARY_CATEGORY_LABELS.get(category_key, DIARY_CATEGORY_LABELS[DIARY_DEFAULT_CATEGORY]),
            "categoryColor": category_color,
            "formEndDate": (entry.end_date.isoformat() if entry.end_date else entry.date.isoformat()) if all_day else '',
            "formStartTime": entry.start_time.strftime('%H:%M') if entry.start_time else '',
            "formEndTime": entry.end_time.strftime('%H:%M') if entry.end_time else '',
            "backgroundColor": category_color,
            "borderColor": category_color,
            "textColor": "#06111E",
        })
    return JsonResponse(data, safe=False)

@login_required
def diary_view(request):
    # Diary page with week view
    diary_entries = DiaryEntry.objects.filter(user=request.user).order_by('-date', '-start_time', '-created_at')
    preferences = get_user_preferences(request)
    context = {
        "diary_entries": diary_entries,
        "diary_category_options": get_diary_category_options(),
        "default_diary_view": preferences.default_diary_view,
        "nav_layout": preferences.nav_layout,
    }
    return render(request, 'dashboard/diary.html', context)


def auth_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    next_url = request.GET.get('next', '').strip()
    active_tab = 'login'

    login_form = AuthenticationForm(request=request)
    signup_form = SignUpForm()

    for field_name in ('username', 'password'):
        login_form.fields[field_name].widget.attrs.update({'class': 'form-control'})

    if request.method == 'POST':
        action = request.POST.get('auth_action', '').strip().lower()
        next_url = request.POST.get('next', '').strip()

        if action == 'signup':
            active_tab = 'signup'
            signup_form = SignUpForm(request.POST)
            if signup_form.is_valid():
                user = signup_form.save()
                try:
                    UserPreference.objects.get_or_create(user=user)
                except (OperationalError, ProgrammingError):
                    pass
                login(request, user)

                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect('dashboard')
        else:
            active_tab = 'login'
            login_form = AuthenticationForm(request=request, data=request.POST)
            for field_name in ('username', 'password'):
                login_form.fields[field_name].widget.attrs.update({'class': 'form-control'})
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)

                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect('dashboard')

    context = {
        'login_form': login_form,
        'signup_form': signup_form,
        'active_tab': active_tab,
        'next_url': next_url,
    }
    return render(request, 'registration/login.html', context)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                UserPreference.objects.get_or_create(user=user)
            except (OperationalError, ProgrammingError):
                pass
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


@login_required
def settings_view(request):
    preferences = get_user_preferences(request)
    open_account = request.GET.get('account', '').strip().lower() in {'1', 'true', 'open'}
    settings_form = SettingsForm(
        initial={
            'nav_layout': preferences.nav_layout,
            'default_diary_view': preferences.default_diary_view,
        }
    )
    email_form = AccountEmailForm(initial={'email': request.user.email}, user=request.user)
    password_form = PasswordChangeForm(request.user)

    for field in password_form.fields.values():
        field.widget.attrs.update({'class': 'form-control'})

    if request.method == 'POST':
        form_type = request.POST.get('form_type', '').strip()

        if form_type == 'update_preferences':
            settings_form = SettingsForm(request.POST)
            if settings_form.is_valid():
                try:
                    preferences.nav_layout = settings_form.cleaned_data['nav_layout']
                    preferences.default_diary_view = settings_form.cleaned_data['default_diary_view']
                    preferences.save(update_fields=['nav_layout', 'default_diary_view', 'updated_at'])
                except (OperationalError, ProgrammingError, AttributeError):
                    session_prefs = request.session.get('user_preferences', {})
                    if not isinstance(session_prefs, dict):
                        session_prefs = {}
                    session_prefs.update(
                        {
                            'nav_layout': settings_form.cleaned_data['nav_layout'],
                            'default_diary_view': settings_form.cleaned_data['default_diary_view'],
                        }
                    )
                    request.session['user_preferences'] = session_prefs
                    request.session.modified = True

                return redirect('settings')

        elif form_type == 'update_email':
            open_account = True
            email_form = AccountEmailForm(request.POST, user=request.user)
            if email_form.is_valid():
                request.user.email = email_form.cleaned_data['email']
                request.user.save(update_fields=['email'])
                return redirect(f"{reverse('settings')}?account=1")

        elif form_type == 'update_password':
            open_account = True
            password_form = PasswordChangeForm(request.user, request.POST)
            for field in password_form.fields.values():
                field.widget.attrs.update({'class': 'form-control'})

            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect(f"{reverse('settings')}?account=1")

    return render(
        request,
        'dashboard/settings.html',
        {
            'settings_form': settings_form,
            'email_form': email_form,
            'password_form': password_form,
            'open_account': open_account,
            'nav_layout': preferences.nav_layout,
            'app_version': getattr(settings, 'FLUID_NOTES_VERSION', 'Fluid Notes v2026.04.10'),
        },
    )


@login_required
def account_view(request):
    return redirect(f"{reverse('settings')}?account=1")

@login_required
def todo_view(request):
    preferences = get_user_preferences(request)
    todo_sections = get_todo_sections(request)
    default_date = datetime.today().date().isoformat()

    if request.method == 'POST' and request.POST.get('form_type') == 'update_section_titles':
        updated_titles = {}
        for section in todo_sections:
            raw_value = request.POST.get(f"section_{section['key']}", "")
            value = raw_value.strip()[:30]
            updated_titles[section['key']] = value if value else section['default_title']

        set_todo_section_titles(request, updated_titles)
        return HttpResponseRedirect(get_todo_return_url(request))

    if request.method == 'POST' and request.POST.get('form_type') == 'add_todo_entry':
        task_title = request.POST.get('task_title', '').strip()
        task_start_date_raw = request.POST.get('task_start_date', '').strip()
        task_end_date_raw = request.POST.get('task_end_date', '').strip()
        task_section = request.POST.get('task_section', '').strip()
        task_notes = request.POST.get('task_notes', '').strip()
        task_checklist_json = request.POST.get('task_checklist_json', '').strip()
        task_priority = request.POST.get('task_priority', '').strip().lower()
        task_completed = request.POST.get('task_completed') == 'on'
        task_add_to_diary = request.POST.get('task_add_to_diary') == 'on'
        task_diary_category = normalize_diary_category(request.POST.get('task_diary_category', DIARY_DEFAULT_CATEGORY))

        try:
            task_checklist_raw = json.loads(task_checklist_json) if task_checklist_json else []
        except (TypeError, ValueError):
            task_checklist_raw = []
        task_checklist = sanitize_task_checklist(task_checklist_raw)

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

        if task_priority not in TODO_PRIORITY_CHOICES:
            task_priority = 'medium'

        task_title = task_title[:120]
        task_notes = task_notes[:TODO_MAX_NOTES_LENGTH]
        task_value = {
            "id": str(uuid4()),
            "title": task_title,
            "notes": task_notes,
            "checklist": task_checklist,
            "priority": task_priority,
            "completed": task_completed,
            "section": task_section,
            "start_day": task_start_day,
            "end_day": task_end_day,
            "start_date": task_start_date.isoformat(),
            "end_date": task_end_date.isoformat(),
        }

        task_items = get_todo_task_items(request)
        new_item = normalize_todo_task_item(task_value, default_day=task_start_day, default_section=task_section)
        if new_item:
            if task_add_to_diary:
                new_item = sync_todo_task_diary_entry(request, new_item, diary_category=task_diary_category)
            if new_item:
                task_items.append(new_item)

        set_todo_task_items(request, task_items)
        return HttpResponseRedirect(get_todo_return_url(request))

    if request.method == 'POST' and request.POST.get('form_type') in ('edit_todo_entry', 'delete_todo_entry', 'toggle_todo_completed', 'toggle_todo_checklist_item'):
        form_type = request.POST.get('form_type')
        task_id = request.POST.get('task_id', '').strip()
        task_add_to_diary = request.POST.get('task_add_to_diary') == 'on'
        task_diary_category = normalize_diary_category(request.POST.get('task_diary_category', DIARY_DEFAULT_CATEGORY))

        valid_sections = {key for key, _, _ in TODO_SECTION_CONFIG}

        if not task_id:
            return HttpResponseRedirect(get_todo_return_url(request))

        task_items = get_todo_task_items(request)
        task_pos = next((index for index, item in enumerate(task_items) if item.get('id') == task_id), -1)
        if task_pos == -1:
            return HttpResponseRedirect(get_todo_return_url(request))

        if form_type == 'delete_todo_entry':
            remove_todo_task_diary_entry(request, task_items[task_pos])
            del task_items[task_pos]
        elif form_type == 'toggle_todo_completed':
            current_task = task_items[task_pos]
            current_task['completed'] = not bool(current_task.get('completed', False))
            task_items[task_pos] = normalize_todo_task_item(
                current_task,
                default_day=current_task.get('start_day', 'Monday'),
                default_section=current_task.get('section', 'planning'),
            )
        elif form_type == 'toggle_todo_checklist_item':
            current_task = task_items[task_pos]
            checklist_items = sanitize_task_checklist(current_task.get('checklist', []))
            checklist_index_raw = request.POST.get('checklist_index', '').strip()
            try:
                checklist_index = int(checklist_index_raw)
            except ValueError:
                checklist_index = -1

            if 0 <= checklist_index < len(checklist_items):
                checklist_items[checklist_index]['completed'] = not bool(checklist_items[checklist_index].get('completed', False))

            current_task['checklist'] = checklist_items
            task_items[task_pos] = normalize_todo_task_item(
                current_task,
                default_day=current_task.get('start_day', 'Monday'),
                default_section=current_task.get('section', 'planning'),
            )
        else:
            existing_task = task_items[task_pos]
            updated_title = request.POST.get('task_title', '').strip()[:120]
            updated_notes = request.POST.get('task_notes', '').strip()[:TODO_MAX_NOTES_LENGTH]
            updated_checklist_json = request.POST.get('task_checklist_json', '').strip()
            try:
                updated_checklist_raw = json.loads(updated_checklist_json) if updated_checklist_json else []
            except (TypeError, ValueError):
                updated_checklist_raw = []
            updated_checklist = sanitize_task_checklist(updated_checklist_raw)
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
                "checklist": updated_checklist,
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

        if form_type == 'edit_todo_entry':
            updated_item = next((item for item in normalized_items if item.get('id') == task_id), None)
            if updated_item:
                if task_add_to_diary:
                    synced_item = sync_todo_task_diary_entry(request, updated_item, diary_category=task_diary_category)
                    if synced_item:
                        normalized_items = [
                            synced_item if item.get('id') == task_id else item
                            for item in normalized_items
                        ]
                else:
                    if updated_item.get('source') == 'todo_diary':
                        remove_todo_task_diary_entry(request, updated_item)

                    unlinked_item = dict(updated_item)
                    unlinked_item['source'] = ''
                    unlinked_item['source_week'] = ''
                    unlinked_item['source_box_id'] = ''

                    normalized_unlinked = normalize_todo_task_item(
                        unlinked_item,
                        default_day=unlinked_item.get('start_day', 'Monday'),
                        default_section=unlinked_item.get('section', 'planning'),
                    )
                    if normalized_unlinked:
                        normalized_items = [
                            normalized_unlinked if item.get('id') == task_id else item
                            for item in normalized_items
                        ]

        set_todo_task_items(request, normalized_items)
        return HttpResponseRedirect(get_todo_return_url(request))

    task_items = get_todo_task_items(request)
    linked_diary_ids = []
    for task in task_items:
        if task.get('source') != 'todo_diary':
            continue
        diary_id_raw = str(task.get('source_box_id', '')).strip()
        if diary_id_raw.isdigit():
            linked_diary_ids.append(int(diary_id_raw))

    diary_category_by_id = {}
    if linked_diary_ids:
        for row in DiaryEntry.objects.filter(user=request.user, id__in=linked_diary_ids).only('id', 'category'):
            diary_category_by_id[row.id] = normalize_diary_category(row.category)

    section_lists = []
    for section in todo_sections:
        section_tasks = [item for item in task_items if item.get('section') == section['key']]

        def task_sort_key(item):
            start_date = parse_task_date(item.get('start_date'))
            end_date = parse_task_date(item.get('end_date'))
            anchor = start_date or end_date
            return (anchor is None, anchor or datetime.max.date(), str(item.get('title', '')).lower())

        section_tasks.sort(key=task_sort_key)

        display_tasks = []
        for task in section_tasks:
            start_date = parse_task_date(task.get('start_date'))
            end_date = parse_task_date(task.get('end_date'))
            display_task = dict(task)
            display_task['checklist'] = sanitize_task_checklist(display_task.get('checklist', []))
            display_task['checklist_json'] = json.dumps(display_task['checklist'])
            display_task['date_range_label'] = format_task_date_range(start_date, end_date)

            linked_diary_category = DIARY_DEFAULT_CATEGORY
            if task.get('source') == 'todo_diary':
                diary_id_raw = str(task.get('source_box_id', '')).strip()
                if diary_id_raw.isdigit():
                    linked_diary_category = diary_category_by_id.get(int(diary_id_raw), DIARY_DEFAULT_CATEGORY)
            display_task['diary_category'] = linked_diary_category

            display_tasks.append(display_task)

        section_lists.append(
            {
                'name': section['title'],
                'key': section['key'],
                'class_name': section['class_name'],
                'tasks': display_tasks,
            }
        )

    return render(
        request,
        'dashboard/todo.html',
        {
            "section_lists": section_lists,
            "todo_sections": todo_sections,
            "today_iso": default_date,
            "nav_layout": preferences.nav_layout,
            "diary_category_options": get_diary_category_options(),
        },
    )


@login_required
def notes_view(request):
    preferences = get_user_preferences(request)
    selected_category_id = str(request.GET.get('category', '')).strip()
    selected_note_id = str(request.GET.get('note', '')).strip()
    search_query = str(request.GET.get('q', '')).strip()[:120]

    def sanitize_note_html(value):
        cleaned = str(value or '')[:30000]
        cleaned = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'\son\w+\s*=\s*(["\']).*?\1', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'\s(href|src)\s*=\s*(["\'])\s*javascript:.*?\2', r' \1="#"', cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned

    if request.method == 'POST':
        notes_action = str(request.POST.get('notes_action', '')).strip().lower()

        if notes_action == 'create_category':
            category_name = str(request.POST.get('category_name', '')).strip()[:40]
            if category_name:
                exists = NoteCategory.objects.filter(user=request.user, name__iexact=category_name).exists()
                if not exists:
                    created_category = NoteCategory.objects.create(user=request.user, name=category_name)
                    return HttpResponseRedirect(f"{reverse('notes')}?category={created_category.id}")
            return HttpResponseRedirect(reverse('notes'))

        if notes_action == 'delete_category':
            category_id = str(request.POST.get('category_id', '')).strip()
            if category_id.isdigit():
                category = NoteCategory.objects.filter(user=request.user, id=int(category_id)).first()
                if category:
                    NoteEntry.objects.filter(user=request.user, category=category).update(category=None)
                    category.delete()
            return HttpResponseRedirect(reverse('notes'))

        if notes_action == 'create_note':
            note_title = str(request.POST.get('new_note_title', '')).strip()[:140]
            if not note_title:
                note_title = 'Untitled note'

            category_id = str(request.POST.get('category_id', '')).strip()
            category = None
            if category_id.isdigit():
                category = NoteCategory.objects.filter(user=request.user, id=int(category_id)).first()

            note = NoteEntry.objects.create(
                user=request.user,
                category=category,
                title=note_title,
                body='',
            )
            return HttpResponseRedirect(f"{reverse('notes')}?note={note.id}")

        if notes_action == 'save_note':
            note_id = str(request.POST.get('note_id', '')).strip()
            note = None
            if note_id.isdigit():
                note = NoteEntry.objects.filter(user=request.user, id=int(note_id)).first()

            if note:
                updated_title = str(request.POST.get('title', '')).strip()[:140]
                if not updated_title:
                    updated_title = 'Untitled note'
                updated_body = sanitize_note_html(request.POST.get('body', ''))

                category_id = str(request.POST.get('category_id', '')).strip()
                category = None
                if category_id.isdigit():
                    category = NoteCategory.objects.filter(user=request.user, id=int(category_id)).first()

                note.title = updated_title
                note.body = updated_body
                note.category = category
                note.save(update_fields=['title', 'body', 'category', 'updated_at'])
                return HttpResponseRedirect(f"{reverse('notes')}?note={note.id}")
            return HttpResponseRedirect(reverse('notes'))

        if notes_action == 'toggle_pin':
            note_id = str(request.POST.get('note_id', '')).strip()
            if note_id.isdigit():
                note = NoteEntry.objects.filter(user=request.user, id=int(note_id)).first()
                if note:
                    note.is_pinned = not bool(note.is_pinned)
                    note.save(update_fields=['is_pinned', 'updated_at'])
                    return HttpResponseRedirect(f"{reverse('notes')}?note={note.id}")
            return HttpResponseRedirect(reverse('notes'))

        if notes_action == 'delete_note':
            note_id = str(request.POST.get('note_id', '')).strip()
            if note_id.isdigit():
                NoteEntry.objects.filter(user=request.user, id=int(note_id)).delete()
            return HttpResponseRedirect(reverse('notes'))

    categories = list(NoteCategory.objects.filter(user=request.user).order_by('name'))
    notes_queryset = NoteEntry.objects.filter(user=request.user).select_related('category')

    active_category = None
    if selected_category_id.isdigit():
        active_category = next((item for item in categories if item.id == int(selected_category_id)), None)
    if active_category:
        notes_queryset = notes_queryset.filter(category=active_category)

    if search_query:
        notes_queryset = notes_queryset.filter(
            Q(title__icontains=search_query)
            | Q(body__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    notes = list(notes_queryset.order_by('-is_pinned', '-updated_at', '-created_at'))

    # Keep Notes from landing on a blank workspace on first use.
    if request.method == 'GET' and not notes and not search_query:
        starter_category = active_category if active_category else None
        starter_note = NoteEntry.objects.create(
            user=request.user,
            category=starter_category,
            title='Untitled note',
            body='<p><br></p>',
        )
        redirect_target = f"{reverse('notes')}?note={starter_note.id}"
        if selected_category_id:
            redirect_target = f"{redirect_target}&category={selected_category_id}"
        return HttpResponseRedirect(redirect_target)

    selected_note = None
    if selected_note_id.isdigit():
        selected_note = next((item for item in notes if item.id == int(selected_note_id)), None)
    if not selected_note and notes:
        selected_note = notes[0]

    context = {
        'categories': categories,
        'notes': notes,
        'selected_note': selected_note,
        'selected_category_id': selected_category_id,
        'search_query': search_query,
        'nav_layout': preferences.nav_layout,
    }
    return render(request, 'dashboard/notes_workspace.html', context)


@login_required
def canvas_view(request):
    preferences = get_user_preferences(request)
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

    notes_canvas_by_week = get_notes_canvas_by_week(request)

    def get_default_canvas_state():
        return {
            'boxes': [
                {
                    'id': str(uuid4()),
                    'x': 70,
                    'y': 70,
                    'w': 360,
                    'h': 150,
                    'title': '',
                    'type': 'Note',
                    'note_date': week_start.isoformat(),
                    'completed': False,
                    'body_html': '',
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
            h = max(200, min(h, 520))

            text = item.get('text', '')
            if not isinstance(text, str):
                text = ''
            text = text[:1200]

            body_html = item.get('body_html', '')
            if not isinstance(body_html, str):
                body_html = ''
            body_html = body_html[:5000]

            title = item.get('title', '')
            if not isinstance(title, str):
                title = ''
            title = title.strip()[:120]

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
                    'title': title,
                    'type': box_type,
                    'note_date': parsed_note_date.isoformat(),
                    'completed': completed,
                    'body_html': body_html,
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

            raw_title = str(box.get('title', '')).strip()
            title = raw_title[:120]

            raw_text = box.get('text', '')
            if not isinstance(raw_text, str):
                continue

            clean_text = raw_text.strip()
            if not title and not clean_text:
                continue

            if not title:
                lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
                if not lines:
                    continue
                title = lines[0].lstrip('-* ').strip()[:120]

            note_lines = []
            checklist_items = []
            for raw_line in clean_text.splitlines():
                stripped_line = raw_line.strip()
                if not stripped_line:
                    continue

                # Convert markdown-like checklist lines into structured checklist data.
                match = re.match(r'^\s*[-*]\s*\[( |x|X)\]\s+(.*)$', raw_line)
                if match:
                    label = str(match.group(2) or '').strip()
                    if label:
                        checklist_items.append(
                            {
                                'text': label[:TODO_MAX_CHECKLIST_TEXT_LENGTH],
                                'completed': str(match.group(1)).lower() == 'x',
                            }
                        )
                    continue

                note_lines.append(stripped_line)

            notes = '\n'.join(note_lines)[:180]

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
                'checklist': checklist_items,
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
        is_auto_save = request.POST.get('auto_save', '').strip() == '1'
        notes_action = request.POST.get('notes_action', '').strip().lower()

        if notes_action == 'clear_canvas':
            set_notes_canvas_week(request, week_key, {'boxes': [], 'links': []})

            task_items = get_todo_task_items(request)
            preserved_items = []
            for item in task_items:
                if not isinstance(item, dict):
                    continue

                is_notes_week_item = (
                    item.get('source') == 'notes_canvas'
                    and item.get('source_week') == week_key
                )
                if not is_notes_week_item:
                    preserved_items.append(item)
                    continue

                converted = dict(item)
                converted['source'] = ''
                converted['source_week'] = ''
                converted['source_box_id'] = ''

                normalized = normalize_todo_task_item(
                    converted,
                    default_day=converted.get('start_day', week_start.strftime('%A')),
                    default_section=converted.get('section', 'planning'),
                )
                if normalized:
                    preserved_items.append(normalized)

            set_todo_task_items(request, preserved_items)
            return HttpResponseRedirect(reverse('canvas'))

        canvas_raw = request.POST.get('canvas_data', '').strip()
        try:
            parsed = json.loads(canvas_raw) if canvas_raw else None
        except json.JSONDecodeError:
            parsed = None

        current_canvas_state = sanitize_canvas_state(parsed)
        set_notes_canvas_week(request, week_key, current_canvas_state)

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
        set_todo_task_items(request, retained_items)
        if is_auto_save:
            return JsonResponse({'status': 'ok', 'saved_at': datetime.now().isoformat()})
        return HttpResponseRedirect(reverse('canvas'))

    current_state = sanitize_canvas_state(notes_canvas_by_week.get(week_key))
    context = {
        'canvas_data_json': json.dumps(current_state),
        'note_type_options_json': json.dumps(note_type_options),
        'note_type_colors_json': json.dumps(note_type_colors),
        'week_start_iso': week_start.isoformat(),
        'week_end_iso': week_end.isoformat(),
        'week_range_label': f"{week_start.strftime('%d %b %Y')} to {week_end.strftime('%d %b %Y')}",
        'nav_layout': preferences.nav_layout,
    }
    return render(request, 'dashboard/notes.html', context)

@login_required
def add_diary_entry(request):
    if request.method == 'POST':
        entry_id = request.POST.get('entry_id')
        title = request.POST.get('title')
        category = normalize_diary_category(request.POST.get('category', DIARY_DEFAULT_CATEGORY))
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
                diary_entry.category = category
                diary_entry.date = parsed_date
                diary_entry.end_date = effective_end_date
                diary_entry.start_time = parsed_start
                diary_entry.end_time = parsed_end
                diary_entry.content = content or ''
                diary_entry.save()
                messages.success(request, 'Diary entry updated successfully!')
                return HttpResponseRedirect(f"{reverse('diary')}?date={redirect_date}")
            else:
                # For timed entries with a date range, create one entry per day in the range.
                if (parsed_start or parsed_end) and parsed_end_date and parsed_end_date > parsed_date:
                    current_date = parsed_date
                    created_count = 0
                    while current_date <= parsed_end_date:
                        DiaryEntry.objects.create(
                            user=request.user,
                            title=title,
                            category=category,
                            date=current_date,
                            end_date=None,
                            start_time=parsed_start,
                            end_time=parsed_end,
                            content=content or ''
                        )
                        created_count += 1
                        current_date = current_date + timedelta(days=1)

                    messages.success(request, f'{created_count} diary entries added successfully!')
                    return HttpResponseRedirect(reverse('diary'))
                else:
                    DiaryEntry.objects.create(
                        user=request.user,
                        title=title,
                        category=category,
                        date=parsed_date,
                        end_date=effective_end_date,
                        start_time=parsed_start,
                        end_time=parsed_end,
                        content=content or ''
                    )
                    messages.success(request, 'Diary entry added successfully!')
                    return HttpResponseRedirect(reverse('diary'))
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
