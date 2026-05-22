from __future__ import annotations

import json
import mimetypes
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import defusedxml.ElementTree as ET
import requests
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage, storages
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from date.functions import slugify_max
from exambank.models import ExamArchive, ExamFile
from functionaries.models import Functionary, FunctionaryRole
from gallery.models import Album
from members.models import FRESHMAN, Member, MembershipType
from news.models import Category, Post
from publications.models import PDFFile, PublicationCollection
from staticpages.models import POST_SLUG_MAX_LENGTH as STATICPAGE_SLUG_MAX_LENGTH
from staticpages.models import StaticPage, StaticPageNav, StaticUrl

WXR_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}

URL_RE = re.compile(r"https?://[^\s<\]\"')]+")
RELATIVE_UPLOAD_RE = re.compile(r"/wp-content/uploads/[^\s<\]\"')]+")
UNWANTED_BLOCK_RE = re.compile(
    r"<(script|style|iframe|object|embed)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
UNWANTED_SINGLE_RE = re.compile(r"<(link|meta)\b[^>]*>", re.IGNORECASE)
WP_SHORTCODE_RE = re.compile(r"\[(/?)(caption|gallery|embed|video|audio)[^\]]*\]", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
BLOCK_TAG_RE = re.compile(
    r"^</?(address|article|aside|blockquote|div|dl|fieldset|figcaption|figure|"
    r"form|h[1-6]|hr|li|main|nav|ol|p|pre|section|table|ul)\b",
    re.IGNORECASE,
)
MEDIA_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".svg",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
IGNORED_CATEGORY_SLUGS = {"nyheter", "uncategorized"}
ISSUU_HOSTS = {"issuu.com", "www.issuu.com"}
AO_PUBLICATION_SOURCE_SLUGS = {"ao"}
AO_COLLECTION_COVER_URL = "http://sfklubben.fi/wp-content/uploads/2022/04/aologo.png"
POLITICUS_PUBLICATION_SOURCE_SLUGS = {"politicus"}
POLITICUS_COLLECTION_COVER_URL = "http://sfklubben.fi/wp-content/uploads/2022/04/politicuslogo.png"
GALLERY_LINK_HOSTS = {
    "photos.app.goo.gl",
    "photos.google.com",
    "drive.google.com",
}
GALLERY_SOURCE_SLUGS = {"bildgalleriet", "gamla-bilder"}
EXAM_ARCHIVE_POST_TYPE = "rtbs_tabs"
EXAM_ARCHIVE_SLUGS = {"tentarkiv"}
FUNCTIONARIES_SOURCE_SLUGS = {"funktionarer"}
GALLERY_THUMBNAIL_USER_AGENT = "Mozilla/5.0 (compatible; date-website-wp-import/1.0; +https://datateknologerna.fi)"
GALLERY_THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
OG_IMAGE_RE = re.compile(
    r'<meta\b[^>]*?(?:'
    r'property=["\']og:image["\'][^>]*?content=["\']([^"\']+)["\']'
    r'|'
    r'content=["\']([^"\']+)["\'][^>]*?property=["\']og:image["\']'
    r')[^>]*?>',
    re.IGNORECASE,
)


def php_unserialize(data: bytes, pos: int = 0):
    """Minimal PHP-serialize decoder for arrays of strings/ints used by rtbs_tabs."""
    code = data[pos : pos + 2]
    if code == b"s:":
        colon = data.index(b":", pos + 2)
        length = int(data[pos + 2 : colon])
        start = colon + 2
        end = start + length
        return data[start:end].decode("utf-8"), end + 2
    if code == b"i:":
        end = data.index(b";", pos + 2)
        return int(data[pos + 2 : end]), end + 1
    if code == b"a:":
        colon = data.index(b":", pos + 2)
        count = int(data[pos + 2 : colon])
        cur = colon + 2
        result: dict = {}
        for _ in range(count):
            key, cur = php_unserialize(data, cur)
            value, cur = php_unserialize(data, cur)
            if not isinstance(key, (str, int)):
                raise ValueError(f"Unsupported PHP array key type {type(key).__name__} at offset {pos}")
            result[key] = value
        return result, cur + 1
    raise ValueError(f"Unsupported PHP serialize token at offset {pos}")


@dataclass
class ImportStats:
    media_saved: int = 0
    media_existing: int = 0
    media_missing: int = 0
    posts_created: int = 0
    posts_updated: int = 0
    pages_created: int = 0
    pages_updated: int = 0
    publications_created: int = 0
    publications_updated: int = 0
    categories_created: int = 0
    nav_categories_created: int = 0
    nav_urls_created: int = 0
    gallery_redirects_created: int = 0
    gallery_redirects_updated: int = 0
    gallery_thumbnails_saved: int = 0
    gallery_thumbnails_missing: int = 0
    exam_collections_created: int = 0
    exam_collections_updated: int = 0
    exam_documents_created: int = 0
    exam_documents_updated: int = 0
    exam_documents_missing: int = 0
    functionary_roles_created: int = 0
    functionaries_created: int = 0
    functionaries_updated: int = 0
    skipped_items: Counter = field(default_factory=Counter)
    missing_media_urls: list[str] = field(default_factory=list)
    missing_exam_hrefs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WpItem:
    post_id: str
    post_type: str
    title: str
    slug: str
    status: str
    creator: str
    post_date: datetime
    modified_date: datetime | None
    content: str
    excerpt: str
    link: str
    attachment_url: str
    categories: tuple[tuple[str, str], ...]
    nav_menus: tuple[tuple[str, str], ...]
    menu_order: int
    meta: dict[str, str]


class Command(BaseCommand):
    help = (
        "One-off SF migration helper: import the SF WordPress WXR export into "
        "Django content apps and copy referenced sfklubben.fi uploads through "
        "Django storage."
    )

    def add_arguments(self, parser):
        parser.add_argument("xml_path", help="Path to the WordPress WXR XML export.")
        parser.add_argument(
            "--media-dir",
            help=(
                "Directory containing downloaded WordPress uploads. Defaults to "
                "<xml parent>/sfklubben-export-local/assets/sfklubben.fi."
            ),
        )
        parser.add_argument(
            "--media-prefix",
            default="wordpress/sfklubben",
            help="Storage prefix for imported media. Default: wordpress/sfklubben",
        )
        parser.add_argument(
            "--author",
            default="wp-import",
            help="Member username to use as imported news author. Created if missing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report planned changes without writing files or database rows.",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing rows with matching slugs. Without this, matching rows are skipped.",
        )
        parser.add_argument(
            "--keep-wordpress-categories",
            action="store_true",
            help=(
                "Create SF WordPress categories as news categories. By default generic "
                "'Nyheter' and 'Uncategorized' are imported as normal uncategorized news."
            ),
        )
        parser.add_argument(
            "--skip-media",
            action="store_true",
            help="Do not copy media files. Content URLs are left as they are.",
        )
        parser.add_argument(
            "--download-missing-media",
            action="store_true",
            help="Fetch missing sfklubben.fi upload files over HTTP when they are not in --media-dir.",
        )
        parser.add_argument(
            "--skip-publications",
            action="store_true",
            help="Do not create publication records from SF A&O and Politicus pages.",
        )
        parser.add_argument(
            "--import-nav",
            action="store_true",
            help="Import SF WordPress nav_menu_item records into StaticPageNav/StaticUrl.",
        )
        parser.add_argument(
            "--nav-menu",
            default="actual",
            help="WordPress nav menu slug to import when --import-nav is used. Default: actual",
        )
        parser.add_argument(
            "--replace-nav",
            action="store_true",
            help="Delete existing StaticPageNav/StaticUrl rows before importing navigation.",
        )
        parser.add_argument(
            "--import-gallery-redirects",
            action="store_true",
            help="Import SF Google Photos/Drive gallery links as redirecting picture albums.",
        )
        parser.add_argument(
            "--replace-gallery-redirects",
            action="store_true",
            help="Delete existing redirect-only picture albums before importing gallery redirects.",
        )
        parser.add_argument(
            "--skip-gallery-thumbnails",
            action="store_true",
            help=(
                "Skip fetching og:image previews from Google Photos/Drive share URLs when "
                "creating gallery redirect albums. Use for offline imports and tests."
            ),
        )
        parser.add_argument(
            "--import-exam-archive",
            action="store_true",
            help=(
                "Import the WordPress 'tentarkiv' rtbs_tabs payload as exam archives with one exam file per linked PDF."
            ),
        )
        parser.add_argument(
            "--replace-exam-archive",
            action="store_true",
            help="Delete existing exam archives (and their files) before importing.",
        )
        parser.add_argument(
            "--import-functionaries",
            action="store_true",
            help=("Import the SF WordPress 'funktionarer' page into FunctionaryRole and name-only Functionary rows."),
        )
        parser.add_argument(
            "--replace-functionaries",
            action="store_true",
            help="Delete existing functionaries before importing from WordPress.",
        )
        parser.add_argument(
            "--report",
            help="Optional JSON report path. Defaults to <xml parent>/wordpress-import-report.json.",
        )

    def handle(self, *args, **options):
        xml_path = Path(options["xml_path"]).expanduser().resolve()
        if not xml_path.exists():
            raise CommandError(f"XML export does not exist: {xml_path}")

        media_dir = (
            Path(options["media_dir"] or xml_path.parent / "sfklubben-export-local" / "assets" / "sfklubben.fi")
            .expanduser()
            .resolve()
        )
        if not options["skip_media"] and not options["download_missing_media"] and not media_dir.exists():
            raise CommandError(
                f"Media directory does not exist: {media_dir}. "
                "Run with --skip-media, pass --media-dir, or use --download-missing-media."
            )

        report_path = Path(options["report"] or xml_path.parent / "wordpress-import-report.json").expanduser().resolve()

        xml_bytes = xml_path.read_bytes()
        xml_text = xml_bytes.decode("utf-8", errors="replace")
        items = self.parse_items(xml_path)
        upload_urls = self.collect_upload_urls(xml_text)
        storage = self.public_media_storage()
        stats = ImportStats()
        url_map: dict[str, str] = {}
        storage_name_map: dict[str, str] = {}

        self.stdout.write(f"Parsed {len(items)} WordPress items and {len(upload_urls)} sfklubben.fi upload URLs.")

        if not options["skip_media"]:
            url_map = self.import_media(
                upload_urls,
                media_dir,
                storage,
                options["media_prefix"].strip("/"),
                options["dry_run"],
                options["download_missing_media"],
                stats,
                storage_name_map,
            )

        author = None
        if not options["dry_run"]:
            author = self.get_or_create_author(options["author"])

        with transaction.atomic():
            for item in items:
                if item.post_type == "post":
                    self.import_post(item, author, url_map, options, stats)
                elif item.post_type == "page":
                    self.import_page(item, url_map, options, stats)
                elif item.post_type == "nav_menu_item" and options["import_nav"]:
                    continue
                else:
                    stats.skipped_items[item.post_type] += 1

            if not options["skip_publications"]:
                self.import_publications(items, storage_name_map, options, stats)
            if options["import_nav"]:
                self.import_navigation(items, url_map, options, stats)
            if options["import_gallery_redirects"]:
                self.import_gallery_redirects(items, url_map, options, stats)
            if options["import_exam_archive"]:
                self.import_exam_archive(items, storage, storage_name_map, xml_bytes, options, stats)
            if options["import_functionaries"]:
                self.import_functionaries(items, options, stats)

            if options["dry_run"]:
                transaction.set_rollback(True)

        report = {
            "xml_path": str(xml_path),
            "media_dir": str(media_dir),
            "storage": storage.__class__.__name__,
            "dry_run": options["dry_run"],
            "stats": {
                "media_saved": stats.media_saved,
                "media_existing": stats.media_existing,
                "media_missing": stats.media_missing,
                "posts_created": stats.posts_created,
                "posts_updated": stats.posts_updated,
                "pages_created": stats.pages_created,
                "pages_updated": stats.pages_updated,
                "publications_created": stats.publications_created,
                "publications_updated": stats.publications_updated,
                "categories_created": stats.categories_created,
                "nav_categories_created": stats.nav_categories_created,
                "nav_urls_created": stats.nav_urls_created,
                "gallery_redirects_created": stats.gallery_redirects_created,
                "gallery_redirects_updated": stats.gallery_redirects_updated,
                "gallery_thumbnails_saved": stats.gallery_thumbnails_saved,
                "gallery_thumbnails_missing": stats.gallery_thumbnails_missing,
                "exam_collections_created": stats.exam_collections_created,
                "exam_collections_updated": stats.exam_collections_updated,
                "exam_documents_created": stats.exam_documents_created,
                "exam_documents_updated": stats.exam_documents_updated,
                "exam_documents_missing": stats.exam_documents_missing,
                "functionary_roles_created": stats.functionary_roles_created,
                "functionaries_created": stats.functionaries_created,
                "functionaries_updated": stats.functionaries_updated,
                "skipped_items": dict(stats.skipped_items),
            },
            "missing_media_urls": stats.missing_media_urls,
            "missing_exam_hrefs": stats.missing_exam_hrefs,
        }
        if not options["dry_run"]:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"Wrote import report to {report_path}")

        self.print_summary(stats, dry_run=options["dry_run"])

    def parse_items(self, xml_path: Path) -> list[WpItem]:
        root = ET.parse(xml_path).getroot()
        parsed_items = []
        for element in root.findall("./channel/item"):
            post_id = self.child_text(element, "wp:post_id")
            post_type = self.child_text(element, "wp:post_type") or "unknown"
            post_date = self.parse_wp_datetime(
                self.child_text(element, "wp:post_date") or self.child_text(element, "pubDate")
            )
            modified_date = self.parse_wp_datetime(self.child_text(element, "wp:post_modified"))
            categories = []
            nav_menus = []
            for category in element.findall("category"):
                if category.attrib.get("domain") == "category":
                    categories.append((category.attrib.get("nicename", ""), category.text or ""))
                elif category.attrib.get("domain") == "nav_menu":
                    nav_menus.append((category.attrib.get("nicename", ""), category.text or ""))
            meta = {}
            for post_meta in element.findall("wp:postmeta", WXR_NS):
                key = self.child_text(post_meta, "wp:meta_key")
                if key:
                    meta[key] = self.child_text(post_meta, "wp:meta_value")
            parsed_items.append(
                WpItem(
                    post_id=post_id,
                    post_type=post_type,
                    title=self.child_text(element, "title") or "(untitled)",
                    slug=self.child_text(element, "wp:post_name"),
                    status=self.child_text(element, "wp:status"),
                    creator=self.child_text(element, "dc:creator"),
                    post_date=post_date,
                    modified_date=modified_date,
                    content=self.child_text(element, "content:encoded"),
                    excerpt=self.child_text(element, "excerpt:encoded"),
                    link=self.child_text(element, "link"),
                    attachment_url=self.child_text(element, "wp:attachment_url"),
                    categories=tuple(categories),
                    nav_menus=tuple(nav_menus),
                    menu_order=int(self.child_text(element, "wp:menu_order") or 0),
                    meta=meta,
                )
            )
        return parsed_items

    def collect_upload_urls(self, xml_text: str) -> list[str]:
        urls = set()
        for url in URL_RE.findall(xml_text):
            clean_url = url.rstrip(".,;")
            parsed = urlparse(clean_url)
            if (
                parsed.netloc.lower() == "sfklubben.fi"
                and "/wp-content/uploads/" in parsed.path
                and Path(unquote(parsed.path)).suffix.lower() in MEDIA_EXTENSIONS
            ):
                urls.add(clean_url)
        for url in RELATIVE_UPLOAD_RE.findall(xml_text):
            clean_url = url.rstrip(".,;")
            if Path(unquote(urlparse(clean_url).path)).suffix.lower() in MEDIA_EXTENSIONS:
                urls.add(f"http://sfklubben.fi{clean_url}")
        return sorted(urls)

    def import_media(
        self,
        urls: list[str],
        media_dir: Path,
        storage,
        media_prefix: str,
        dry_run: bool,
        download_missing_media: bool,
        stats: ImportStats,
        storage_name_map: dict[str, str],
    ) -> dict[str, str]:
        url_map = {}
        for url in urls:
            source = self.local_source_path(media_dir, url)
            storage_name = self.storage_name_for_url(media_prefix, url)
            if storage.exists(storage_name):
                stats.media_existing += 1
                url_map[url] = storage.url(storage_name)
                storage_name_map[url] = storage_name
                continue

            downloaded_content = None
            if not source.exists() and download_missing_media:
                downloaded_content = self.download_media_content(url)
            if not source.exists() and downloaded_content is None:
                stats.media_missing += 1
                stats.missing_media_urls.append(url)
                continue

            if dry_run:
                stats.media_saved += 1
                url_map[url] = f"DRY-RUN:{storage_name}"
                storage_name_map[url] = storage_name
                continue

            if downloaded_content is not None:
                saved_name = storage.save(
                    storage_name,
                    ContentFile(downloaded_content, name=Path(storage_name).name),
                )
            else:
                with source.open("rb") as source_file:
                    saved_name = storage.save(storage_name, File(source_file, name=source.name))
            storage_name = saved_name
            stats.media_saved += 1
            url_map[url] = storage.url(storage_name)
            storage_name_map[url] = storage_name
        return url_map

    def download_media_content(self, url: str) -> bytes | None:
        for candidate in self.media_download_candidates(url):
            try:
                response = requests.get(candidate, timeout=8, allow_redirects=True)
                response.raise_for_status()
            except requests.RequestException:
                continue
            return response.content
        return None

    def media_download_candidates(self, url: str) -> list[str]:
        candidates = [url]
        if url.startswith("http://"):
            candidates.append("https://" + url[len("http://") :])
        elif url.startswith("https://"):
            candidates.append("http://" + url[len("https://") :])
        return candidates

    def import_post(self, item: WpItem, author: Member | None, url_map: dict[str, str], options, stats: ImportStats):
        slug = self.unique_slug(item.slug or item.title, Post, max_length=Post._meta.get_field("slug").max_length)  # type: ignore[arg-type]
        existing = Post.objects.filter(slug=slug).first()
        if existing and not options["update_existing"]:
            return

        category = self.category_for_item(item, options["keep_wordpress_categories"], options["dry_run"], stats)
        content = self.prepare_content(item.content, url_map)
        fields = {
            "title": item.title[:255],
            "content": content,
            "author": author,
            "created_time": item.post_date,
            "published_time": item.post_date if item.status == "publish" else None,
            "modified_time": item.modified_date,
            "category": category,
        }
        if options["dry_run"]:
            stats.posts_updated += int(existing is not None)
            stats.posts_created += int(existing is None)
            return
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.posts_updated += 1
        else:
            Post.objects.create(slug=slug, **fields)
            stats.posts_created += 1

    def import_page(self, item: WpItem, url_map: dict[str, str], options, stats: ImportStats):
        slug = self.unique_slug(
            item.slug or item.title,
            StaticPage,
            max_length=STATICPAGE_SLUG_MAX_LENGTH,
        )
        existing = StaticPage.objects.filter(slug=slug).first()
        if existing and not options["update_existing"]:
            return

        fields = {
            "title": item.title[:255],
            "content": self.prepare_content(item.content, url_map),
            "created_time": item.post_date,
            "modified_time": item.modified_date,
            "members_only": item.status == "private",
        }
        if options["dry_run"]:
            stats.pages_updated += int(existing is not None)
            stats.pages_created += int(existing is None)
            return
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.pages_updated += 1
        else:
            StaticPage.objects.create(slug=slug, **fields)
            stats.pages_created += 1

    def import_publications(
        self,
        items: list[WpItem],
        storage_name_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        ao_collection = self.import_publication_collection(
            "ao",
            "A&O",
            "Allwar och Oförskämt",
            AO_COLLECTION_COVER_URL,
            storage_name_map,
            options,
        )
        for link in self.ao_publication_links(items):
            self.import_publication_link(link, ao_collection, storage_name_map, options, stats)

        politicus_collection = self.import_publication_collection(
            "politicus",
            "Politicus",
            "",
            POLITICUS_COLLECTION_COVER_URL,
            storage_name_map,
            options,
        )
        for link in self.politicus_publication_links(items):
            self.import_publication_link(link, politicus_collection, storage_name_map, options, stats)

    def import_publication_collection(
        self,
        slug: str,
        title: str,
        description: str,
        cover_url: str,
        storage_name_map: dict[str, str],
        options,
    ):
        if options["dry_run"]:
            return None

        cover_image = self.storage_name_for_upload_url(cover_url, storage_name_map)
        collection, _ = PublicationCollection.objects.get_or_create(
            slug=slug,
            defaults={
                "title": title,
                "description": description,
                "cover_image": cover_image,
                "visibility": PublicationCollection.VISIBILITY_PUBLIC,
                "ordering": 0,
                "is_active": True,
            },
        )
        if cover_image and (options["update_existing"] or not collection.cover_image):
            collection.cover_image = cover_image
            collection.save(update_fields=["cover_image", "updated_at"])
        return collection

    def import_publication_link(
        self,
        link: dict,
        collection: PublicationCollection | None,
        storage_name_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        if not link.get("url") and not link.get("file_url"):
            return

        slug = self.unique_slug(
            link["title"],
            PDFFile,
            max_length=PDFFile._meta.get_field("slug").max_length,  # type: ignore[arg-type]
        )
        existing = PDFFile.objects.filter(slug=slug).first()
        if existing and not options["update_existing"]:
            return

        if options["dry_run"]:
            stats.publications_updated += int(existing is not None)
            stats.publications_created += int(existing is None)
            return

        fields = {
            "collection": collection,
            "title": link["title"][:250],
            "description": link["description"],
            "publication_date": link["publication_date"],
            "is_public": True,
            "requires_login": False,
            "file": self.storage_name_for_upload_url(link.get("file_url", ""), storage_name_map),
            "redirect_url": link.get("url", ""),
            "cover_image": self.storage_name_for_upload_url(
                link["cover_image_url"],
                storage_name_map,
            ),
        }
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.publications_updated += 1
        else:
            PDFFile.objects.create(slug=slug, **fields)
            stats.publications_created += 1

    def ao_publication_links(self, items: list[WpItem]) -> list[dict]:
        links = []
        seen_urls = set()
        for item in items:
            if item.post_type != "page" or item.slug not in AO_PUBLICATION_SOURCE_SLUGS:
                continue
            for publication in AOPublicationPageParser.parse(item.content):
                url = publication["url"]
                if not self.is_issuu_url(url):
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                links.append(
                    {
                        "title": publication["title"],
                        "url": url,
                        "description": self.plain_text(item.excerpt),
                        "publication_date": publication["publication_date"] or item.post_date.date(),
                        "cover_image_url": publication["cover_image_url"],
                    }
                )
        return links

    def politicus_publication_links(self, items: list[WpItem]) -> list[dict]:
        links = []
        seen_targets = set()
        items_by_slug = {item.slug: item for item in items if item.slug and item.post_type == "page"}
        for item in items:
            if item.post_type != "page" or item.slug not in POLITICUS_PUBLICATION_SOURCE_SLUGS:
                continue
            for publication in PoliticusPublicationPageParser.parse(item.content):
                link_url = urljoin("https://sfklubben.fi/", publication["url"])
                target_url = link_url
                file_url = ""
                if not self.is_issuu_url(link_url):
                    target_item = items_by_slug.get(self.slug_from_url(link_url))
                    file_url = self.first_pdf_link(target_item.content) if target_item else ""
                    if not file_url:
                        continue
                    target_url = file_url
                    link_url = ""
                if target_url in seen_targets:
                    continue
                seen_targets.add(target_url)
                links.append(
                    {
                        "title": publication["title"],
                        "url": link_url,
                        "file_url": file_url,
                        "description": self.plain_text(item.excerpt),
                        "publication_date": publication["publication_date"] or item.post_date.date(),
                        "cover_image_url": publication["cover_image_url"],
                    }
                )
        return links

    def slug_from_url(self, url: str) -> str:
        path = urlparse(url).path.strip("/")
        return path.split("/")[-1] if path else ""

    def first_pdf_link(self, html: str) -> str:
        parser = AnchorExtractor()
        parser.feed(html or "")
        for anchor in parser.anchors:
            href = anchor["href"].strip()
            if urlparse(href).path.lower().endswith(".pdf"):
                return urljoin("https://sfklubben.fi/", href)
        return ""

    def is_issuu_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in ISSUU_HOSTS

    def storage_name_for_upload_url(self, url: str, storage_name_map: dict[str, str]) -> str:
        if not url:
            return ""
        candidates = [url]
        if url.startswith("/wp-content/uploads/"):
            candidates.append(f"http://sfklubben.fi{url}")
            candidates.append(f"https://sfklubben.fi{url}")
        elif url.startswith("http://"):
            candidates.append("https://" + url[len("http://") :])
        elif url.startswith("https://"):
            candidates.append("http://" + url[len("https://") :])
        for candidate in candidates:
            storage_name = storage_name_map.get(candidate)
            if storage_name:
                return storage_name
        return ""

    def import_navigation(
        self,
        items: list[WpItem],
        url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        menu_slug = options["nav_menu"]
        nav_items = [
            item
            for item in items
            if item.post_type == "nav_menu_item" and any(slug == menu_slug for slug, _name in item.nav_menus)
        ]
        if not nav_items:
            self.stdout.write(self.style.WARNING(f"No WordPress nav items found for menu '{menu_slug}'."))
            return

        if options["dry_run"]:
            stats.nav_categories_created += len([item for item in nav_items if self.nav_parent_id(item) == "0"])
            stats.nav_urls_created += len(nav_items)
            return

        if options["replace_nav"]:
            StaticUrl.objects.all().delete()
            StaticPageNav.objects.all().delete()

        item_by_id = {item.post_id: item for item in nav_items}
        object_by_id = {item.post_id: item for item in items if item.post_type in {"page", "post"}}
        children_by_parent: dict[str, list[WpItem]] = {}
        for item in nav_items:
            children_by_parent.setdefault(self.nav_parent_id(item), []).append(item)
        for children in children_by_parent.values():
            children.sort(key=lambda item: item.menu_order)

        top_level_items = sorted(children_by_parent.get("0", []), key=lambda item: item.menu_order)
        for index, top_item in enumerate(top_level_items, start=1):
            title = self.nav_title(top_item, object_by_id)
            if not title:
                continue
            descendants = self.nav_descendants(top_item, children_by_parent)
            top_url = self.nav_url(top_item, object_by_id, url_map)
            has_children = bool(descendants)
            category, created = StaticPageNav.objects.update_or_create(
                category_name=title[:255],
                defaults={
                    "nav_element": index * 10,
                    "use_category_url": not has_children,
                    "url": top_url if not has_children else "",
                },
            )
            stats.nav_categories_created += int(created)

            if has_children:
                top_level_dropdown_items = [top_item]
                top_level_dropdown_items.extend(children_by_parent.get(top_item.post_id, []))
                imported_parent_links = {}
                for dropdown_index, dropdown_item in enumerate(top_level_dropdown_items, start=1):
                    dropdown_title = self.nav_title(dropdown_item, object_by_id)
                    dropdown_url = self.nav_url(dropdown_item, object_by_id, url_map)
                    has_submenu_children = bool(children_by_parent.get(dropdown_item.post_id))
                    if not dropdown_title or (not dropdown_url and not has_submenu_children):
                        continue
                    dropdown_url_obj, created = StaticUrl.objects.update_or_create(
                        category=category,
                        title=dropdown_title[:255],
                        parent=None,
                        defaults={
                            "url": dropdown_url[:200],
                            "dropdown_element": dropdown_index * 10,
                            "logged_in_only": False,
                        },
                    )
                    stats.nav_urls_created += int(created)
                    imported_parent_links[dropdown_item.post_id] = dropdown_url_obj

                for parent_item in children_by_parent.get(top_item.post_id, []):
                    parent_url = imported_parent_links.get(parent_item.post_id)
                    if parent_url is None:
                        continue
                    for child_index, child_item in enumerate(
                        self.nav_descendants(parent_item, children_by_parent),
                        start=1,
                    ):
                        if self.nav_parent_id(child_item) == parent_item.post_id:
                            child_title = self.nav_title(child_item, object_by_id)
                        else:
                            child_title = self.nav_dropdown_title(child_item, item_by_id, object_by_id)
                        child_url = self.nav_url(child_item, object_by_id, url_map)
                        if not child_title or not child_url:
                            continue
                        _child_url_obj, created = StaticUrl.objects.update_or_create(
                            parent=parent_url,
                            title=child_title[:255],
                            defaults={
                                "url": child_url[:200],
                                "dropdown_element": child_index * 10,
                                "logged_in_only": False,
                            },
                        )
                        stats.nav_urls_created += int(created)

    def import_gallery_redirects(
        self,
        items: list[WpItem],
        url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        links = self.gallery_redirect_links(items, url_map)
        if options["dry_run"]:
            stats.gallery_redirects_created += len(links)
            return

        if options["replace_gallery_redirects"]:
            Album.objects.filter(redirect_url__gt="").delete()

        for link in links:
            album = Album.objects.filter(title=link["title"]).first()
            fields = {
                "pub_date": link["pub_date"],
                "redirect_url": link["url"],
                "hide_for_gulis": False,
            }
            if album:
                for key, value in fields.items():
                    setattr(album, key, value)
                album.save()
                stats.gallery_redirects_updated += 1
            else:
                album = Album.objects.create(
                    title=link["title"][:250],
                    **fields,
                )
                stats.gallery_redirects_created += 1

            if not options["skip_gallery_thumbnails"] and not album.thumbnail:
                self.apply_gallery_thumbnail(album, link, stats)

    def gallery_redirect_links(self, items: list[WpItem], url_map: dict[str, str]) -> list[dict]:
        links = []
        seen = set()
        for item in items:
            if item.post_type != "page" or item.slug not in GALLERY_SOURCE_SLUGS:
                continue
            parser = AnchorExtractor()
            parser.feed(item.content or "")
            for anchor in parser.anchors:
                url = self.normalize_gallery_redirect_url(anchor["href"], url_map)
                if not url:
                    continue
                title = re.sub(r"\s+", " ", anchor["text"]).strip()
                if not title:
                    title = url
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                links.append(
                    {
                        "title": title,
                        "url": url,
                        "pub_date": self.gallery_pub_date(title, item.post_date),
                    }
                )
        return links

    def import_functionaries(self, items: list[WpItem], options, stats: ImportStats) -> None:
        page = next(
            (item for item in items if item.post_type == "page" and item.slug in FUNCTIONARIES_SOURCE_SLUGS),
            None,
        )
        if page is None:
            self.stdout.write(self.style.WARNING("No 'funktionarer' page found; skipping functionary import."))
            return

        rows = FunctionaryPageParser.parse(page.content)
        if not rows:
            self.stdout.write(self.style.WARNING("No functionary rows found on the 'funktionarer' page."))
            return

        if options["replace_functionaries"] and not options["dry_run"]:
            Functionary.objects.all().delete()

        role_cache = {
            role.title: role for role in FunctionaryRole.objects.filter(title__in={row["role"] for row in rows})
        }
        dry_run_created_roles = set()
        for row in rows:
            role = role_cache.get(row["role"])
            if role is None:
                if options["dry_run"]:
                    if row["role"] not in dry_run_created_roles:
                        dry_run_created_roles.add(row["role"])
                        stats.functionary_roles_created += 1
                    role = None
                else:
                    role = FunctionaryRole.objects.create(title=row["role"][:200], board=True)
                    role_cache[row["role"]] = role
                    stats.functionary_roles_created += 1
            elif not options["dry_run"] and not role.board:
                role.board = True
                role.save(update_fields=["board"])

            if options["dry_run"]:
                existing = (
                    Functionary.objects.filter(
                        functionary_role__title=row["role"],
                        year=row["year"],
                        name=row["name"],
                    ).exists()
                    if role is not None
                    else False
                )
                stats.functionaries_updated += int(existing)
                stats.functionaries_created += int(not existing)
                continue

            _functionary, created = Functionary.objects.get_or_create(
                functionary_role=role,
                year=row["year"],
                name=row["name"][:200],
            )
            stats.functionaries_created += int(created)
            stats.functionaries_updated += int(not created)

    def import_exam_archive(
        self,
        items: list[WpItem],
        storage,
        storage_name_map: dict[str, str],
        xml_bytes: bytes,
        options,
        stats: ImportStats,
    ) -> None:
        rtbs_item = next(
            (item for item in items if item.post_type == EXAM_ARCHIVE_POST_TYPE and item.slug in EXAM_ARCHIVE_SLUGS),
            None,
        )
        if rtbs_item is None:
            self.stdout.write(self.style.WARNING("No 'tentarkiv' rtbs_tabs item found; skipping exam archive import."))
            return

        # ElementTree normalizes CRLF to LF, which corrupts PHP byte counts in
        # multi-line string values. Extract the raw payload from the source
        # bytes when possible so the byte counts line up.
        serialized_bytes = self.extract_rtbs_payload_bytes(xml_bytes)
        if serialized_bytes is None:
            serialized_text = rtbs_item.meta.get("_rtbs_tabs_head") or ""
            if not serialized_text:
                self.stdout.write(self.style.WARNING("'tentarkiv' rtbs_tabs item has no _rtbs_tabs_head meta."))
                return
            serialized_bytes = serialized_text.encode("utf-8")

        try:
            tabs, _ = php_unserialize(serialized_bytes)
        except (ValueError, IndexError, UnicodeDecodeError) as exc:
            self.stdout.write(self.style.WARNING(f"Failed to parse rtbs_tabs payload: {exc}"))
            return
        if not isinstance(tabs, dict):
            self.stdout.write(self.style.WARNING("rtbs_tabs payload is not an array."))
            return

        if options["replace_exam_archive"] and not options["dry_run"]:
            existing = ExamArchive.objects.all()
            ExamFile.objects.filter(archive__in=existing).delete()
            existing.delete()

        for _, tab in tabs.items():
            if not isinstance(tab, dict):
                continue
            title = (tab.get("_rtbs_title") or "").strip()
            content = tab.get("_rtbs_content") or ""
            if not title:
                continue

            archive = self.get_or_create_exam_collection(title, rtbs_item.post_date, options, stats)
            anchors = self.exam_anchors_in_content(content)
            for anchor in anchors:
                self.import_exam_document(
                    archive,
                    anchor,
                    storage,
                    storage_name_map,
                    options,
                    stats,
                )

    def extract_rtbs_payload_bytes(self, xml_bytes: bytes) -> bytes | None:
        match = re.search(
            rb"_rtbs_tabs_head\]\]>"
            rb".*?<wp:meta_value>\s*<!\[CDATA\[(a:\d+:\{.*?)\]\]>\s*</wp:meta_value>",
            xml_bytes,
            re.DOTALL,
        )
        return match.group(1) if match else None

    def get_or_create_exam_collection(
        self,
        title: str,
        fallback_date: datetime,
        options,
        stats: ImportStats,
    ) -> ExamArchive | None:
        existing = ExamArchive.objects.filter(title=title).first()
        if existing:
            stats.exam_collections_updated += 1
            return existing
        if options["dry_run"]:
            stats.exam_collections_created += 1
            return None
        archive = ExamArchive.objects.create(
            title=title[:250],
            pub_date=fallback_date,
        )
        stats.exam_collections_created += 1
        return archive

    def exam_anchors_in_content(self, html: str) -> list[dict]:
        parser = AnchorExtractor()
        parser.feed(html or "")
        anchors = []
        seen = set()
        for anchor in parser.anchors:
            href = (anchor.get("href") or "").strip()
            text = re.sub(r"\s+", " ", anchor.get("text") or "").strip()
            if not href or not text:
                continue
            key = (text, href)
            if key in seen:
                continue
            seen.add(key)
            anchors.append({"href": href, "text": text})
        return anchors

    def import_exam_document(
        self,
        archive: ExamArchive | None,
        anchor: dict,
        storage,
        storage_name_map: dict[str, str],
        options,
        stats: ImportStats,
    ) -> None:
        href = anchor["href"]
        title = anchor["text"]
        storage_name = self.exam_storage_name_for_href(href, storage_name_map)
        if not storage_name:
            stats.exam_documents_missing += 1
            stats.missing_exam_hrefs.append(href)
            return

        if options["dry_run"] or archive is None:
            existing = ExamFile.objects.filter(archive=archive, title=title).first() if archive is not None else None
            if existing:
                stats.exam_documents_updated += 1
            else:
                stats.exam_documents_created += 1
            return

        storage_name = self.exam_document_storage_name(storage_name, archive, title, storage)

        existing = ExamFile.objects.filter(archive=archive, title=title).first()
        if existing:
            existing.document = storage_name
            existing.save()
            stats.exam_documents_updated += 1
        else:
            ExamFile.objects.create(
                archive=archive,
                title=title[:250],
                document=storage_name,
            )
            stats.exam_documents_created += 1

    def exam_document_storage_name(
        self,
        source_name: str,
        archive: ExamArchive,
        title: str,
        storage,
    ) -> str:
        max_length = ExamFile._meta.get_field("document").max_length or 100
        if len(source_name) <= max_length:
            return source_name

        extension = Path(source_name).suffix.lower() or ".pdf"
        year = archive.pub_date.strftime("%Y") if archive.pub_date else "wordpress"
        coll_slug = slugify_max(archive.title, max_length=40) or "exams"
        title_slug = slugify_max(title, max_length=40) or "exam"
        target_name = f"Exams/{year}/{coll_slug}/{title_slug}{extension}"
        if len(target_name) > max_length:
            fixed = len(f"Exams/{year}//{extension}")
            budget = max(8, max_length - fixed)
            coll_slug = slugify_max(archive.title, max_length=max(4, budget // 3)) or "ex"
            title_slug = slugify_max(title, max_length=budget - len(coll_slug) - 1) or "f"
            target_name = f"Exams/{year}/{coll_slug}/{title_slug}{extension}"
            target_name = target_name[:max_length]

        if not storage.exists(target_name):
            with storage.open(source_name, "rb") as source_file:
                storage.save(target_name, File(source_file, name=Path(target_name).name))
        return target_name

    def exam_storage_name_for_href(
        self,
        href: str,
        storage_name_map: dict[str, str],
    ) -> str | None:
        candidates = [href]
        if href.startswith("http://"):
            candidates.append("https://" + href[len("http://") :])
        elif href.startswith("https://"):
            candidates.append("http://" + href[len("https://") :])
        elif href.startswith("/wp-content/uploads/"):
            candidates.append(f"https://sfklubben.fi{href}")
            candidates.append(f"http://sfklubben.fi{href}")
        for candidate in candidates:
            name = storage_name_map.get(candidate)
            if name:
                return name
        return None

    def normalize_gallery_redirect_url(self, url: str, url_map: dict[str, str]) -> str:
        if not url:
            return ""
        normalized = self.normalize_nav_url(url, url_map)
        parsed = urlparse(normalized)
        if parsed.netloc.lower() in GALLERY_LINK_HOSTS:
            return normalized
        return ""

    def gallery_pub_date(self, title: str, fallback: datetime) -> datetime:
        match = re.search(r"\b(19|20)\d{2}\b", title)
        if match:
            year = int(match.group(0))
            return timezone.make_aware(datetime(year, 6, 1, 12), timezone.get_current_timezone())
        return fallback

    def apply_gallery_thumbnail(self, collection: Album, link: dict, stats: ImportStats) -> None:
        result = self.fetch_gallery_og_image(link["url"])
        if result is None:
            stats.gallery_thumbnails_missing += 1
            self.stdout.write(self.style.WARNING(f"  no og:image preview for {link['url']} ({link['title']})"))
            return
        image_url, image_bytes = result
        filename = self.gallery_thumbnail_filename(link["title"], image_url)
        collection.thumbnail.save(filename, ContentFile(image_bytes), save=True)
        stats.gallery_thumbnails_saved += 1

    def fetch_gallery_og_image(self, share_url: str) -> tuple[str, bytes] | None:
        headers = {"User-Agent": GALLERY_THUMBNAIL_USER_AGENT}
        try:
            response = requests.get(share_url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException:
            return None
        match = OG_IMAGE_RE.search(response.text)
        if not match:
            return None
        image_url = match.group(1) or match.group(2)
        if not image_url:
            return None
        try:
            image_response = requests.get(image_url, headers=headers, timeout=15)
            image_response.raise_for_status()
        except requests.RequestException:
            return None
        return image_url, image_response.content

    def gallery_thumbnail_filename(self, title: str, image_url: str) -> str:
        extension = Path(unquote(urlparse(image_url).path)).suffix.lower()
        if extension not in GALLERY_THUMBNAIL_EXTENSIONS:
            extension = ".jpg"
        base = slugify_max(title, max_length=80) or "thumbnail"
        return f"{base}{extension}"

    def nav_parent_id(self, item: WpItem) -> str:
        return item.meta.get("_menu_item_menu_item_parent") or "0"

    def nav_descendants(self, item: WpItem, children_by_parent: dict[str, list[WpItem]]) -> list[WpItem]:
        descendants = []
        for child in children_by_parent.get(item.post_id, []):
            descendants.append(child)
            descendants.extend(self.nav_descendants(child, children_by_parent))
        return descendants

    def nav_dropdown_title(
        self,
        item: WpItem,
        item_by_id: dict[str, WpItem],
        object_by_id: dict[str, WpItem],
    ) -> str:
        title = self.nav_title(item, object_by_id)
        parent_id = self.nav_parent_id(item)
        parent = item_by_id.get(parent_id)
        grandparent_id = self.nav_parent_id(parent) if parent else "0"
        if parent and grandparent_id != "0":
            parent_title = self.nav_title(parent, object_by_id)
            if parent_title and not title.startswith(parent_title):
                return f"{parent_title} / {title}"
        return title

    def nav_title(self, item: WpItem, object_by_id: dict[str, WpItem]) -> str:
        title = item.title.strip()
        if title == "(untitled)" or not title or not any(character.isalnum() for character in title):
            object_item = object_by_id.get(item.meta.get("_menu_item_object_id", ""))
            title = object_item.title.strip() if object_item else ""
        return title

    def nav_url(self, item: WpItem, object_by_id: dict[str, WpItem], url_map: dict[str, str]) -> str:
        item_type = item.meta.get("_menu_item_type")
        if item_type == "post_type":
            object_item = object_by_id.get(item.meta.get("_menu_item_object_id", ""))
            if object_item and object_item.post_type == "page":
                slug = self.unique_slug(object_item.slug or object_item.title, StaticPage, STATICPAGE_SLUG_MAX_LENGTH)
                return reverse("staticpages:page", args=[slug])
            if object_item and object_item.post_type == "post":
                return f"/news/articles/{self.unique_slug(object_item.slug or object_item.title, Post, Post._meta.get_field('slug').max_length)}/"  # type: ignore[arg-type]
        return self.normalize_nav_url(item.meta.get("_menu_item_url", ""), url_map)

    def normalize_nav_url(self, url: str, url_map: dict[str, str]) -> str:
        if not url:
            return ""
        url = url.strip()
        if url in url_map:
            return url_map[url]
        if url.startswith("/wp-content/uploads/"):
            absolute_url = f"http://sfklubben.fi{url}"
            return url_map.get(absolute_url) or url_map.get(absolute_url.replace("http://", "https://", 1)) or url
        parsed = urlparse(url)
        if parsed.netloc.lower() == "sfklubben.fi":
            if "/wp-content/uploads/" in parsed.path:
                return url_map.get(url) or url_map.get(url.replace("http://", "https://", 1)) or parsed.path
            return parsed.path or "/"
        return url

    def category_for_item(
        self,
        item: WpItem,
        keep_wordpress_categories: bool,
        dry_run: bool,
        stats: ImportStats,
    ) -> Category | None:
        if not keep_wordpress_categories:
            categories = [category for category in item.categories if category[0] not in IGNORED_CATEGORY_SLUGS]
        else:
            categories = list(item.categories)
        if not categories:
            return None

        category_slug, category_name = categories[0]
        category_slug = slugify(category_slug or category_name)[:50] or "wordpress"
        category_name = category_name or category_slug
        existing = Category.objects.filter(slug=category_slug).first()
        if existing or dry_run:
            return existing

        stats.categories_created += 1
        return Category.objects.create(slug=category_slug, name=category_name[:255])

    def prepare_content(self, html: str, url_map: dict[str, str]) -> str:
        content = html or ""
        content = UNWANTED_BLOCK_RE.sub("", content)
        content = UNWANTED_SINGLE_RE.sub("", content)
        content = WP_SHORTCODE_RE.sub("", content)
        for source_url, target_url in url_map.items():
            content = content.replace(source_url, target_url)
            https_source_url = source_url.replace("http://", "https://", 1)
            content = content.replace(https_source_url, target_url)
        return self.preserve_wordpress_linebreaks(content)

    def preserve_wordpress_linebreaks(self, html: str) -> str:
        content = html.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" not in content:
            return content

        blocks = []
        for chunk in re.split(r"\n\s*\n+", content):
            chunk = chunk.strip()
            if not chunk:
                continue

            chunk = re.sub(r"\n+", "<br>", chunk)
            if self.is_standalone_media_tag(chunk):
                blocks.append(chunk)
            elif self.is_blank_html_chunk(chunk):
                continue
            elif BLOCK_TAG_RE.match(chunk):
                blocks.append(chunk)
            elif HTML_TAG_RE.search(chunk) or chunk:
                blocks.append(f"<p>{chunk}</p>")

        return "\n".join(blocks)

    def is_standalone_media_tag(self, html: str) -> bool:
        return bool(re.fullmatch(r"<(img|video|audio|iframe)\b[^>]*(?:/>|>.*?</\1>)", html, re.IGNORECASE | re.DOTALL))

    def is_blank_html_chunk(self, html: str) -> bool:
        text = HTML_TAG_RE.sub("", html)
        text = text.replace("&nbsp;", "").replace("&#160;", "").replace("\xa0", "")
        return not text.strip()

    def unique_slug(self, source: str, model, max_length: int) -> str:
        base = slugify_max(source, max_length=max_length) or "wordpress"
        if len(base) <= max_length:
            return base
        return base[:max_length].strip("-") or "wordpress"

    def get_or_create_author(self, username: str) -> Member:
        member = Member.objects.filter(username=username).first()
        if member:
            return member

        membership_type = MembershipType.objects.filter(pk=FRESHMAN).first() or MembershipType.objects.first()
        if membership_type is None:
            membership_type = MembershipType.objects.create(
                name="Imported",
                description="Created by the WordPress importer.",
                permission_profile=FRESHMAN,
            )
        return Member.objects.create(
            username=username[:20],
            first_name="WordPress",
            last_name="Import",
            membership_type=membership_type,
            is_active=False,
        )

    def public_media_storage(self):
        if getattr(settings, "USE_S3", False):
            return storages["public_media"]
        return default_storage

    def local_source_path(self, media_dir: Path, url: str) -> Path:
        parsed = urlparse(url)
        parts = [part for part in unquote(parsed.path).split("/") if part]
        candidate = (media_dir / Path(*parts)).resolve()
        # Reject URL paths containing ".." segments that would escape
        # media_dir before resolution copies arbitrary files into storage.
        media_root = media_dir.resolve()
        try:
            candidate.relative_to(media_root)
        except ValueError:
            return media_dir / "__rejected__"
        return candidate

    def storage_name_for_url(self, media_prefix: str, url: str) -> str:
        parsed = urlparse(url)
        parts = [part for part in unquote(parsed.path).split("/") if part]
        cleaned_parts = [self.clean_path_part(part) for part in parts]
        return "/".join([media_prefix, *cleaned_parts])

    def child_text(self, element: ET.Element, name: str) -> str:
        found = element.find(name, WXR_NS) if ":" in name else element.find(name)
        return found.text if found is not None and found.text is not None else ""

    def parse_wp_datetime(self, value: str) -> datetime:
        if not value or value.startswith("0000-00-00"):
            return timezone.now()
        try:
            if "," in value:
                parsed = parsedate_to_datetime(value)
            else:
                parsed = datetime.fromisoformat(value)
        except ValueError:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed.astimezone(timezone.get_current_timezone())

    def clean_path_part(self, value: str) -> str:
        name, extension = os.path.splitext(value)
        extension = extension.lower()
        cleaned_name = slugify(name, allow_unicode=False) or "file"
        guessed_extension = extension or mimetypes.guess_extension(mimetypes.guess_type(value)[0] or "") or ""
        return f"{cleaned_name}{guessed_extension}"

    def plain_text(self, html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1000]

    def print_summary(self, stats: ImportStats, dry_run: bool):
        prefix = "Dry-run planned" if dry_run else "Imported"
        self.stdout.write(self.style.SUCCESS(f"{prefix} WordPress export import:"))
        self.stdout.write(f"  media saved: {stats.media_saved}")
        self.stdout.write(f"  media already present: {stats.media_existing}")
        self.stdout.write(f"  media missing locally: {stats.media_missing}")
        self.stdout.write(f"  posts created/updated: {stats.posts_created}/{stats.posts_updated}")
        self.stdout.write(f"  pages created/updated: {stats.pages_created}/{stats.pages_updated}")
        self.stdout.write(f"  publications created/updated: {stats.publications_created}/{stats.publications_updated}")
        self.stdout.write(f"  categories created: {stats.categories_created}")
        self.stdout.write(f"  nav categories created: {stats.nav_categories_created}")
        self.stdout.write(f"  nav urls created: {stats.nav_urls_created}")
        self.stdout.write(
            f"  gallery redirects created/updated: {stats.gallery_redirects_created}/{stats.gallery_redirects_updated}"
        )
        self.stdout.write(
            f"  gallery thumbnails saved/missing: {stats.gallery_thumbnails_saved}/{stats.gallery_thumbnails_missing}"
        )
        self.stdout.write(
            f"  exam collections created/updated: {stats.exam_collections_created}/{stats.exam_collections_updated}"
        )
        self.stdout.write(
            f"  exam documents created/updated/missing: "
            f"{stats.exam_documents_created}/{stats.exam_documents_updated}/{stats.exam_documents_missing}"
        )
        self.stdout.write(f"  functionary roles created: {stats.functionary_roles_created}")
        self.stdout.write(
            f"  functionaries created/updated: {stats.functionaries_created}/{stats.functionaries_updated}"
        )
        if stats.skipped_items:
            self.stdout.write(f"  skipped item types: {dict(stats.skipped_items)}")


class AnchorExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "a":
            self._current = {"href": attrs.get("href", ""), "text": ""}

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"] += data

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current is not None:
            self.anchors.append(self._current)
            self._current = None


class AOPublicationPageParser(HTMLParser):
    ISSUE_RE = re.compile(r"^\d{1,2}(?:/\d{4})?$")
    YEAR_RE = re.compile(r"\b(20\d{2})\b")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current_year = ""
        self.in_heading = False
        self.heading_text = ""
        self.in_table = False
        self.table_labels = []
        self.table_link_index = 0
        self.in_cell = False
        self.cell_text = ""
        self.cell_anchors = []
        self.current_anchor = None

    @classmethod
    def parse(cls, html: str) -> list[dict]:
        parser = cls()
        parser.feed(html or "")
        parser.close()
        return parser.links

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.in_heading = True
            self.heading_text = ""
        elif tag == "table":
            self.in_table = True
            self.table_labels = []
            self.table_link_index = 0
        elif tag == "td" and self.in_table:
            self.in_cell = True
            self.cell_text = ""
            self.cell_anchors = []
        elif tag == "a" and self.in_cell:
            self.current_anchor = {"href": attrs.get("href", ""), "text": "", "image_src": ""}
        elif tag == "img" and self.current_anchor is not None:
            self.current_anchor["image_src"] = attrs.get("src", "")

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text += data
        if self.in_cell:
            self.cell_text += data
        if self.current_anchor is not None:
            self.current_anchor["text"] += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.in_heading:
            match = self.YEAR_RE.search(self.heading_text)
            if match:
                self.current_year = match.group(1)
            self.in_heading = False
            self.heading_text = ""
        elif tag == "a" and self.current_anchor is not None:
            self.cell_anchors.append(self.current_anchor)
            self.current_anchor = None
        elif tag == "td" and self.in_cell:
            self.flush_cell()
        elif tag == "table":
            self.in_table = False
            self.table_labels = []
            self.table_link_index = 0

    def flush_cell(self):
        text = re.sub(r"\s+", " ", self.cell_text).strip()
        if self.cell_anchors:
            for anchor in self.cell_anchors:
                issue_label = self.issue_label_for_current_link(anchor, text)
                if not issue_label:
                    continue
                self.links.append(
                    {
                        "title": f"A&O {issue_label}",
                        "url": anchor["href"].strip(),
                        "cover_image_url": anchor.get("image_src", "").strip(),
                        "publication_date": self.publication_date(issue_label),
                    }
                )
                self.table_link_index += 1
        elif self.ISSUE_RE.match(text):
            self.table_labels.append(text)

        self.in_cell = False
        self.cell_text = ""
        self.cell_anchors = []

    def issue_label_for_current_link(self, anchor: dict, fallback_text: str) -> str:
        label = (
            self.table_labels[self.table_link_index]
            if self.table_link_index < len(self.table_labels)
            else fallback_text
        )
        label = label.strip()
        if not label:
            label = re.sub(r"\s+", " ", anchor.get("text") or "").strip()
        if label and "/" not in label and self.current_year:
            label = f"{label}/{self.current_year}"
        return label

    def publication_date(self, issue_label: str):
        match = re.match(r"^(\d{1,2})/(\d{4})$", issue_label)
        if not match:
            return None
        issue_number = max(1, min(12, int(match.group(1))))
        year = int(match.group(2))
        return datetime(year, issue_number, 1).date()


class PoliticusPublicationPageParser(HTMLParser):
    YEAR_RE = re.compile(r"\b(20\d{2})\b")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.in_heading = False
        self.heading_text = ""
        self.current_anchor = None
        self.heading_anchors = []

    @classmethod
    def parse(cls, html: str) -> list[dict]:
        parser = cls()
        parser.feed(html or "")
        parser.close()
        return parser.links

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.in_heading = True
            self.heading_text = ""
            self.heading_anchors = []
        elif tag == "a" and self.in_heading:
            self.current_anchor = {"href": attrs.get("href", ""), "text": "", "image_src": ""}
        elif tag == "img" and self.current_anchor is not None:
            self.current_anchor["image_src"] = attrs.get("src", "")

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text += data
        if self.current_anchor is not None:
            self.current_anchor["text"] += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self.current_anchor is not None:
            self.heading_anchors.append(self.current_anchor)
            self.current_anchor = None
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.in_heading:
            self.flush_heading()

    def flush_heading(self):
        year_match = self.YEAR_RE.search(self.heading_text)
        if year_match:
            year = int(year_match.group(1))
            for anchor in self.heading_anchors:
                if not anchor.get("href"):
                    continue
                self.links.append(
                    {
                        "title": f"Politicus {year}",
                        "url": anchor["href"].strip(),
                        "cover_image_url": anchor.get("image_src", "").strip(),
                        "publication_date": datetime(year, 1, 1).date(),
                    }
                )
        self.in_heading = False
        self.heading_text = ""
        self.heading_anchors = []


class FunctionaryPageParser(HTMLParser):
    YEAR_HEADING_RE = re.compile(r"\bStyrelse\s+(\d{4})\b", re.IGNORECASE)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_year = None
        self.current_role = ""
        self.current_name = ""
        self.in_heading = False
        self.heading_text = ""
        self.in_role = False

    @classmethod
    def parse(cls, html: str) -> list[dict]:
        parser = cls()
        parser.feed(html or "")
        parser.close()
        return parser.rows

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush_row()
            self.in_heading = True
            self.heading_text = ""
        elif tag in {"strong", "b"}:
            self.flush_row()
            self.in_role = True
            self.current_role = ""
            self.current_name = ""
        elif tag in {"br", "p", "div", "li"}:
            self.current_name += " "

    def handle_data(self, data):
        if self.in_heading:
            self.heading_text += data
        elif self.in_role:
            self.current_role += data
        elif self.current_role:
            self.current_name += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.in_heading:
            match = self.YEAR_HEADING_RE.search(self.clean_text(self.heading_text))
            if match:
                self.current_year = int(match.group(1))
            self.in_heading = False
            self.heading_text = ""
        elif tag in {"strong", "b"}:
            self.in_role = False
        elif tag in {"p", "div", "li"}:
            self.flush_row()

    def close(self):
        super().close()
        self.flush_row()

    def flush_row(self):
        role = self.clean_role(self.current_role)
        name = self.clean_text(self.current_name)
        if self.current_year and role and name:
            self.rows.append(
                {
                    "year": self.current_year,
                    "role": role,
                    "name": name,
                }
            )
        self.current_role = ""
        self.current_name = ""

    def clean_role(self, value: str) -> str:
        role = self.clean_text(value).strip(":")
        return role[:200]

    def clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()
