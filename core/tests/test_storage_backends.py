from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from core.storage_backends import PrivateMediaStorage, PublicMediaStorage

SIGNED_URL = (
    "https://s3.eu-central-003.backblazeb2.com/date-media/date/media/foo/secret.pdf"
    "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=key"
    "&X-Amz-Date=20260807T000000Z&X-Amz-Signature=abc123"
)


class _FakeConnection:
    def __init__(self, client):
        self.meta = SimpleNamespace(client=client)


def make_private_storage(**kwargs):
    storage = PrivateMediaStorage(
        bucket_name="date-media",
        location="date/media",
        querystring_auth=True,
        **kwargs,
    )
    storage._bucket = SimpleNamespace(name="date-media")
    client = Mock()
    client.generate_presigned_url.return_value = SIGNED_URL
    storage._connections.connection = _FakeConnection(client)
    return storage, client


class PrivateMediaStorageCustomDomainTests(SimpleTestCase):
    def test_presigned_url_with_swapped_host(self):
        storage, client = make_private_storage(custom_domain="media.example.com")
        url = storage.url("foo/secret.pdf")
        self.assertTrue(url.startswith("https://media.example.com/date-media/date/media/foo/secret.pdf?"))
        self.assertIn("X-Amz-Signature=abc123", url)
        client.generate_presigned_url.assert_called_once()
        call_kwargs = client.generate_presigned_url.call_args.kwargs
        self.assertEqual(
            call_kwargs["Params"],
            {"Bucket": "date-media", "Key": "date/media/foo/secret.pdf"},
        )
        self.assertEqual(call_kwargs["ExpiresIn"], 3600)
        self.assertIsNone(call_kwargs["HttpMethod"])

    def test_custom_domain_with_scheme_and_trailing_slash(self):
        storage, _ = make_private_storage(custom_domain="https://media.example.com/")
        url = storage.url("foo/secret.pdf")
        self.assertTrue(url.startswith("https://media.example.com/date-media/"))

    def test_expire_and_parameters_passthrough(self):
        storage, client = make_private_storage(custom_domain="media.example.com")
        storage.url(
            "foo/secret.pdf",
            parameters={"ResponseContentDisposition": "attachment"},
            expire=120,
        )
        call_kwargs = client.generate_presigned_url.call_args.kwargs
        self.assertEqual(call_kwargs["ExpiresIn"], 120)
        self.assertEqual(call_kwargs["Params"]["ResponseContentDisposition"], "attachment")

    def test_without_custom_domain_uses_endpoint_host(self):
        storage, client = make_private_storage()
        url = storage.url("foo/secret.pdf")
        self.assertEqual(url, SIGNED_URL)
        client.generate_presigned_url.assert_called_once()


class PublicMediaStorageCustomDomainTests(SimpleTestCase):
    def test_custom_domain_returns_unsigned_url_with_location(self):
        storage = PublicMediaStorage(
            bucket_name="date-media",
            location="date/public",
            querystring_auth=False,
            custom_domain="media.example.com",
        )
        url = storage.url("foo/bar.jpg")
        self.assertEqual(url, "https://media.example.com/date/public/foo/bar.jpg")
        self.assertNotIn("X-Amz-Signature", url)
