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
