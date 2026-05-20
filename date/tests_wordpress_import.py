from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse

from django.core.management import call_command
from django.test import TestCase, override_settings

from exambank.models import ExamArchive, ExamFile
from functionaries.models import Functionary, FunctionaryRole
from gallery.models import Album
from news.models import Post
from publications.models import PDFFile, PublicationCollection
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


def _php_str(value: str) -> str:
    return f's:{len(value.encode("utf-8"))}:"{value}";'


def _php_int_key(value: int) -> str:
    return f"i:{value};"


def _php_assoc(pairs: list[tuple[str, str]]) -> str:
    inner = "".join(k + v for k, v in pairs)
    return f"a:{len(pairs)}:{{{inner}}}"


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
      <title><![CDATA[Funktionärer]]></title>
      <link>https://sfklubben.fi/funktionarer/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[
        <h5><strong>Styrelse 2026</strong></h5>
        <strong>Ordförande&nbsp;</strong>Ylva Erlin
        <strong>Skattmästare </strong>Linn Ahlskog
        <h5>Styrelse 2025</h5>
        <strong>Ordförande </strong>Antonia Holmberg
      ]]></content:encoded>
      <excerpt:encoded><![CDATA[]]></excerpt:encoded>
      <wp:post_id>14</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[funktionarer]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[page]]></wp:post_type>
    </item>
    <item>
      <title><![CDATA[A&O]]></title>
      <link>https://sfklubben.fi/ao/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[
        <h1><strong>2026</strong></h1>
        <table>
          <tbody>
            <tr><td>01/2026</td><td>02/2026</td></tr>
            <tr>
              <td><a href="https://issuu.com/sfklubben/docs/ao-1-2026"><img src="/wp-content/uploads/2026/05/ao1.jpg" alt="" /></a></td>
              <td><a href="https://issuu.com/sfklubben/docs/ao-2-2026"><img src="/wp-content/uploads/2026/05/ao2.jpg" alt="" /></a></td>
            </tr>
          </tbody>
        </table>
      ]]></content:encoded>
      <excerpt:encoded><![CDATA[Argument och Opinion på Issuu]]></excerpt:encoded>
      <wp:post_id>15</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[ao]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[page]]></wp:post_type>
    </item>
    <item>
      <title><![CDATA[aologo]]></title>
      <wp:post_id>16</wp:post_id>
      <wp:post_date>2022-04-13 23:45:52</wp:post_date>
      <wp:post_name><![CDATA[aologo]]></wp:post_name>
      <wp:status><![CDATA[inherit]]></wp:status>
      <wp:post_type><![CDATA[attachment]]></wp:post_type>
      <wp:attachment_url><![CDATA[http://sfklubben.fi/wp-content/uploads/2022/04/aologo.png]]></wp:attachment_url>
    </item>
    <item>
      <title><![CDATA[Politicus]]></title>
      <link>https://sfklubben.fi/politicus/</link>
      <pubDate>Sat, 09 May 2026 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[
        <table>
          <tbody>
            <tr>
              <td><h2>2025<a href="https://issuu.com/sfklubben/docs/politicus-2025"><img src="/wp-content/uploads/2025/11/Politicus-2025.png" alt="" /></a></h2></td>
              <td><h2>2019<a href="/politicus-4/"><img src="/wp-content/uploads/2019/11/Politicus2019-01.jpg" alt="" /></a></h2></td>
            </tr>
          </tbody>
        </table>
      ]]></content:encoded>
      <excerpt:encoded><![CDATA[Politicus publications]]></excerpt:encoded>
      <wp:post_id>17</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[politicus]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[page]]></wp:post_type>
    </item>
    <item>
      <title><![CDATA[politicuslogo]]></title>
      <wp:post_id>18</wp:post_id>
      <wp:post_date>2022-04-13 23:48:02</wp:post_date>
      <wp:post_name><![CDATA[politicuslogo]]></wp:post_name>
      <wp:status><![CDATA[inherit]]></wp:status>
      <wp:post_type><![CDATA[attachment]]></wp:post_type>
      <wp:attachment_url><![CDATA[http://sfklubben.fi/wp-content/uploads/2022/04/politicuslogo.png]]></wp:attachment_url>
    </item>
    <item>
      <title><![CDATA[Politicus 2019]]></title>
      <link>https://sfklubben.fi/politicus-4/</link>
      <content:encoded><![CDATA[
        <a href="/wp-content/uploads/2019/11/Politicus2019.pdf">Läs som PDF</a>
        <a href="https://sfklubben.fi/politicus/">Tillbaka</a>
      ]]></content:encoded>
      <wp:post_id>19</wp:post_id>
      <wp:post_date>2019-11-01 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[politicus-4]]></wp:post_name>
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
    <item>
      <title><![CDATA[Nested Child]]></title>
      <wp:post_id>22</wp:post_id>
      <wp:post_date>2026-05-09 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[nested-child]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[nav_menu_item]]></wp:post_type>
      <wp:menu_order>3</wp:menu_order>
      <category domain="nav_menu" nicename="actual"><![CDATA[Actual]]></category>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_type]]></wp:meta_key><wp:meta_value><![CDATA[custom]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object]]></wp:meta_key><wp:meta_value><![CDATA[custom]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_object_id]]></wp:meta_key><wp:meta_value><![CDATA[22]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_url]]></wp:meta_key><wp:meta_value><![CDATA[/nested-child/]]></wp:meta_value></wp:postmeta>
      <wp:postmeta><wp:meta_key><![CDATA[_menu_item_menu_item_parent]]></wp:meta_key><wp:meta_value><![CDATA[21]]></wp:meta_value></wp:postmeta>
    </item>
  </channel>
