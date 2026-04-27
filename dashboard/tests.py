import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import NoteAttachment, NoteEntry, TodoTask, UserPreference


class TodoViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='todo_tester', password='pass12345')
        self.client.login(username='todo_tester', password='pass12345')

    def add_task(self, title, priority):
        return self.client.post(
            reverse('todo'),
            {
                'form_type': 'add_todo_entry',
                'task_title': title,
                'task_start_date': '2026-04-17',
                'task_end_date': '2026-04-17',
                'task_section': 'planning',
                'task_notes': '',
                'task_checklist_json': '[]',
                'task_priority': priority,
            },
        )

    def test_todo_accepts_urgent_priority(self):
        response = self.add_task('Fix outage', 'urgent')
        self.assertEqual(response.status_code, 302)

        get_response = self.client.get(reverse('todo'))
        self.assertEqual(get_response.status_code, 200)
        planning = next(section for section in get_response.context['section_lists'] if section['key'] == 'planning')
        self.assertEqual(planning['active_tasks'][0]['priority'], 'urgent')
        self.assertEqual(planning['active_tasks'][0]['priority_label'], 'Urgent')

    def test_todo_is_sorted_by_priority(self):
        self.add_task('Low task', 'low')
        self.add_task('High task', 'high')
        self.add_task('Urgent task', 'urgent')
        self.add_task('Medium task', 'medium')

        response = self.client.get(reverse('todo'))
        self.assertEqual(response.status_code, 200)
        planning = next(section for section in response.context['section_lists'] if section['key'] == 'planning')
        ordered_titles = [task['title'] for task in planning['active_tasks']]
        self.assertEqual(ordered_titles[:4], ['Urgent task', 'High task', 'Medium task', 'Low task'])

    def test_todo_can_persist_manual_drag_drop_order(self):
        self.add_task('Low task', 'low')
        self.add_task('Urgent task', 'urgent')

        tasks = list(TodoTask.objects.filter(user=self.user).order_by('created_at'))
        self.assertEqual(len(tasks), 2)

        response = self.client.post(
            reverse('todo'),
            {
                'form_type': 'reorder_todo_entries',
                'ordered_task_ids_json': json.dumps([
                    {
                        'id': tasks[0].task_id,
                        'section': 'planning',
                    },
                    {
                        'id': tasks[1].task_id,
                        'section': 'planning',
                    },
                ]),
            },
        )

        self.assertEqual(response.status_code, 302)

        get_response = self.client.get(reverse('todo'))
        self.assertEqual(get_response.status_code, 200)
        planning = next(section for section in get_response.context['section_lists'] if section['key'] == 'planning')
        ordered_titles = [task['title'] for task in planning['active_tasks']]
        self.assertEqual(ordered_titles[:2], ['Low task', 'Urgent task'])

    def test_todo_completed_tasks_render_in_collapsed_archive(self):
        active = TodoTask.objects.create(
            user=self.user,
            task_id='active-task',
            title='Active task',
            section='planning',
            completed=False,
        )
        completed = TodoTask.objects.create(
            user=self.user,
            task_id='completed-task',
            title='Completed task',
            section='planning',
            completed=True,
        )

        response = self.client.get(reverse('todo'))

        self.assertEqual(response.status_code, 200)
        planning = next(section for section in response.context['section_lists'] if section['key'] == 'planning')
        self.assertEqual([task['id'] for task in planning['active_tasks']], [active.task_id])
        self.assertEqual([task['id'] for task in planning['completed_tasks']], [completed.task_id])
        self.assertContains(response, 'class="todo-archive"')
        self.assertContains(response, 'Archive / Completed (1)')
        self.assertContains(response, 'clear_completed_todo_entries')

    def test_clear_completed_todo_entries_removes_only_target_section_completed_tasks(self):
        keep_active = TodoTask.objects.create(
            user=self.user,
            task_id='keep-active',
            title='Keep active',
            section='planning',
            completed=False,
        )
        remove_completed = TodoTask.objects.create(
            user=self.user,
            task_id='remove-completed',
            title='Remove completed',
            section='planning',
            completed=True,
        )
        keep_completed_other_section = TodoTask.objects.create(
            user=self.user,
            task_id='keep-other-section',
            title='Keep other section completed',
            section='next',
            completed=True,
        )

        response = self.client.post(
            reverse('todo'),
            {
                'form_type': 'clear_completed_todo_entries',
                'section_key': 'planning',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(TodoTask.objects.filter(user=self.user, task_id=keep_active.task_id).exists())
        self.assertFalse(TodoTask.objects.filter(user=self.user, task_id=remove_completed.task_id).exists())
        self.assertTrue(TodoTask.objects.filter(user=self.user, task_id=keep_completed_other_section.task_id).exists())

    def test_todo_renders_clamped_notes_preview_with_expandable_full_notes(self):
        TodoTask.objects.create(
            user=self.user,
            task_id='task-notes-preview',
            title='Task with notes',
            notes='Line one\nLine two\nLine three',
            priority='medium',
            section='planning',
        )

        response = self.client.get(reverse('todo'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="todo-task-notes"')
        self.assertContains(response, 'class="todo-task-inline-notes"')
        self.assertContains(response, 'data-has-details="true"')
        self.assertContains(response, 'Line one\nLine two\nLine three')


class NotesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.client.login(username='tester', password='pass12345')

    def test_notes_editor_exposes_table_toolbar_button(self):
        note = NoteEntry.objects.create(user=self.user, title='Toolbar note', body='<p>Body</p>')

        response = self.client.get(reverse('notes'), {'note': note.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-cmd="insertTable"')
        self.assertContains(response, 'data-cmd="insertHorizontalRule"')
        self.assertContains(response, 'id="text-color-input"')

    def test_save_note_preserves_table_markup(self):
        note = NoteEntry.objects.create(user=self.user, title='Table note', body='<p>Old</p>')
        table_html = '<table><tr><th>Head</th></tr><tr><td>Cell</td></tr></table>'

        response = self.client.post(
            reverse('notes'),
            {
                'notes_action': 'save_note',
                'note_id': str(note.id),
                'title': 'Table note',
                'body': table_html,
                'category_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertIn('<table>', note.body)
        self.assertIn('<th>Head</th>', note.body)
        self.assertIn('<td>Cell</td>', note.body)

    def test_save_note_preserves_text_color_markup(self):
        note = NoteEntry.objects.create(user=self.user, title='Color note', body='<p>Old</p>')
        colored_html = '<p><span style="color: rgb(255, 0, 0);">Important</span></p>'

        response = self.client.post(
            reverse('notes'),
            {
                'notes_action': 'save_note',
                'note_id': str(note.id),
                'title': 'Color note',
                'body': colored_html,
                'category_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        note.refresh_from_db()
        self.assertIn('style="color: rgb(255, 0, 0);"', note.body)
        self.assertIn('Important', note.body)

    def test_create_note_with_attachment(self):
        upload = SimpleUploadedFile('hello.txt', b'hello world', content_type='text/plain')

        response = self.client.post(
            reverse('notes'),
            {
                'notes_action': 'create_note',
                'new_note_title': 'Attachment note',
                'new_note_body': '<p>Body</p>',
                'attachments': upload,
            },
        )

        self.assertEqual(response.status_code, 302)
        note = NoteEntry.objects.get(title='Attachment note')
        self.assertEqual(note.attachments.count(), 1)
        self.assertEqual(NoteAttachment.objects.count(), 1)

    def test_delete_attachment_from_note(self):
        note = NoteEntry.objects.create(user=self.user, title='Existing', body='<p>Text</p>')
        attachment = NoteAttachment.objects.create(
            note=note,
            file=SimpleUploadedFile('keep.txt', b'data', content_type='text/plain'),
        )

        response = self.client.post(
            reverse('notes'),
            {
                'notes_action': 'delete_attachment',
                'note_id': str(note.id),
                'attachment_id': str(attachment.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(NoteAttachment.objects.filter(id=attachment.id).exists())


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dashboard_tester', password='pass12345')
        self.client.login(username='dashboard_tester', password='pass12345')

    def test_dashboard_uses_embedded_quick_add_tab_in_bottom_menu(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="bottom-menu"', html=False)
        self.assertContains(response, 'menu-label">Quick Add<', html=False)
        self.assertNotContains(response, 'mobile-bottom-btn-primary', html=False)

    def test_dashboard_quick_add_matches_standard_tab_styling(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mobile-quick-add', html=False)
        self.assertNotContains(response, 'menu-item quick-add', html=False)

    def test_dashboard_ipad_bottom_nav_hides_footer(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'body.nav-position-bottom .dashboard-footer', html=False)
        self.assertContains(response, 'display: none !important', html=False)

    def test_dashboard_phone_menu_hides_settings_but_keeps_ipad_version(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="menu-item settings-link"', html=False)
        self.assertContains(response, '.bottom-menu .menu-item.settings-link {', html=False)
        self.assertContains(response, 'grid-template-columns: repeat(5, minmax(0, 1fr));', html=False)

    def test_dashboard_shows_account_modal_trigger(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="account-open-btn"', html=False)
        self.assertContains(response, 'id="account-modal"', html=False)
        self.assertContains(response, self.user.username)

    def test_dashboard_can_update_email_from_account_modal(self):
        response = self.client.post(
            reverse('dashboard'),
            {
                'form_type': 'update_email',
                'email': 'updated@example.com',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_dashboard_todo_board_hides_completed_tasks(self):
        TodoTask.objects.create(
            user=self.user,
            task_id='todo-active-dashboard',
            title='Active dashboard task',
            priority='high',
            section='planning',
            completed=False,
        )
        TodoTask.objects.create(
            user=self.user,
            task_id='todo-done-dashboard',
            title='Done dashboard task',
            priority='high',
            section='planning',
            completed=True,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active dashboard task')
        self.assertNotContains(response, 'Done dashboard task')


class SettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='settings_tester', password='pass12345')
        self.client.login(username='settings_tester', password='pass12345')

    def test_settings_shows_ipad_navigation_option(self):
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'iPad navigation')
        self.assertContains(response, 'iPhone-style bottom menu')
        self.assertContains(response, 'name="nav_layout"', html=False)

    def test_settings_can_save_ipad_navigation_preference(self):
        response = self.client.post(
            reverse('settings'),
            {
                'form_type': 'update_preferences',
                'nav_layout': 'bottom',
                'default_diary_view': 'week',
            },
        )

        self.assertEqual(response.status_code, 302)
        preferences = UserPreference.objects.get(user=self.user)
        self.assertEqual(preferences.nav_layout, 'bottom')

    def test_shared_compact_menu_keeps_settings_for_ipad_and_desktop(self):
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Settings"', html=False)
        self.assertContains(response, 'mobile-bottom-link-settings', html=False)
        self.assertContains(response, '>Settings<', html=False)

    def test_shared_phone_menu_hides_settings_link(self):
        css_path = Path(settings.BASE_DIR) / 'dashboard' / 'static' / 'dashboard' / 'css' / 'mobile-bottom-nav.css'
        css = css_path.read_text(encoding='utf-8')

        self.assertIn('@media (max-width: 599px)', css)
        self.assertIn('.mobile-bottom-link-settings', css)
        self.assertIn('display: none !important', css)

    def test_shared_compact_menu_uses_inline_quick_add_tab(self):
        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mobile-quick-add', html=False)
        self.assertNotContains(response, 'mobile-bottom-btn-primary', html=False)


class CanvasViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='canvas_tester', password='pass12345')
        self.client.login(username='canvas_tester', password='pass12345')

    def get_canvas_payload(self):
        return {
            'boxes': [
                {
                    'id': 'box-text-1',
                    'x': 80,
                    'y': 90,
                    'w': 360,
                    'h': 220,
                    'title': 'Roadmap',
                    'type': 'Text',
                    'note_date': '2026-04-13',
                    'completed': False,
                    'body_html': 'Simple linked text',
                    'text': 'Simple linked text',
                }
            ],
            'links': [],
        }

    def test_canvas_preserves_plain_text_box_type(self):
        payload = self.get_canvas_payload()
        payload['boxes'][0]['title'] = ''

        post_response = self.client.post(
            reverse('canvas'),
            {
                'canvas_data': json.dumps(payload),
            },
        )
        self.assertEqual(post_response.status_code, 302)

        get_response = self.client.get(reverse('canvas'))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn('"type": "Text"', get_response.context['canvas_data_json'])

    def test_canvas_can_save_named_snapshot_for_later(self):
        payload = self.get_canvas_payload()

        post_response = self.client.post(
            reverse('canvas'),
            {
                'notes_action': 'save_saved_canvas',
                'canvas_name': 'Sprint Plan',
                'canvas_data': json.dumps(payload),
            },
        )

        self.assertEqual(post_response.status_code, 302)

        get_response = self.client.get(reverse('canvas'))
        self.assertEqual(get_response.status_code, 200)
        saved_canvases = list(get_response.context['saved_canvases'])
        self.assertTrue(any(item.name == 'Sprint Plan' for item in saved_canvases))

    def test_canvas_can_reopen_saved_snapshot(self):
        payload = self.get_canvas_payload()
        self.client.post(
            reverse('canvas'),
            {
                'notes_action': 'save_saved_canvas',
                'canvas_name': 'Sprint Plan',
                'canvas_data': json.dumps(payload),
            },
        )

        initial_get = self.client.get(reverse('canvas'))
        saved_canvases = list(initial_get.context['saved_canvases'])
        self.assertEqual(len(saved_canvases), 1)

        load_response = self.client.post(
            reverse('canvas'),
            {
                'notes_action': 'load_saved_canvas',
                'saved_canvas_id': str(saved_canvases[0].id),
            },
        )

        self.assertEqual(load_response.status_code, 302)

        get_response = self.client.get(reverse('canvas'))
        self.assertEqual(get_response.status_code, 200)
        self.assertIn('"title": "Roadmap"', get_response.context['canvas_data_json'])
        self.assertIn('"canvas_name": "Sprint Plan"', get_response.context['canvas_data_json'])

    def test_canvas_preserves_box_colour_and_link_style(self):
        payload = self.get_canvas_payload()
        payload['boxes'][0]['color'] = '#ff6b6b'
        payload['boxes'][0]['w'] = 140
        payload['boxes'][0]['h'] = 90
        payload['boxes'].append(
            {
                'id': 'box-text-2',
                'x': 420,
                'y': 120,
                'w': 180,
                'h': 110,
                'title': 'Second',
                'type': 'Text',
                'note_date': '2026-04-13',
                'completed': False,
                'color': '#4ade80',
                'body_html': 'Another box',
                'text': 'Another box',
            }
        )
        payload['links'] = [
            {
                'from': 'box-text-1',
                'to': 'box-text-2',
                'style': 'dashed',
                'end': 'arrow',
                'color': '#ff8844',
            }
        ]

        post_response = self.client.post(
            reverse('canvas'),
            {
                'canvas_data': json.dumps(payload),
            },
        )
        self.assertEqual(post_response.status_code, 302)

        get_response = self.client.get(reverse('canvas'))
        self.assertEqual(get_response.status_code, 200)
        canvas_data = get_response.context['canvas_data_json']
        self.assertIn('"color": "#ff6b6b"', canvas_data)
        self.assertIn('"style": "dashed"', canvas_data)
        self.assertIn('"end": "arrow"', canvas_data)
        self.assertIn('"color": "#ff8844"', canvas_data)
        self.assertIn('"w": 140', canvas_data)

    def test_canvas_exposes_link_mode_guidance_ui(self):
        response = self.client.get(reverse('canvas'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="link-mode-btn"', html=False)
        self.assertContains(response, 'Link Mode: Off')
        self.assertContains(response, 'id="toolbar-info"', html=False)
        self.assertContains(response, 'id="link-mode-hint"', html=False)
