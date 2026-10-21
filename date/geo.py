"""Resolve an association address to coordinates for the lunch widget."""

import logging
import time
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
CACHE_KEY = 'lunch-coordinates:{project}'
CACHE_TIMEOUT = 30 * 24 * 60 * 60
MAX_AGE = 7 * 24 * 60 * 60
REQUEST_TIMEOUT = 10
USER_AGENT = 'date-website-geocoder/1.0 ({email})'


class GeocodeError(Exception):
    """Nominatim did not return a usable result."""


def cache_key() -> str:
    project = getattr(settings, 'PROJECT_NAME', 'date')
    return CACHE_KEY.format(project=project)


def cached() -> dict[str, Any] | None:
    """Return the cached coordinate record, or None when it cannot be read."""
    try:
        value = cache.get(cache_key())
    except Exception:
        logger.warning('Could not read the lunch coordinate cache.', exc_info=True)
        return None
    return value if isinstance(value, dict) else None


def cached_coordinates() -> tuple[float, float] | None:
    """Return the cached coordinates when they are present and valid."""
    value = cached()
    if value is None:
        return None
    try:
        lat = float(value['lat'])
        lng = float(value['lng'])
    except KeyError, TypeError, ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def association_address() -> str:
    variables = getattr(settings, 'CONTENT_VARIABLES', {}) or {}
    parts = (
        variables.get('ASSOCIATION_ADDRESS_L1'),
        variables.get('ASSOCIATION_ADDRESS_L2'),
        variables.get('ASSOCIATION_POSTAL_CODE'),
    )
    return ', '.join(str(part).strip() for part in parts if part and str(part).strip())


def association_email() -> str:
    variables = getattr(settings, 'CONTENT_VARIABLES', {}) or {}
    return str(variables.get('ASSOCIATION_EMAIL') or 'date@abo.fi')


def geocode(address: str) -> dict[str, Any]:
    """Resolve an address with Nominatim and return its coordinates.

    The command is the only caller; the request path never geocodes.
    """
    response = requests.get(
        NOMINATIM_URL,
        params={'q': address, 'format': 'jsonv2', 'limit': '1', 'countrycodes': 'fi'},
        headers={'User-Agent': USER_AGENT.format(email=association_email())},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise GeocodeError('Nominatim returned no match')
    result = results[0]
    return {
        'lat': float(result['lat']),
        'lng': float(result['lon']),
        'display_name': str(result.get('display_name') or ''),
    }


def store_coordinates(result: dict[str, Any], address: str) -> dict[str, Any]:
    value = {
        'lat': result['lat'],
        'lng': result['lng'],
        'cached_at': time.time(),
        'address': address,
        'display_name': result.get('display_name', ''),
    }
    cache.set(cache_key(), value, CACHE_TIMEOUT)
    return value