</rss>
"""


class WordPressImportCommandTests(TestCase):
    def call_import_command(self, *args):
        return call_command(
            "import_wordpress_export",
            *args,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    def test_imports_posts_pages_ao_publications_and_rewrites_media(self):
        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            work_path = Path(work_dir)
            xml_path = work_path / "export.xml"
            media_dir = work_path / "downloads" / "sfklubben.fi"
            uploads = media_dir / "wp-content" / "uploads" / "2026" / "05"
            uploads.mkdir(parents=True)
            logo_uploads = media_dir / "wp-content" / "uploads" / "2022" / "04"
            logo_uploads.mkdir(parents=True)
            (uploads / "news-image.jpg").write_bytes(b"image")
            (uploads / "imported.pdf").write_bytes(b"%PDF-1.4")
            (uploads / "ao1.jpg").write_bytes(b"ao cover 1")
            (uploads / "ao2.jpg").write_bytes(b"ao cover 2")
            (logo_uploads / "aologo.png").write_bytes(b"ao logo")
            (logo_uploads / "politicuslogo.png").write_bytes(b"politicus logo")
            politicus_2025_uploads = media_dir / "wp-content" / "uploads" / "2025" / "11"
            politicus_2025_uploads.mkdir(parents=True)
            (politicus_2025_uploads / "Politicus-2025.png").write_bytes(b"politicus cover 2025")
            politicus_2019_uploads = media_dir / "wp-content" / "uploads" / "2019" / "11"
            politicus_2019_uploads.mkdir(parents=True)
            (politicus_2019_uploads / "Politicus2019-01.jpg").write_bytes(b"politicus cover 2019")
            (politicus_2019_uploads / "Politicus2019.pdf").write_bytes(b"%PDF-1.4")
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            self.call_import_command(
                str(xml_path),
                "--media-dir",
                str(media_dir),
                "--media-prefix",
                "wordpress/test",
            )

            post = Post.objects.get(slug="imported-news")
            self.assertIn("/media/wordpress/test/wp-content/uploads/2026/05/news-image.jpg", post.content)
            self.assertIn("<p><span>Loose WordPress line</span></p>", post.content)
            self.assertIn("<p>Plain ending</p>", post.content)
            self.assertNotIn("<script>", post.content)
            self.assertIsNone(post.category)

            page = StaticPage.objects.get(slug="imported-page")
            self.assertEqual(page.title, "Imported Page")

            self.assertFalse(PDFFile.objects.filter(slug="imported-pdf").exists())
            self.assertTrue(
                (Path(work_dir) / "media" / "wordpress/test/wp-content/uploads/2026/05/imported.pdf").exists()
            )

            publication = PDFFile.objects.get(title="A&O 01/2026")
            self.assertEqual(publication.collection.slug, "ao")
            self.assertEqual(
                publication.collection.cover_image.name, "wordpress/test/wp-content/uploads/2022/04/aologo.png"
            )
            self.assertFalse(publication.file)
            self.assertEqual(publication.redirect_url, "https://issuu.com/sfklubben/docs/ao-1-2026")
            self.assertEqual(publication.cover_image.name, "wordpress/test/wp-content/uploads/2026/05/ao1.jpg")
            self.assertEqual(publication.publication_date.isoformat(), "2026-01-01")
            self.assertTrue(PDFFile.objects.filter(title="A&O 02/2026").exists())
            self.assertTrue(PublicationCollection.objects.filter(slug="ao", title="A&O").exists())

            politicus = PDFFile.objects.get(title="Politicus 2025")
            self.assertEqual(politicus.collection.slug, "politicus")
            self.assertEqual(
                politicus.collection.cover_image.name,
                "wordpress/test/wp-content/uploads/2022/04/politicuslogo.png",
            )
            self.assertEqual(politicus.redirect_url, "https://issuu.com/sfklubben/docs/politicus-2025")
            self.assertEqual(politicus.cover_image.name, "wordpress/test/wp-content/uploads/2025/11/politicus-2025.png")

            politicus_2019 = PDFFile.objects.get(title="Politicus 2019")
            self.assertFalse(politicus_2019.redirect_url)
            self.assertEqual(politicus_2019.file.name, "wordpress/test/wp-content/uploads/2019/11/politicus2019.pdf")
            self.assertEqual(
                politicus_2019.cover_image.name, "wordpress/test/wp-content/uploads/2019/11/politicus2019-01.jpg"
            )

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

            self.call_import_command(
                str(xml_path),
                "--media-dir",
                str(media_dir),
                "--media-prefix",
                "wordpress/test",
                "--import-nav",
                "--replace-nav",
            )

            category = StaticPageNav.objects.get(category_name="Imported Page")
            self.assertFalse(category.use_category_url)
            urls = list(StaticUrl.objects.filter(category=category, parent=None).order_by("dropdown_element"))
            self.assertEqual([url.title for url in urls], ["Imported Page", "Imported PDF Link"])
            self.assertEqual(urls[0].url, "/pages/imported-page/")
            self.assertEqual(urls[1].url, "/media/wordpress/test/wp-content/uploads/2026/05/imported.pdf")
            child_urls = list(urls[1].children.order_by("dropdown_element"))
            self.assertEqual([url.title for url in child_urls], ["Nested Child"])
            self.assertEqual(child_urls[0].url, "/nested-child/")

    def test_downloads_missing_media_when_requested(self):
        def fake_get(url, *args, **kwargs):
            response = type("FakeResponse", (), {})()
            response.raise_for_status = lambda: None
            response.content = b"%PDF-1.4 downloaded"
            return response

        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            work_path = Path(work_dir)
            xml_path = work_path / "export.xml"
            media_dir = work_path / "downloads" / "sfklubben.fi"
            media_dir.mkdir(parents=True)
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            with patch(
                "date.management.commands.import_wordpress_export.requests.get",
                side_effect=fake_get,
            ) as mocked:
                self.call_import_command(
                    str(xml_path),
                    "--media-dir",
                    str(media_dir),
                    "--media-prefix",
                    "wordpress/test",
                    "--download-missing-media",
                    "--skip-publications",
                )

            self.assertGreater(mocked.call_count, 0)
            self.assertTrue(
                (Path(work_dir) / "media" / "wordpress/test/wp-content/uploads/2026/05/imported.pdf").exists()
            )

    def test_imports_gallery_redirect_albums(self):
        with TemporaryDirectory() as work_dir:
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            self.call_import_command(
                str(xml_path),
                "--skip-media",
                "--skip-publications",
                "--import-gallery-redirects",
                "--skip-gallery-thumbnails",
            )

            photos_album = Album.objects.get(title="2025 - Testalbum")
            self.assertEqual(photos_album.redirect_url, "https://photos.app.goo.gl/exampleAlbum")
            self.assertEqual(photos_album.pub_date.year, 2025)
            self.assertFalse(photos_album.thumbnail)

            drive_album = Album.objects.get(title="2024 - Drivealbum")
            self.assertEqual(drive_album.redirect_url, "https://drive.google.com/drive/folders/example")
            self.assertEqual(drive_album.pub_date.year, 2024)

    def test_gallery_redirect_albums_fetch_og_thumbnail(self):
        share_html = (
            '<html><head>'
            '<meta property="og:image" content="https://lh3.googleusercontent.com/preview.jpg">'
            '</head><body></body></html>'
        )
        image_bytes = b"\x89PNG\r\n\x1a\n-fake-image-bytes-"

        def fake_get(url, *args, **kwargs):
            response = type("FakeResponse", (), {})()
            response.raise_for_status = lambda: None
            parsed_url = urlparse(url)
            if parsed_url.scheme == "https" and parsed_url.netloc in {
                "photos.app.goo.gl",
                "drive.google.com",
            }:
                response.text = share_html
                response.content = share_html.encode("utf-8")
            else:
                response.text = ""
                response.content = image_bytes
            return response

        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            with patch(
                "date.management.commands.import_wordpress_export.requests.get",
                side_effect=fake_get,
            ) as mocked:
                self.call_import_command(
                    str(xml_path),
                    "--skip-media",
                    "--skip-publications",
                    "--import-gallery-redirects",
                )

            self.assertGreaterEqual(mocked.call_count, 4)

            photos_album = Album.objects.get(title="2025 - Testalbum")
            self.assertTrue(photos_album.thumbnail)
            self.assertTrue(photos_album.thumbnail.name.endswith(".jpg"))
            with photos_album.thumbnail.open("rb") as fh:
                self.assertEqual(fh.read(), image_bytes)

            drive_album = Album.objects.get(title="2024 - Drivealbum")
            self.assertTrue(drive_album.thumbnail)

    def test_imports_functionaries_from_funktionarer_page(self):
        with TemporaryDirectory() as work_dir:
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            self.call_import_command(
                str(xml_path),
                "--skip-media",
                "--skip-publications",
                "--import-functionaries",
            )

            chair = FunctionaryRole.objects.get(title="Ordförande")
            treasurer = FunctionaryRole.objects.get(title="Skattmästare")
            self.assertTrue(chair.board)
            self.assertTrue(treasurer.board)

            self.assertTrue(
                Functionary.objects.filter(
                    functionary_role=chair,
                    year=2026,
                    name="Ylva Erlin",
                    member=None,
                ).exists()
            )
            self.assertTrue(
                Functionary.objects.filter(
                    functionary_role=treasurer,
                    year=2026,
                    name="Linn Ahlskog",
                    member=None,
                ).exists()
            )
            self.assertTrue(
                Functionary.objects.filter(
                    functionary_role=chair,
                    year=2025,
                    name="Antonia Holmberg",
                    member=None,
                ).exists()
            )

    def test_imports_exam_archive_from_rtbs_tabs(self):
        folkratt_pdf = "https://sfklubben.fi/wp-content/uploads/2024/04/Inledning-till-folkratt-29.2.2024-2.pdf"
        statskunskap_pdf = "https://sfklubben.fi/wp-content/uploads/2023/01/Val-och-valmetoder-14.10.2022.pdf"
        folkratt_tab = _php_assoc(
            [
                (_php_str("_rtbs_title"), _php_str("Folkrätt")),
                (
                    _php_str("_rtbs_content"),
                    _php_str(f'<p><a href="{folkratt_pdf}">Inledning till Folkrätt 29.2.2024</a></p>'),
                ),
            ]
        )
        statskunskap_tab = _php_assoc(
            [
                (_php_str("_rtbs_title"), _php_str("Statskunskap")),
                (
                    _php_str("_rtbs_content"),
                    _php_str(f'<p><a href="{statskunskap_pdf}">Val och valmetoder 14.10.2022</a></p>'),
                ),
            ]
        )
        payload = _php_assoc(
            [
                (_php_int_key(0), folkratt_tab),
                (_php_int_key(1), statskunskap_tab),
            ]
        )

        rtbs_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"
    xmlns:content="http://purl.org/rss/1.0/modules/content/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
    xmlns:wp="http://wordpress.org/export/1.2/">
  <channel>
    <item>
      <title><![CDATA[Tentarkiv]]></title>
      <link>https://sfklubben.fi/rtbs_tabs/tentarkiv/</link>
      <pubDate>Mon, 15 Apr 2024 10:00:00 +0000</pubDate>
      <dc:creator><![CDATA[admin]]></dc:creator>
      <content:encoded><![CDATA[]]></content:encoded>
      <excerpt:encoded><![CDATA[]]></excerpt:encoded>
      <wp:post_id>30</wp:post_id>
      <wp:post_date>2024-04-15 10:00:00</wp:post_date>
      <wp:post_name><![CDATA[tentarkiv]]></wp:post_name>
      <wp:status><![CDATA[publish]]></wp:status>
      <wp:post_type><![CDATA[rtbs_tabs]]></wp:post_type>
      <wp:postmeta>
        <wp:meta_key><![CDATA[_rtbs_tabs_head]]></wp:meta_key>
        <wp:meta_value><![CDATA[{payload}]]></wp:meta_value>
      </wp:postmeta>
    </item>
  </channel>
</rss>
"""

        with TemporaryDirectory() as work_dir, override_settings(MEDIA_ROOT=str(Path(work_dir) / "media")):
            work_path = Path(work_dir)
            xml_path = work_path / "export.xml"
            xml_path.write_text(rtbs_xml, encoding="utf-8")
            media_dir = work_path / "downloads" / "sfklubben.fi"
            (media_dir / "wp-content" / "uploads" / "2024" / "04").mkdir(parents=True)
            (media_dir / "wp-content" / "uploads" / "2023" / "01").mkdir(parents=True)
            folkratt_path = (
                media_dir / "wp-content" / "uploads" / "2024" / "04" / "Inledning-till-folkratt-29.2.2024-2.pdf"
            )
            statskunskap_path = (
                media_dir / "wp-content" / "uploads" / "2023" / "01" / "Val-och-valmetoder-14.10.2022.pdf"
            )
            folkratt_path.write_bytes(b"%PDF-1.4 folkratt")
            statskunskap_path.write_bytes(b"%PDF-1.4 statskunskap")

            self.call_import_command(
                str(xml_path),
                "--media-dir",
                str(media_dir),
                "--media-prefix",
                "wordpress/test",
                "--skip-publications",
                "--import-exam-archive",
            )

            folkratt = ExamArchive.objects.get(title="Folkrätt")
            statskunskap = ExamArchive.objects.get(title="Statskunskap")

            folkratt_doc = ExamFile.objects.get(archive=folkratt)
            self.assertEqual(folkratt_doc.title, "Inledning till Folkrätt 29.2.2024")
            self.assertEqual(
                folkratt_doc.document.name,
                "wordpress/test/wp-content/uploads/2024/04/inledning-till-folkratt-2922024-2.pdf",
            )

            statskunskap_doc = ExamFile.objects.get(archive=statskunskap)
            self.assertEqual(statskunskap_doc.title, "Val och valmetoder 14.10.2022")
            self.assertEqual(
                statskunskap_doc.document.name,
                "wordpress/test/wp-content/uploads/2023/01/val-och-valmetoder-14102022.pdf",
            )

    def test_dry_run_does_not_write_rows(self):
        with TemporaryDirectory() as work_dir:
            xml_path = Path(work_dir) / "export.xml"
            xml_path.write_text(WORDPRESS_EXPORT, encoding="utf-8")

            self.call_import_command(
                str(xml_path),
                "--dry-run",
                "--skip-media",
                "--skip-publications",
            )

            self.assertFalse(Post.objects.filter(slug="imported-news").exists())
            self.assertFalse(StaticPage.objects.filter(slug="imported-page").exists())
