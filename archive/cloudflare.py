import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger("date")


class CloudflareImagesError(Exception):
    pass


class CloudflareImagesClient:
    api_base_template = "https://api.cloudflare.com/client/v4/accounts/{account_id}/images"

    def __init__(self):
        self.account_id = settings.CF_IMAGES_ACCOUNT_ID
        self.api_token = settings.CF_IMAGES_API_TOKEN
        self.delivery_base_url = settings.CF_IMAGES_DELIVERY_BASE_URL.rstrip("/")
        self.default_variant = settings.CF_IMAGES_DEFAULT_VARIANT

    @classmethod
    def is_configured(cls):
        return bool(
            settings.CF_IMAGES_ACCOUNT_ID
            and settings.CF_IMAGES_API_TOKEN
            and settings.CF_IMAGES_DELIVERY_BASE_URL
        )

    def _ensure_configured(self):
        if not self.is_configured():
            raise ImproperlyConfigured("Cloudflare Images is not configured.")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}",
        }

    def _api_base(self):
        return self.api_base_template.format(account_id=self.account_id)

    def build_variant_url(self, image_id, variant=None):
        selected_variant = variant or self.default_variant
        return f"{self.delivery_base_url}/{image_id}/{selected_variant}"

    def create_direct_upload(self):
        self._ensure_configured()
        try:
            response = requests.post(
                f"{self._api_base()}/v2/direct_upload",
                headers=self._headers(),
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Cloudflare direct upload request failed: %s", exc)
            raise CloudflareImagesError("Unable to create direct upload URL.") from exc
        if not response.ok or not payload.get("success"):
            logger.warning("Cloudflare direct upload failed: %s", payload)
            raise CloudflareImagesError("Unable to create direct upload URL.")

        result = payload.get("result", {})
        return {
            "id": result["id"],
            "upload_url": result["uploadURL"],
        }

    def get_image(self, image_id):
        self._ensure_configured()
        try:
            response = requests.get(
                f"{self._api_base()}/v1/{image_id}",
                headers=self._headers(),
                timeout=15,
            )
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Cloudflare image fetch request failed for %s: %s", image_id, exc)
            raise CloudflareImagesError("Unable to verify uploaded image.") from exc
        if not response.ok or not payload.get("success"):
            logger.warning("Cloudflare image fetch failed for %s: %s", image_id, payload)
            raise CloudflareImagesError("Unable to verify uploaded image.")
        return payload.get("result", {})
