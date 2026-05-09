from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from archive.models import Collection
from news.models import Post
from publications.models import PDFFile
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


WORDPRESS_EXPORT = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
    xmlns:content="http://purl.org/rss/1.0/modules/content/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
    xmlns:wp="http://wordpress.org/export/1.2/">
  <channel>
    <item>
      <title><![CDATA[Imported News]]></title>
      <link>https://sfklubben.fi/imported-news/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[<p>Hello <img src="https://sfklubben.fi/wp-content/uploads/2026/05/news-image.jpg"></p>

<span>Loose WordPress line</span>

Plain ending<script>bad()</script>]]></content:encoded>
      <excerpt:encoded><![CDATA[]]></excerpt:encoded>
      <wp:post_id>10</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_modified>2026-05-09 11:00:00</wp:post_modified>
      <wp:post_name><![CDATA[imported-news]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[post]]></wp:post_type>
      <category domain="category" nicename="nyheter"><![CDATA[Nyheter]]></category>
    </item>
    <item>
      <title><![CDATA[Imported Page]]></title>
      <link>https://sfklubben.fi/imported-page/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[<p>Page body</p>]]></content:encoded>
      <excerpt:encoded><![CDATA[]]></excerpt:encoded>
      <wp:post_id>11</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[imported-page]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[page]]></wp:post_type>
    </item>
    <item>
      <title><![CDATA[Bildgalleriet]]></title>
      <link>https://sfklubben.fi/bildgalleriet/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[
        <a href="https://photos.app.goo.gl/exampleAlbum">2025 - Testalbum</a>
        <a href="https://drive.google.com/drive/folders/example">2024 - Drivealbum</a>
      ]]></content:encoded>
      <excerpt:encoded><![CDATA[]]></excerpt:encoded>
      <wp:post_id>13</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[bildgalleriet]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[page]]></wp:post_type>
    </item>
    <item>
      <title><![CDATA[Imported PDF]]></title>
      <link>https://sfklubben.fi/imported-pdf/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[]]></content:encoded>
      <excerpt:encoded><![CDATA[PDF description]]></excerpt:encoded>
      <wp:post_id>12</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[imported-pdf]]></wp:post_name>
      <wp:status><![CDATA[inherit]]></wp:status>
      <wp:post_type><![CDATA[attachment]]></wp:post_type>
      <wp:attachment_url><![CDATA[https://sfklubben.fi/wp-content/uploads/2026/05/imported.pdf]]></wp:attachment_url>
    </item>
    <item>
      <title><![CDATA[Imported Page]]></title>
      <wp:post_id>20</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[imported-page-menu]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[nav_menu_item]]></wp:post_type>
      <wp:menu_order>1</wp:menu_order>
      <category domain="nav_menu" nicename="actual"><![CDATA[Actual]]></category>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_type]]></wp:meta_key><wp:meta_value><![CDATA[post_type]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object]]></wp:meta_key><wp:meta_value><![CDATA[page]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object_id]]></wp:meta_key><wp:meta_value><![CDATA[11]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_menu_item_parent]]></wp:meta_key><wp:meta_value><![CDATA[0]]></wp:meta_value></wp:postmeta>
    </item>
    <item>
      <title><![CDATA[Imported PDF Link]]></title>
      <wp:post_id>21</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[imported-pdf-link]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[nav_menu_item]]></wp:post_type>
      <wp:menu_order>2</wp:menu_order>
      <category domain="nav_menu" nicename="actual"><![CDATA[Actual]]></category>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_type]]></wp:meta_key><wp:meta_value><![CDATA[custom]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object]]></wp:meta_key><wp:meta_value><![CDATA[custom]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object_id]]></wp:meta_key><wp:meta_value><![CDATA[21]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_url]]></wp:meta_key><wp:meta_value><![CDATA[/wp-content/uploads/2026/05/imported.pdf]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_menu_item_parent]]></wp:meta_key><wp:meta_value><![CDATA[20]]></wp:meta_value></wp:postmeta>
    </item>
  </channel>
