from importlib import import_module

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_ckeditor_5.widgets import CKEditor5Widget

from ctf.admin import FlagInline
from ctf.models import Ctf, Flag, Guess, PostMortem
from members.models import ORDINARY_MEMBER, Member, MembershipType


class CtfTranslationAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="ctf-translation-admin",
            password="pass",
            email="ctf-translation-admin@example.com",
        )
        self.client.force_login(self.admin_user)
        self.request_factory = RequestFactory()
        self.ctf = Ctf.objects.create(title="Spring CTF", slug="spring-ctf")

    def _translation_form(self):
        request = self.request_factory.get(reverse("admin:ctf_ctf_change", args=[self.ctf.pk]))
        request.user = self.admin_user
        return admin.site._registry[Ctf].get_form(request, obj=self.ctf)

    def test_change_page_renders_translation_fields(self):
        response = self.client.get(reverse("admin:ctf_ctf_change", args=[self.ctf.pk]))

        self.assertEqual(response.status_code, 200)
        for field_name in ("title_sv", "title_en", "title_fi", "content_sv"):
            self.assertContains(response, f'name="{field_name}"')

    def test_translation_form_uses_ckeditor_widget_for_content_fields(self):
        form_class = self._translation_form()

        for field_name in ("content_sv", "content_en", "content_fi"):
            self.assertIsInstance(form_class.base_fields[field_name].widget, CKEditor5Widget)

    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English")))
    def test_translation_form_hides_inactive_language_fields(self):
        form_class = self._translation_form()

        self.assertIn("title_en", form_class.base_fields)
        self.assertIn("content_en", form_class.base_fields)
        self.assertNotIn("title_fi", form_class.base_fields)
        self.assertNotIn("content_fi", form_class.base_fields)

    def test_translation_status_counts_completed_fields(self):
        model_admin = admin.site._registry[Ctf]

        self.assertEqual(model_admin.translation_status(self.ctf), "sv: 1/2; en: 0/2; fi: 0/2")
        self.assertEqual(
            model_admin.translation_status(Ctf(title="Spring CTF", content="<p>Come solve puzzles</p>")),
            "sv: 2/2; en: 0/2; fi: 0/2",
        )

    def test_changelist_shows_translation_coverage(self):
        response = self.client.get(reverse("admin:ctf_ctf_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sv: 1/2; en: 0/2; fi: 0/2")

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_translation_coverage_is_hidden_when_language_features_are_disabled(self):
        model_admin = admin.site._registry[Ctf]
        request = self.request_factory.get(reverse("admin:ctf_ctf_changelist"))

        self.assertNotIn("translation_status", model_admin.get_list_display(request))


class CtfPublicTranslationTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="ctf-member", password="pass")
        self.client.force_login(self.member)
        self.ctf = Ctf.objects.create(
            title="Vår CTF",
            content="<p>Svensk text</p>",
            title_en="Spring CTF",
            content_en="<p>English text</p>",
            slug="spring-ctf",
        )

    def test_detail_page_renders_the_selected_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:detail", args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring CTF")
        self.assertContains(response, "English text")
        self.assertNotContains(response, "Svensk text")

    def test_index_page_lists_titles_in_the_selected_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring CTF")

    def test_detail_page_falls_back_to_swedish_when_a_translation_is_missing(self):
        self.ctf.title_en = ""
        self.ctf.content_en = ""
        self.ctf.save()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:detail", args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vår CTF")
        self.assertContains(response, "Svensk text")


