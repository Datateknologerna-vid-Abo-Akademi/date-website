from unittest import skipUnless

from django.apps import apps
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


@skipUnless(apps.is_installed('lucia'), 'lucia is only installed for the kk association')
class CandidateVisibilityTests(TestCase):
    def setUp(self):
        # Imported here rather than at module level: the default test settings do
        # not install lucia, and a module-level model import would break the date
        # suite's test discovery even though these tests are skipped under it.
        from lucia.models import Candidate

        self.published = Candidate.objects.create(
            title='Viktor Kuokka',
            slug='viktor',
            poll_url='https://kemistklubben.org/polls/74/',
            published_time=timezone.now() - timezone.timedelta(days=1),
        )
        self.scheduled = Candidate.objects.create(
            title='Gustav Johnsson',
            slug='Gurran',
            poll_url='https://kemistklubben.org/polls/74/',
            published_time=timezone.now() + timezone.timedelta(days=1),
        )
        self.hidden = Candidate.objects.create(
            title='Ingen publicering',
            slug='dold',
            poll_url='https://kemistklubben.org/polls/74/',
            published_time=None,
        )

    def test_published_candidate_resolves(self):
        response = self.client.get(reverse('lucia:candidate', args=[self.published.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['candidate'], self.published)

    def test_unknown_slug_returns_404(self):
        response = self.client.get(reverse('lucia:candidate', args=['Gustav']))
        self.assertEqual(response.status_code, 404)

    def test_unpublished_slugs_return_404(self):
        for candidate in (self.scheduled, self.hidden):
            with self.subTest(slug=candidate.slug):
                response = self.client.get(reverse('lucia:candidate', args=[candidate.slug]))
                self.assertEqual(response.status_code, 404)

    def test_candidates_list_renders_only_published(self):
        response = self.client.get(reverse('lucia:candidates'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['candidates']), [self.published])

    def test_index_context_renders_only_published(self):
        response = self.client.get(reverse('lucia:index'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['candidates']), [self.published])
