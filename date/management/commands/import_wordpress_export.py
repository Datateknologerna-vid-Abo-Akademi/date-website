from __future__ import annotations

import json
import mimetypes
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage, storages
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from archive.models import Collection
from date.functions import slugify_max
from members.models import FRESHMAN, Member, MembershipType
from news.models import Category, Post
from publications.models import PDFFile
from staticpages.models import POST_SLUG_MAX_LENGTH as STATICPAGE_SLUG_MAX_LENGTH
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


WXR_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}

URL_RE = re.compile(r"https?://[^\s<\]\"')]+")
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
PUBLICATION_EXTENSIONS = {".pdf"}
IGNORED_CATEGORY_SLUGS = {"nyheter", "uncategorized"}
GALLERY_LINK_HOSTS = {
    "photos.app.goo.gl",
    "photos.google.com",
    "drive.google.com",
}
GALLERY_SOURCE_SLUGS = {"bildgalleriet", "gamla-bilder"}


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
    skipped_items: Counter = field(default_factory=Counter)
    missing_media_urls: list[str] = field(default_factory=list)


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
        "Import a WordPress WXR export into news/static pages/publications and "
        "copy referenced upload files through Django storage."
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
                "Create news categories from WordPress categories. By default generic "
                "'Nyheter' and 'Uncategorized' are imported as normal uncategorized news."
            ),
        )
        parser.add_argument(
            "--skip-media",
            action="store_true",
            help="Do not copy media files. Content URLs are left as they are.",
        )
        parser.add_argument(
            "--skip-publications",
            action="store_true",
            help="Do not create publication records from PDF attachment items.",
        )
        parser.add_argument(
            "--import-nav",
            action="store_true",
            help="Import WordPress nav_menu_item records into StaticPageNav/StaticUrl.",
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
            help="Import Google Photos/Drive gallery links as redirecting picture albums.",
        )
        parser.add_argument(
            "--replace-gallery-redirects",
            action="store_true",
            help="Delete existing redirect-only picture albums before importing gallery redirects.",
        )
        parser.add_argument(
            "--report",
            help="Optional JSON report path. Defaults to <xml parent>/wordpress-import-report.json.",
        )

    def handle(self, *args, **options):
        xml_path = Path(options["xml_path"]).expanduser().resolve()
        if not xml_path.exists():
            raise CommandError(f"XML export does not exist: {xml_path}")

        media_dir = Path(
            options["media_dir"]
            or xml_path.parent / "sfklubben-export-local" / "assets" / "sfklubben.fi"
        ).expanduser().resolve()
        if not options["skip_media"] and not media_dir.exists():
            raise CommandError(
                f"Media directory does not exist: {media_dir}. "
                "Run with --skip-media or pass --media-dir."
            )

        report_path = Path(
            options["report"] or xml_path.parent / "wordpress-import-report.json"
        ).expanduser().resolve()

        xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
        items = self.parse_items(xml_path)
        upload_urls = self.collect_upload_urls(xml_text)
        storage = self.public_media_storage()
        stats = ImportStats()
        url_map: dict[str, str] = {}
        storage_name_map: dict[str, str] = {}

        self.stdout.write(
            f"Parsed {len(items)} WordPress items and {len(upload_urls)} sfklubben.fi upload URLs."
        )

        if not options["skip_media"]:
            url_map = self.import_media(
                upload_urls,
                media_dir,
                storage,
                options["media_prefix"].strip("/"),
                options["dry_run"],
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
                elif item.post_type == "attachment" and not options["skip_publications"]:
                    self.import_publication(item, storage, storage_name_map, options, stats)
                elif item.post_type == "nav_menu_item" and options["import_nav"]:
                    continue
                else:
                    stats.skipped_items[item.post_type] += 1

            if options["import_nav"]:
                self.import_navigation(items, url_map, options, stats)
            if options["import_gallery_redirects"]:
                self.import_gallery_redirects(items, url_map, options, stats)

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
                "skipped_items": dict(stats.skipped_items),
            },
            "missing_media_urls": stats.missing_media_urls,
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
        return sorted(urls)

    def import_media(
        self,
        urls: list[str],
        media_dir: Path,
        storage,
        media_prefix: str,
        dry_run: bool,
        stats: ImportStats,
        storage_name_map: dict[str, str],
    ) -> dict[str, str]:
        url_map = {}
        for url in urls:
            source = self.local_source_path(media_dir, url)
            if not source.exists():
                stats.media_missing += 1
                stats.missing_media_urls.append(url)
                continue

            storage_name = self.storage_name_for_url(media_prefix, url)
            if dry_run:
                stats.media_saved += 1
                url_map[url] = f"DRY-RUN:{storage_name}"
                storage_name_map[url] = storage_name
                continue

            if storage.exists(storage_name):
                stats.media_existing += 1
            else:
                with source.open("rb") as source_file:
                    saved_name = storage.save(storage_name, File(source_file, name=source.name))
                storage_name = saved_name
                stats.media_saved += 1
            url_map[url] = storage.url(storage_name)
            storage_name_map[url] = storage_name
        return url_map

    def import_post(self, item: WpItem, author: Member | None, url_map: dict[str, str], options, stats: ImportStats):
        slug = self.unique_slug(item.slug or item.title, Post, max_length=Post._meta.get_field("slug").max_length)
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
            "published": item.status == "publish",
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

    def import_publication(
        self,
        item: WpItem,
        storage,
        storage_name_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        if not item.attachment_url:
            return
        extension = Path(unquote(urlparse(item.attachment_url).path)).suffix.lower()
        if extension not in PUBLICATION_EXTENSIONS:
            return

        storage_name = storage_name_map.get(item.attachment_url)
        if not storage_name and not options["dry_run"]:
            if options["skip_media"]:
                stats.media_missing += 1
                stats.missing_media_urls.append(item.attachment_url)
            return

        slug = self.unique_slug(item.slug or item.title, PDFFile, max_length=PDFFile._meta.get_field("slug").max_length)
        existing = PDFFile.objects.filter(slug=slug).first()
        if existing and not options["update_existing"]:
            return

        if options["dry_run"]:
            stats.publications_updated += int(existing is not None)
            stats.publications_created += int(existing is None)
            return

        storage_name = self.publication_storage_name(item, storage_name, slug, storage)
        fields = {
            "title": item.title[:250],
            "description": self.plain_text(item.excerpt or item.content),
            "publication_date": item.post_date.date(),
            "is_public": item.status != "private",
            "requires_login": item.status == "private",
            "file": storage_name,
        }
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.publications_updated += 1
        else:
            PDFFile.objects.create(slug=slug, **fields)
            stats.publications_created += 1

    def import_navigation(
        self,
        items: list[WpItem],
        url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        menu_slug = options["nav_menu"]
        nav_items = [
            item for item in items
            if item.post_type == "nav_menu_item"
            and any(slug == menu_slug for slug, _name in item.nav_menus)
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
                dropdown_items = [(top_item, title, top_url)]
                for child in descendants:
                    dropdown_items.append(
                        (
                            child,
                            self.nav_dropdown_title(child, item_by_id, object_by_id),
                            self.nav_url(child, object_by_id, url_map),
                        )
                    )
                for dropdown_index, (_item, dropdown_title, dropdown_url) in enumerate(dropdown_items, start=1):
                    if not dropdown_title or not dropdown_url:
                        continue
                    _url, created = StaticUrl.objects.update_or_create(
                        category=category,
                        title=dropdown_title[:255],
                        defaults={
                            "url": dropdown_url[:200],
                            "dropdown_element": dropdown_index * 10,
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
            Collection.objects.filter(type="Pictures", redirect_url__gt="").delete()

        for link in links:
            collection = Collection.objects.filter(type="Pictures", title=link["title"]).first()
            fields = {
                "pub_date": link["pub_date"],
                "redirect_url": link["url"],
                "hide_for_gulis": False,
            }
            if collection:
                for key, value in fields.items():
                    setattr(collection, key, value)
                collection.save()
                stats.gallery_redirects_updated += 1
            else:
                Collection.objects.create(
                    title=link["title"][:250],
                    type="Pictures",
                    **fields,
                )
                stats.gallery_redirects_created += 1

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
                links.append({
                    "title": title,
                    "url": url,
                    "pub_date": self.gallery_pub_date(title, item.post_date),
                })
        return links

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
                return f"/news/articles/{self.unique_slug(object_item.slug or object_item.title, Post, Post._meta.get_field('slug').max_length)}/"
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

    def publication_storage_name(self, item: WpItem, source_name: str, slug: str, storage) -> str:
        max_length = PDFFile._meta.get_field("file").max_length or 100
        if len(source_name) <= max_length:
            return source_name

        original_name = Path(unquote(urlparse(item.attachment_url).path)).name
        cleaned_name = self.clean_path_part(original_name)
        extension = Path(cleaned_name).suffix
        base = Path(cleaned_name).stem

        slug_budget = 44
        short_slug = slugify_max(slug, max_length=slug_budget) or "wordpress"
        reserved = len("pdfs//") + len(short_slug) + len(extension)
        filename_budget = max(12, max_length - reserved)
        short_base = slugify_max(base, max_length=filename_budget) or "file"
        target_name = f"pdfs/{short_slug}/{short_base}{extension}"

        if len(target_name) > max_length:
            target_name = f"pdfs/{short_slug[:32].strip('-')}/{short_base[:45].strip('-')}{extension}"

        if not storage.exists(target_name):
            with storage.open(source_name, "rb") as source_file:
                storage.save(target_name, File(source_file, name=Path(target_name).name))
        return target_name

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
        return media_dir / Path(*parts)

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
        self.stdout.write(
            f"  publications created/updated: {stats.publications_created}/{stats.publications_updated}"
        )
        self.stdout.write(f"  categories created: {stats.categories_created}")
        self.stdout.write(f"  nav categories created: {stats.nav_categories_created}")
        self.stdout.write(f"  nav urls created: {stats.nav_urls_created}")
        self.stdout.write(
            f"  gallery redirects created/updated: "
            f"{stats.gallery_redirects_created}/{stats.gallery_redirects_updated}"
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