class CtfTranslationBackfillTests(TestCase):
    """Cover the 0006 backfill of the translated columns.

    ``Ctf.title`` and ``Ctf.content`` resolve through the modeltranslation
    descriptor, which only reads the ``*_<language>`` columns, so rows that
    predate the translated columns would render blank without the backfill.

    The historical model from the migration state is used on purpose: it has a
    plain manager, exactly like the model the migration runs against, while the
    live model's manager rewrites ``F("title")`` to the translated column and
    would turn the backfill into a no-op.
    """

    migration = "0005_ctf_content_en_ctf_content_fi_ctf_content_sv_and_more"

    def setUp(self):
        super().setUp()
        state = MigrationLoader(connection, ignore_no_migrations=True).project_state([("ctf", self.migration)])
        self.migration_apps = state.apps
        self.legacy_ctf = state.apps.get_model("ctf", "Ctf")

    def _run_backfill(self):
        module = import_module("ctf.migrations.0006_backfill_ctf_default_translations")
        module.backfill_ctf_default_translations(self.migration_apps, None)

    def test_backfill_copies_legacy_values_into_the_swedish_columns(self):
        ctf = self.legacy_ctf.objects.create(
            title="Legacy CTF",
            content="<p>Legacy text</p>",
            slug="legacy-ctf",
        )
        # Guard the test against becoming vacuous: a row written before the
        # translated columns existed has no Swedish values yet.
        self.assertIsNone(self.legacy_ctf.objects.values_list("title_sv", flat=True).get(pk=ctf.pk))

        self._run_backfill()

        row = self.legacy_ctf.objects.values("title_sv", "content_sv").get(pk=ctf.pk)
        self.assertEqual(row["title_sv"], "Legacy CTF")
        self.assertEqual(row["content_sv"], "<p>Legacy text</p>")
        # The public page reads through the live descriptor.
        self.assertEqual(Ctf.objects.get(pk=ctf.pk).title, "Legacy CTF")

    def test_backfill_keeps_existing_swedish_values(self):
        ctf = self.legacy_ctf.objects.create(
            title="Legacy CTF",
            content="<p>Legacy text</p>",
            slug="translated-ctf",
        )
        self.legacy_ctf.objects.filter(pk=ctf.pk).update(title_sv="Översatt titel", content_sv="<p>Översatt</p>")

        self._run_backfill()

        row = self.legacy_ctf.objects.values("title_sv", "content_sv").get(pk=ctf.pk)
        self.assertEqual(row["title_sv"], "Översatt titel")
        self.assertEqual(row["content_sv"], "<p>Översatt</p>")


def _make_member(username='member'):
    return Member.objects.create_user(
        username=username[:20],
        password='test',
        email=f'{username[:20]}@example.com',
        membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
    )


def _make_ctf(*, ended, published, slug, title):
    now = timezone.now()
    return Ctf.objects.create(
        title=title,
        slug=slug,
        start_date=now - timezone.timedelta(days=2),
        end_date=now - timezone.timedelta(days=1) if ended else now + timezone.timedelta(days=1),
        published_time=now - timezone.timedelta(days=1) if published else None,
    )


def _make_flag(ctf, title, slug, solver=None, solution=''):
    return Flag.objects.create(
        ctf=ctf,
        title=title,
        flag=f'flag{{{slug}}}',
        slug=slug,
        solver=solver,
        solved_date=timezone.now() if solver else None,
        solution=solution,
    )


def _make_guess(ctf, flag, user, correct, guess='attempt'):
    return Guess.objects.create(ctf=ctf, flag=flag, user=user, guess=guess, correct=correct)


