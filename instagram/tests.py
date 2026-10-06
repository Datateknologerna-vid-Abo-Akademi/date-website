import sys
import tempfile
from io import BytesIO, StringIO
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from instagram.admin import IgUrlAdmin
from instagram.models import IgUrl
from instagram.templatetags.instagram_slider import conveyor


class InstagramLegacyAdminPermissionTests(TestCase):
    def test_legacy_social_permissions_preserve_admin_access(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                has_module_perms=Mock(return_value=False),
                has_perm=Mock(side_effect=lambda permission: permission.startswith('social.')),
            )
        )
        model_admin = IgUrlAdmin(IgUrl, admin.site)

        self.assertTrue(model_admin.has_module_permission(request))
        self.assertTrue(model_admin.has_change_permission(request))


class FakeInstaloaderException(Exception):
    pass


def fake_instaloader(posts=(), error=None):
    def get_posts():
        yield from posts
        if error:
            raise error

    module = ModuleType("instaloader")
    module.InstaloaderException = FakeInstaloaderException
    module.Instaloader = Mock(return_value=SimpleNamespace(context="context"))
    module.Profile = SimpleNamespace(from_username=Mock(return_value=SimpleNamespace(get_posts=get_posts)))
    return module


def fake_post(number):
    return SimpleNamespace(url=f"https://cdn.example/{number}.jpg", shortcode=f"Post{number}")


@override_settings(INSTAGRAM_USERNAME="impulsrf")
class UpdateInstagramCommandTests(TestCase):
    def setUp(self):
        IgUrl.objects.create(url="https://cdn.example/old.jpg", shortcode="Old")

    def run_command(self, instaloader):
        with patch.dict(sys.modules, {"instaloader": instaloader}):
            call_command("update_instagram", stdout=StringIO())

    def stored(self):
        return list(IgUrl.objects.order_by("shortcode").values_list("url", "shortcode"))

    def test_replaces_stored_posts_with_the_configured_profiles_posts(self):
        instaloader = fake_instaloader(posts=[fake_post(1), fake_post(2)])

        self.run_command(instaloader)

        instaloader.Profile.from_username.assert_called_once_with("context", "impulsrf")
        self.assertEqual(
            self.stored(),
            [("https://cdn.example/1.jpg", "Post1"), ("https://cdn.example/2.jpg", "Post2")],
        )

    def test_keeps_instagrams_newest_first_order(self):
        self.run_command(fake_instaloader(posts=[fake_post(1), fake_post(2)]))

        self.assertEqual(list(IgUrl.objects.values_list("shortcode", flat=True)), ["Post1", "Post2"])

    def test_leaves_posts_with_uploaded_images_alone(self):
        IgUrl.objects.create(image="instagram/uploaded.png", shortcode="Uploaded")

        self.run_command(fake_instaloader(posts=[fake_post(1)]))

        self.assertEqual(
            sorted(IgUrl.objects.values_list("shortcode", flat=True)),
            ["Post1", "Uploaded"],
        )

    def test_stores_at_most_forty_posts(self):
        self.run_command(fake_instaloader(posts=[fake_post(number) for number in range(45)]))

        self.assertEqual(IgUrl.objects.count(), 40)

    def test_keeps_stored_posts_when_the_fetch_fails_partway(self):
        instaloader = fake_instaloader(posts=[fake_post(1)], error=FakeInstaloaderException("rate limited"))

        with self.assertRaises(CommandError):
            self.run_command(instaloader)

        self.assertEqual(self.stored(), [("https://cdn.example/old.jpg", "Old")])

    def test_keeps_stored_posts_when_the_profile_has_no_posts(self):
        with self.assertRaises(CommandError):
            self.run_command(fake_instaloader(posts=[]))

        self.assertEqual(self.stored(), [("https://cdn.example/old.jpg", "Old")])

    @override_settings(INSTAGRAM_USERNAME="")
    def test_requires_a_configured_profile(self):
        instaloader = fake_instaloader(posts=[fake_post(1)])

        with self.assertRaisesMessage(CommandError, "INSTAGRAM_USERNAME"):
            self.run_command(instaloader)

        instaloader.Instaloader.assert_not_called()
        self.assertEqual(self.stored(), [("https://cdn.example/old.jpg", "Old")])

    def test_explains_how_to_install_instaloader_when_missing(self):
        with self.assertRaisesMessage(CommandError, "uv sync --extra instagram"):
            self.run_command(None)


