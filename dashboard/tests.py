import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import NoteAttachment, NoteEntry


class NotesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.client.login(username='tester', password='pass12345')

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