class PostMortemVisibilityTests(TestCase):
    def setUp(self):
        self.member = _make_member('viewer')
        self.ctf = _make_ctf(ended=True, published=True, slug='puzzle-hunt', title='Puzzle Hunt')

    def test_anonymous_detail_redirects_to_login(self):
        path = reverse('ctf:post_mortem_detail', args=[self.ctf.slug])
        response = self.client.get(path)

        self.assertRedirects(response, f'{reverse("members:login")}?next={path}', fetch_redirect_response=False)

    def test_anonymous_index_redirects_to_login(self):
        path = reverse('ctf:post_mortem_index')
        response = self.client.get(path)

        self.assertRedirects(response, f'{reverse("members:login")}?next={path}', fetch_redirect_response=False)

    def test_unpublished_post_mortem_is_bare_404(self):
        PostMortem.objects.create(ctf=self.ctf, overview='Hidden overview')
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_detail', args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.ctf.title, response.content.decode())

    def test_running_ctf_post_mortem_is_404(self):
        running = _make_ctf(ended=False, published=True, slug='running', title='Running CTF')
        PostMortem.objects.create(ctf=running, published_time=timezone.now() - timezone.timedelta(hours=1))
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_detail', args=[running.slug]))

        self.assertEqual(response.status_code, 404)

    def test_scheduled_post_mortem_is_404(self):
        PostMortem.objects.create(ctf=self.ctf, published_time=timezone.now() + timezone.timedelta(days=1))
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_detail', args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 404)

    def test_missing_post_mortem_is_404(self):
        # The CTF is ended and published, but no PostMortem row exists at all.
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_detail', args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 404)

    def test_ended_and_published_post_mortem_renders(self):
        solver = _make_member('solver')
        flag = _make_flag(self.ctf, 'First flag', 'first-flag', solver=solver, solution='Use the decoder ring.')
        PostMortem.objects.create(
            ctf=self.ctf,
            overview='Overview fragment',
            published_time=timezone.now() - timezone.timedelta(hours=1),
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_detail', args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ctf.title)
        self.assertContains(response, 'Overview fragment')
        self.assertContains(response, flag.flag)
        self.assertContains(response, 'Use the decoder ring.')
        self.assertContains(response, solver.username)
        self.assertContains(response, '[SOLVED]')

    def test_index_lists_only_visible_post_mortems(self):
        visible = PostMortem.objects.create(
            ctf=self.ctf,
            published_time=timezone.now() - timezone.timedelta(hours=1),
        )
        hidden_ctf = _make_ctf(ended=True, published=True, slug='hidden', title='Hidden CTF')
        PostMortem.objects.create(ctf=hidden_ctf)
        running_ctf = _make_ctf(ended=False, published=True, slug='running', title='Running CTF')
        PostMortem.objects.create(ctf=running_ctf, published_time=timezone.now() - timezone.timedelta(hours=1))
        scheduled_ctf = _make_ctf(ended=True, published=True, slug='scheduled', title='Scheduled CTF')
        scheduled = PostMortem.objects.create(
            ctf=scheduled_ctf,
            published_time=timezone.now() + timezone.timedelta(days=1),
        )
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:post_mortem_index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['post_mortems']), [visible])
        self.assertNotIn(scheduled, response.context['post_mortems'])

    def test_queryset_methods_and_properties_track_visibility(self):
        now = timezone.now()
        past = now - timezone.timedelta(hours=1)
        future = now + timezone.timedelta(hours=1)
        ended = _make_ctf(ended=True, published=True, slug='ended', title='Ended')
        running = _make_ctf(ended=False, published=True, slug='running', title='Running')
        scheduled_ctf = _make_ctf(ended=True, published=True, slug='scheduled', title='Scheduled')
        hidden_ctf = _make_ctf(ended=True, published=True, slug='hidden', title='Hidden')

        published_visible = PostMortem.objects.create(ctf=ended, published_time=past)
        published_running = PostMortem.objects.create(ctf=running, published_time=past)
        scheduled = PostMortem.objects.create(ctf=scheduled_ctf, published_time=future)
        hidden = PostMortem.objects.create(ctf=hidden_ctf)

        self.assertEqual(set(PostMortem.objects.published()), {published_visible, published_running})
        self.assertEqual(set(PostMortem.objects.visible()), {published_visible})
        self.assertTrue(published_visible.published)
        self.assertTrue(published_visible.is_visible)
        self.assertTrue(published_running.published)
        self.assertFalse(published_running.is_visible)
        self.assertFalse(scheduled.published)
        self.assertFalse(scheduled.is_visible)
        self.assertFalse(hidden.published)
        self.assertFalse(hidden.is_visible)

    def test_get_absolute_url_uses_ctf_slug(self):
        post_mortem = PostMortem(ctf=self.ctf)

        self.assertEqual(post_mortem.get_absolute_url(), reverse('ctf:post_mortem_detail', args=[self.ctf.slug]))
        self.assertEqual(post_mortem.get_absolute_url(), '/ctf/post-mortem/puzzle-hunt')

    def test_ctf_detail_renders_without_a_post_mortem(self):
        # Reverse one-to-one access raises RelatedObjectDoesNotExist, which the
        # template engine swallows as a failed lookup.
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('ctf:detail', args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)

    def test_literal_post_mortem_route_wins_over_post_mortem_slug(self):
        # A CTF slugged `post-mortem` is unreachable at ctf:detail; the literal
        # post-mortem patterns must keep matching first.
        _make_ctf(ended=True, published=True, slug='post-mortem', title='Shadowing CTF')
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

        response = self.client.get('/ctf/post-mortem')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ctf/post_mortem_index.html')