class IgUrlModelTests(TestCase):
    def test_clean_turns_a_pasted_post_link_into_its_shortcode(self):
        for link in (
            "https://www.instagram.com/p/ABC_12-3/",
            "https://www.instagram.com/p/ABC_12-3/?igsh=xyz",
            "https://www.instagram.com/impulsrf/p/ABC_12-3/",
            "https://www.instagram.com/reel/ABC_12-3/",
            "ABC_12-3",
        ):
            with self.subTest(link=link):
                post = IgUrl(image="instagram/post.png", shortcode=link)
                post.full_clean()
                self.assertEqual(post.shortcode, "ABC_12-3")

    def test_clean_requires_an_image_or_an_image_address(self):
        with self.assertRaises(ValidationError) as raised:
            IgUrl(shortcode="ABC123").full_clean()

        self.assertIn("image", raised.exception.message_dict)

    def test_image_url_prefers_the_uploaded_image(self):
        self.assertEqual(
            IgUrl(image="instagram/post.png", url="https://cdn.example/x.jpg").image_url,
            "/media/instagram/post.png",
        )
        self.assertEqual(IgUrl(url="https://cdn.example/x.jpg").image_url, "https://cdn.example/x.jpg")


def png(width, height):
    buffer = BytesIO()
    Image.new("RGB", (width, height)).save(buffer, format="PNG")
    return SimpleUploadedFile("post.png", buffer.getvalue(), content_type="image/png")


class IgUrlAdminUploadTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(username="igadmin", email="ig@example.com", password="pass")
        self.client.force_login(user, backend="members.backends.AuthBackend")
        media_root = tempfile.TemporaryDirectory()
        self.addCleanup(media_root.cleanup)
        media_override = override_settings(MEDIA_ROOT=media_root.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def add_post(self, image, shortcode="ABC123"):
        return self.client.post(
            reverse("admin:instagram_igurl_add"),
            {"image": image, "shortcode": shortcode, "url": "", "_save": "Save"},
        )

    def test_board_member_can_add_a_post_with_an_image_and_its_link(self):
        response = self.add_post(png(300, 300), shortcode="https://www.instagram.com/p/ABC123/?igsh=xyz")

        self.assertEqual(response.status_code, 302)
        post = IgUrl.objects.get(shortcode="ABC123")
        self.assertTrue(post.image.name.startswith("instagram/post"))

    def test_rejects_an_image_too_small_to_stay_sharp(self):
        response = self.add_post(png(300, 299))

        self.assertContains(response, "Bilden är för liten (299 px hög)")
        self.assertFalse(IgUrl.objects.exists())

    def test_rejects_a_renamed_file_that_is_not_an_image(self):
        response = self.add_post(SimpleUploadedFile("post.png", b"not an image", content_type="image/png"))

        self.assertContains(response, "Filen är inte en bild.")
        self.assertFalse(IgUrl.objects.exists())

    def test_rejects_a_file_without_an_image_extension(self):
        response = self.add_post(SimpleUploadedFile("notes.txt", b"text", content_type="text/plain"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(IgUrl.objects.exists())

    def test_editing_a_post_does_not_recheck_its_stored_image(self):
        post = IgUrl.objects.create(image="instagram/already-stored.png", shortcode="Old")

        response = self.client.post(
            reverse("admin:instagram_igurl_change", args=[post.pk]),
            {"shortcode": "New", "url": "", "_save": "Save"},
        )

        self.assertEqual(response.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.shortcode, "New")


class ConveyorFilterTests(SimpleTestCase):
    def test_repeats_few_posts_until_each_half_is_full_then_doubles_the_track(self):
        track = conveyor(["a", "b", "c"], 7)

        self.assertEqual([post for post, _ in track], list("abcabcabc") * 2)

    def test_only_the_first_occurrence_of_each_post_is_not_a_repeat(self):
        track = conveyor(["a", "b", "c"], 7)

        self.assertEqual([post for post, is_repeat in track if not is_repeat], ["a", "b", "c"])
        self.assertEqual([is_repeat for _, is_repeat in track[:3]], [False, False, False])

    def test_many_posts_are_not_repeated_within_a_half(self):
        posts = [str(number) for number in range(20)]

        self.assertEqual([post for post, _ in conveyor(posts)], posts * 2)

    def test_no_posts_gives_an_empty_track(self):
        self.assertEqual(conveyor([]), [])