</rss>
"""


class WordPressImportCommandTests(TestCase):
    def test_imports_posts_pages_publications_and_rewrites_media(self):
        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            work_path = Path(work_dir)
            xml_path = work_path / "export.xml"
            media_dir = work_path / "downloads" / "sfklubben.fi"
            uploads = media_dir / "wp-content" / "uploads" / "2026" / "05"
            uploads.mkdir(parents=True)
            (uploads / "news-image.jpg").write_bytes(b"image")
            (uploads / "imported.pdf").write_bytes(b"%PDF-1.4")
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            call_command(
                "import_wordpress_export",
                str(xml_path),
                "--media-dir",
                str(media_dir),
                "--media-prefix",
                "wordpress/test",
                verbosity=0,
            )

            post = Post.objects.get(slug="imported-news")
            self.assertIn("/media/wordpress/test/wp-content/uploads/2026/05/news-image.jpg", post.content)
            self.assertIn("<p><span>Loose WordPress line</span></p>", post.content)
            self.assertIn("<p>Plain ending</p>", post.content)
            self.assertNotIn("<script>", post.content)
            self.assertIsNone(post.category)

            page = StaticPage.objects.get(slug="imported-page")
            self.assertEqual(page.title, "Imported Page")

            pdf = PDFFile.objects.get(slug="imported-pdf")
            self.assertEqual(pdf.file.name, "wordpress/test/wp-content/uploads/2026/05/imported.pdf")
            self.assertTrue((Path(work_dir) / "media" / pdf.file.name).exists())

    def test_imports_navigation(self):
        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            work_path = Path(work_dir)
            xml_path = work_path / "export.xml"
            media_dir = work_path / "downloads" / "sfklubben.fi"
            uploads = media_dir / "wp-content" / "uploads" / "2026" / "05"
            uploads.mkdir(parents=True)
            (uploads / "news-image.jpg").write_bytes(b"image")
            (uploads / "imported.pdf").write_bytes(b"%PDF-1.4")
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            call_command(
                "import_wordpress_export",
                str(xml_path),
                "--media-dir",
                str(media_dir),
                "--media-prefix",
                "wordpress/test",
                "--import-nav",
                "--replace-nav",
                verbosity=0,
            )

            category = StaticPageNav.objects.get(category_name="Imported Page")
            self.assertFalse(category.use_category_url)
            urls = list(StaticUrl.objects.filter(category=category).order_by("dropdown_element"))
            self.assertEqual([url.title for url in urls], ["Imported Page", "Imported PDF Link"])
            self.assertEqual(urls[0].url, "/pages/imported-page/")
            self.assertEqual(urls[1].url, "/media/wordpress/test/wp-content/uploads/2026/05/imported.pdf")

    def test_imports_gallery_redirect_albums(self):
        with TemporaryDirectory() as work_dir:
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            call_command(
                "import_wordpress_export",
                str(xml_path),
                "--skip-media",
                "--skip-publications",
                "--import-gallery-redirects",
                verbosity=0,
            )

            photos_album = Collection.objects.get(title="2025 - Testalbum", type="Pictures")
            self.assertEqual(photos_album.redirect_url, "https://photos.app.goo.gl/exampleAlbum")
            self.assertEqual(photos_album.pub_date.year, 2025)

            drive_album = Collection.objects.get(title="2024 - Drivealbum", type="Pictures")
            self.assertEqual(drive_album.redirect_url, "https://drive.google.com/drive/folders/example")
            self.assertEqual(drive_album.pub_date.year, 2024)

    def test_dry_run_does_not_write_rows(self):
        with TemporaryDirectory() as work_dir:
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            call_command(
                "import_wordpress_export",
                str(xml_path),
                "--dry-run",
                "--skip-media",
                "--skip-publications",
                verbosity=0,
            )

            self.assertFalse(Post.objects.filter(slug="imported-news").exists())
            self.assertFalse(StaticPage.objects.filter(slug="imported-page").exists())