class PostMortemContentTests(TestCase):
    def setUp(self):
        self.member = _make_member('viewer')
        self.solver = _make_member('solver')
        self.ctf = _make_ctf(ended=True, published=True, slug='hunt', title='Hunt')
        PostMortem.objects.create(
            ctf=self.ctf,
            overview='Overview',
            published_time=timezone.now() - timezone.timedelta(hours=1),
        )
        self.url = reverse('ctf:post_mortem_detail', args=[self.ctf.slug])
        self.client.force_login(self.member, backend='members.backends.AuthBackend')

    def test_per_challenge_input_counts_and_total(self):
        first = _make_flag(self.ctf, 'First', 'first')
        second = _make_flag(self.ctf, 'Second', 'second')
        third = _make_flag(self.ctf, 'Third', 'third')
        for _ in range(3):
            _make_guess(self.ctf, first, self.member, False)
        _make_guess(self.ctf, second, self.member, True)

        response = self.client.get(self.url)

        challenges = response.context['challenges']
        self.assertEqual([challenge['flag'] for challenge in challenges], [first, second, third])
        self.assertEqual([challenge['inputs'] for challenge in challenges], [3, 1, 0])
        self.assertEqual(response.context['total_guesses'], 4)
        self.assertEqual(response.context['total_guesses'], Guess.objects.filter(ctf=self.ctf).count())

    def test_unsolved_challenge_renders_unsolved_state(self):
        flag = _make_flag(self.ctf, 'Broken cipher', 'broken-cipher')
        _make_guess(self.ctf, flag, self.member, False)
        # The LangMiddleware activates the language from the cookie, so
        # translation.override() is not enough to force English here.
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'

        response = self.client.get(self.url)

        self.assertContains(response, 'Unsolved')
        self.assertContains(response, 'Number of inputs: 1')
        self.assertNotContains(response, '[SOLVED]')
        self.assertContains(response, flag.flag)

    def test_flag_string_and_solution_narrative_are_rendered(self):
        flag = _make_flag(
            self.ctf,
            'Solved challenge',
            'solved-challenge',
            solver=self.solver,
            solution='Decode the base64 payload.',
        )

        response = self.client.get(self.url)

        self.assertContains(response, flag.flag)
        self.assertContains(response, 'Decode the base64 payload.')

    def test_challenges_are_rendered_in_pk_order(self):
        zeta = _make_flag(self.ctf, 'Zeta', 'zeta')
        alpha = _make_flag(self.ctf, 'Alpha', 'alpha')

        response = self.client.get(self.url)

        self.assertEqual([challenge['flag'] for challenge in response.context['challenges']], [zeta, alpha])

    def test_other_members_wrong_guess_is_not_exposed(self):
        flag = _make_flag(self.ctf, 'Broken cipher', 'broken-cipher', solver=self.solver)
        other = _make_member('wrongguessr')
        _make_guess(self.ctf, flag, other, False, guess='totally-wrong-answer')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'totally-wrong-answer')
        self.assertNotContains(response, other.username)
        self.assertContains(response, self.solver.username)

    def test_mismatched_guess_does_not_break_the_total(self):
        first = _make_flag(self.ctf, 'First', 'first')
        _make_guess(self.ctf, first, self.member, False, guess='wrong-on-purpose')
        foreign_ctf = _make_ctf(ended=True, published=True, slug='foreign', title='Foreign CTF')
        foreign_flag = _make_flag(foreign_ctf, 'Foreign flag', 'foreign-flag')
        # GuessAdmin lets ctf and flag be chosen independently, so a row can
        # point at this CTF while its flag belongs to another one.
        _make_guess(self.ctf, foreign_flag, self.member, False, guess='foreign-attempt')

        response = self.client.get(self.url)

        challenges = response.context['challenges']
        self.assertEqual(Guess.objects.filter(ctf=self.ctf).count(), 2)
        self.assertEqual(response.context['total_guesses'], sum(challenge['inputs'] for challenge in challenges))
        self.assertEqual(response.context['total_guesses'], 1)


