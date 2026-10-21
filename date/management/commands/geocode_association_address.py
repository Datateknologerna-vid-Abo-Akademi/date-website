"""Geocode the association address and cache it for the lunch widget."""

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from date import geo


class Command(BaseCommand):
    help = "Resolve the association address to coordinates and cache them for the lunch widget."

    def add_arguments(self, parser):
        parser.add_argument('--address', help='Address to geocode instead of the association address.')
        parser.add_argument('--force', action='store_true', help='Ignore a fresh cached result.')

    def handle(self, *args, **options):
        cached = geo.cached()
        if cached and not options['force']:
            try:
                fresh = time.time() - float(cached.get('cached_at')) < geo.MAX_AGE
            except TypeError, ValueError:
                fresh = False
            if fresh:
                self.stdout.write(
                    f"Using cached coordinates for {settings.PROJECT_NAME}: {cached.get('lat')}, {cached.get('lng')}"
                )
                return

        address = (options['address'] or geo.association_address()).strip()
        if not address:
            self.stderr.write(self.style.WARNING('No association address; the widget will fall back to the city.'))
            return

        try:
            result = geo.geocode(address)
        except Exception as exc:
            self.stderr.write(
                self.style.WARNING(
                    f'Could not geocode {address!r}: {exc}. Keeping the cached coordinates or falling back to the city.'
                )
            )
            return

        try:
            value = geo.store_coordinates(result, address)
        except Exception as exc:
            self.stderr.write(
                self.style.WARNING(
                    f'Geocoded {address!r} but could not cache the coordinates: {exc}. '
                    'The widget will fall back to the city.'
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Geocoded {address!r} to {value['lat']}, {value['lng']}."))
        self.stdout.write(f'Matched: {value.get("display_name") or "-"}')
        self.stdout.write(f'Cached under {geo.cache_key()}.')
