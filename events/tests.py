from django.test import TestCase, Client
from django.urls import reverse

from events.models import Event
from members.models import Member

class EventTestCase(TestCase):
    def setUp(self):
        member = Member.objects.create(username='Test')
        Event.objects.create(title='Test event', slug='test', author_id=member.id)

    def test_attending_event(self):
        event = Event.objects.get(slug='test')
        self.assertIsNotNone(event)
        c = Client()
        response = c.post(reverse('events:detail', args=[event.slug]), {'user': 'person', 'email': 'person@test.com'})
        self.assertEqual(response.status_code, 200)