class PostMortemAdminAccessTests(TestCase):
    def setUp(self):
        self.ctf = _make_ctf(ended=True, published=True, slug='admin-ctf', title='Admin CTF')
        self.group, _ = Group.objects.get_or_create(name=settings.STAFF_GROUPS[0])

    def _editor(self, *permissions):
        member = _make_member(f'editor{self._testMethodName}')
        member.groups.add(self.group)
        for app_label, codename in permissions:
            member.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        self.client.force_login(member, backend='members.backends.AuthBackend')
        return member

    def _post_mortem_changelist_link(self):
        ctf_admin = admin.site.get_model_admin(Ctf)
        return next(link for link in ctf_admin.changelist_links if link.url_name == 'admin:ctf_postmortem_changelist')

    def test_changelist_link_admits_every_ctf_content_permission(self):
        # The changelist shortcut and the sidebar entry must admit the same set.
        # Only a holder who can open the CTF changelist can see the shortcut at
        # all, so the matrix is asserted against the link's own resolution.
        link = self._post_mortem_changelist_link()

        for codename in ('add_ctf', 'change_ctf', 'add_flag', 'change_flag'):
            with self.subTest(codename=codename):
                member = _make_member(f'link{codename}')
                member.user_permissions.add(Permission.objects.get(content_type__app_label='ctf', codename=codename))
                request = RequestFactory().get('/admin/')
                request.user = member

                self.assertIsNotNone(link.resolve(request))

    def test_changelist_link_is_hidden_from_view_only_staff(self):
        link = self._post_mortem_changelist_link()
        member = _make_member('linkviewer')
        member.user_permissions.add(Permission.objects.get(content_type__app_label='ctf', codename='view_ctf'))
        request = RequestFactory().get('/admin/')
        request.user = member

        self.assertIsNone(link.resolve(request))

    def test_ctf_editor_can_open_post_mortem_admin(self):
        self._editor(('ctf', 'change_ctf'))

        changelist_response = self.client.get(reverse('admin:ctf_postmortem_changelist'))
        add_response = self.client.get(reverse('admin:ctf_postmortem_add'))

        self.assertEqual(changelist_response.status_code, 200)
        self.assertEqual(add_response.status_code, 200)

    def test_ctf_editor_can_create_published_post_mortem(self):
        self._editor(('ctf', 'change_ctf'))
        published_time = timezone.localtime(timezone.now() - timezone.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')

        response = self.client.post(
            reverse('admin:ctf_postmortem_add'),
            {'ctf': self.ctf.pk, 'published_time': published_time},
        )

        self.assertEqual(response.status_code, 302)
        post_mortem = PostMortem.objects.get()
        self.assertIsNotNone(post_mortem.published_time)

    def test_ctf_editor_can_create_hidden_post_mortem(self):
        self._editor(('ctf', 'change_ctf'))

        response = self.client.post(
            reverse('admin:ctf_postmortem_add'),
            {'ctf': self.ctf.pk, 'published_time': ''},
        )

        self.assertEqual(response.status_code, 302)
        post_mortem = PostMortem.objects.get()
        self.assertIsNone(post_mortem.published_time)

    def test_staff_without_ctf_permission_is_forbidden(self):
        member = _make_member('plainstaff')
        member.groups.add(self.group)
        self.client.force_login(member, backend='members.backends.AuthBackend')

        response = self.client.get(reverse('admin:ctf_postmortem_changelist'))

        self.assertEqual(response.status_code, 403)

    def test_flag_inline_exposes_solution_field(self):
        editor = self._editor(('ctf', 'change_ctf'), ('ctf', 'change_flag'))
        _make_flag(self.ctf, 'Inline flag', 'inline-flag', solution='Inline solution')

        response = self.client.get(reverse('admin:ctf_ctf_change', args=[self.ctf.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'flag_set-0-solution')

        request = RequestFactory().get('/admin/')
        request.user = editor
        self.assertIn('solution', FlagInline(Ctf, admin.site).get_fields(request, self.ctf))

    def test_view_only_postmortem_permission_is_read_only(self):
        post_mortem = PostMortem.objects.create(ctf=self.ctf)
        self._editor(('ctf', 'view_postmortem'))
        published_time = timezone.localtime(timezone.now() - timezone.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')

        changelist_response = self.client.get(reverse('admin:ctf_postmortem_changelist'))
        add_response = self.client.get(reverse('admin:ctf_postmortem_add'))
        change_response = self.client.get(reverse('admin:ctf_postmortem_change', args=[post_mortem.pk]))
        write_response = self.client.post(
            reverse('admin:ctf_postmortem_change', args=[post_mortem.pk]),
            {'ctf': self.ctf.pk, 'published_time': published_time},
        )
        delete_response = self.client.post(reverse('admin:ctf_postmortem_delete', args=[post_mortem.pk]))

        self.assertEqual(changelist_response.status_code, 200)
        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(change_response.status_code, 200)
        # Read-only means read-only: neither a write nor a delete may take effect.
        self.assertEqual(write_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        post_mortem.refresh_from_db()
        self.assertIsNone(post_mortem.published_time)
        self.assertTrue(PostMortem.objects.filter(pk=post_mortem.pk).exists())

    def test_explicit_change_postmortem_permission_allows_write_without_escalation(self):
        # Deliberate, pinned decision: the `or super()` fallback stays in
        # PostMortemAdmin, so an explicit ctf.change_postmortem grant lets a
        # staff member write post-mortems. It grants nothing on the CTF, Flag
        # or Guess admins, so it cannot escalate beyond the post-mortem model.
        # Django's add view separately requires ctf.add_postmortem, so the write
        # path pinned here is the change form.
        post_mortem = PostMortem.objects.create(ctf=self.ctf)
        self._editor(('ctf', 'change_postmortem'))
        published_time = timezone.localtime(timezone.now() - timezone.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')

        change_response = self.client.get(reverse('admin:ctf_postmortem_change', args=[post_mortem.pk]))
        write_response = self.client.post(
            reverse('admin:ctf_postmortem_change', args=[post_mortem.pk]),
            {'ctf': self.ctf.pk, 'published_time': published_time},
        )
        add_response = self.client.get(reverse('admin:ctf_postmortem_add'))
        ctf_response = self.client.get(reverse('admin:ctf_ctf_changelist'))
        flag_response = self.client.get(reverse('admin:ctf_flag_changelist'))
        guess_response = self.client.get(reverse('admin:ctf_guess_changelist'))

        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(write_response.status_code, 302)
        post_mortem.refresh_from_db()
        self.assertIsNotNone(post_mortem.published_time)
        # Adding a post-mortem still needs ctf.add_postmortem.
        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(ctf_response.status_code, 403)
        self.assertEqual(flag_response.status_code, 403)
        self.assertEqual(guess_response.status_code, 403)
