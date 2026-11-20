"""Regression tests for the indexes the admin performance work depends on.

Each index backs an admin changelist ordering, a date hierarchy or an inline
filter. Pinning the names here means a future model edit cannot silently drop
one of them without a test failure.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from billing.models import EventInvoice
from booking.models import Booking, Closure
from ctf.models import Guess
from gallery.models import Album
from news.models import Post
from publications.models import PDFFile


def index_names(model):
    return {index.name for index in model._meta.indexes}


class AdminPerformanceIndexTests(SimpleTestCase):
    def assert_declares_index(self, model, name):
        self.assertIn(name, index_names(model), msg=f'{model._meta.label} lost index {name}')

    def test_news_post_created_time_index(self):
        self.assert_declares_index(Post, 'post_created_idx')

    def test_publications_pdffile_indexes(self):
        self.assert_declares_index(PDFFile, 'pdffile_uploaded_idx')
        self.assert_declares_index(PDFFile, 'pdffile_pubdate_idx')

    def test_ctf_guess_timestamp_index(self):
        self.assert_declares_index(Guess, 'guess_timestamp_idx')

    def test_billing_eventinvoice_invoice_date_index(self):
        self.assert_declares_index(EventInvoice, 'invoice_date_idx')

    def test_booking_booking_indexes(self):
        self.assert_declares_index(Booking, 'booking_room_start_idx')
        self.assert_declares_index(Booking, 'booking_room_end_idx')

    def test_booking_closure_indexes(self):
        self.assert_declares_index(Closure, 'closure_room_start_idx')
        self.assert_declares_index(Closure, 'closure_room_end_idx')

    def test_gallery_album_pubdate_index(self):
        self.assert_declares_index(Album, 'album_pubdate_idx')

    def test_admin_log_index_migration_exists(self):
        migrations_dir = Path(settings.BASE_DIR) / 'date' / 'migrations'
        self.assertTrue((migrations_dir / '__init__.py').is_file())
        migration = migrations_dir / '0001_admin_log_action_time_idx.py'
        self.assertTrue(migration.is_file())
        source = migration.read_text(encoding='utf-8')
        self.assertIn('django_admin_log_action_time_idx', source)
        # IF NOT EXISTS would otherwise accept an index left invalid by an
        # interrupted concurrent build, and the migration job retries on
        # failure, so the migration verifies validity before succeeding.
        self.assertIn('indisvalid', source)
