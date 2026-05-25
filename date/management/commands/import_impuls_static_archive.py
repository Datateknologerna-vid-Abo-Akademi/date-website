from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
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
from django.utils.html import strip_tags
from django.utils.text import slugify

from date.functions import slugify_max
from members.models import FRESHMAN, Member, MembershipType
from news.models import Category, Post
from staticpages.models import POST_SLUG_MAX_LENGTH as STATICPAGE_SLUG_MAX_LENGTH
from staticpages.models import StaticPage, StaticPageNav, StaticUrl

IMPULS_HOST = "impuls.divanen.fi"
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
UPLOAD_URL_RE = re.compile(
    r"(?:https?:)?//impuls\.divanen\.fi(/wp-content/uploads/[^\s<\"')]+)"
    r"|(/wp-content/uploads/[^\s<\"')]+)"
)
UNWANTED_BLOCK_RE = re.compile(r"<(script|style|iframe|object|embed)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
UNWANTED_SINGLE_RE = re.compile(r"<(link|meta)\b[^>]*>", re.IGNORECASE)
WP_SHORTCODE_RE = re.compile(r"\[/?(?:caption|gallery|embed|video|audio)[^\]]*\]", re.IGNORECASE)


@dataclass
class ImportStats:
    media_saved: int = 0
    media_existing: int = 0
    media_missing: int = 0
    pages_created: int = 0
    pages_updated: int = 0
    posts_created: int = 0
    posts_updated: int = 0
    categories_created: int = 0
    nav_categories_created: int = 0
    nav_urls_created: int = 0
    skipped: Counter = field(default_factory=Counter)
    missing_media_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PageCandidate:
    title: str
    slug: str
    content: str
    created_time: datetime
    modified_time: datetime | None
    members_only: bool = False
    source_url: str = ""


@dataclass(frozen=True)
class PostCandidate:
    title: str
    slug: str
    content: str
    published_time: datetime
    category_name: str = ""
    category_slug: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class NavCandidate:
    title: str
    href: str
    level: int


class Command(BaseCommand):
    help = "Import the latest recoverable Impuls WordPress static archive into Django content apps."

    def add_arguments(self, parser):
        parser.add_argument(
            "--archive-dir",
            default=str(Path(settings.BASE_DIR) / "impuls"),
            help="Static WordPress archive directory. Default: <BASE_DIR>/impuls",
        )
        parser.add_argument(
            "--media-prefix",
            default="wordpress/impuls",
            help="Storage prefix for copied WordPress uploads. Default: wordpress/impuls",
        )
        parser.add_argument(
            "--author",
            default="wp-import",
            help="Member username to use as imported news author. Created if missing.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse and report changes without writing.")
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing rows with matching slugs. Without this, matching rows are skipped.",
        )
        parser.add_argument("--import-nav", action="store_true", help="Import the current WordPress navigation menu.")
        parser.add_argument(
            "--replace-nav",
            action="store_true",
            help="Delete existing StaticPageNav/StaticUrl rows before importing navigation.",
        )
        parser.add_argument(
            "--report",
            help="Optional JSON report path. Defaults to <archive-dir>/impuls-import-report.json.",
        )

    def handle(self, *args, **options):
        archive_dir = Path(options["archive_dir"]).expanduser().resolve()
        if not archive_dir.exists():
            raise CommandError(f"Archive directory does not exist: {archive_dir}")

        report_path = Path(options["report"] or archive_dir / "impuls-import-report.json").expanduser().resolve()
        pages = self.collect_pages(archive_dir)
        posts = self.collect_posts(archive_dir)
        content_blobs = [page.content for page in pages] + [post.content for post in posts]
        upload_paths = self.collect_upload_paths(content_blobs)
        storage = self.public_media_storage()
        stats = ImportStats()

        self.stdout.write(
            f"Parsed {len(pages)} page candidates, {len(posts)} post candidates, "
            f"and {len(upload_paths)} referenced upload paths."
        )

        url_map = self.import_media(
            archive_dir,
            storage,
            options["media_prefix"].strip("/"),
            upload_paths,
            options["dry_run"],
            stats,
        )
        page_url_map = self.page_url_map(pages)
        post_url_map = self.post_url_map(posts)

        author = None
        if posts and not options["dry_run"]:
            author = self.get_or_create_author(options["author"])

        if options["dry_run"]:
            for page in pages:
                self.import_page(page, url_map, page_url_map, post_url_map, options, stats)
            for post in posts:
                self.import_post(post, author, url_map, page_url_map, post_url_map, options, stats)
            if options["import_nav"]:
                self.import_navigation(archive_dir, page_url_map, post_url_map, options, stats)
        else:
            with transaction.atomic():
                for page in pages:
                    self.import_page(page, url_map, page_url_map, post_url_map, options, stats)
                for post in posts:
                    self.import_post(post, author, url_map, page_url_map, post_url_map, options, stats)
                if options["import_nav"]:
                    self.import_navigation(archive_dir, page_url_map, post_url_map, options, stats)

        report = {
            "archive_dir": str(archive_dir),
            "dry_run": options["dry_run"],
            "stats": {
                "media_saved": stats.media_saved,
                "media_existing": stats.media_existing,
                "media_missing": stats.media_missing,
                "pages_created": stats.pages_created,
                "pages_updated": stats.pages_updated,
                "posts_created": stats.posts_created,
                "posts_updated": stats.posts_updated,
                "categories_created": stats.categories_created,
                "nav_categories_created": stats.nav_categories_created,
                "nav_urls_created": stats.nav_urls_created,
                "skipped": dict(stats.skipped),
            },
            "missing_media_paths": stats.missing_media_paths,
        }
        if not options["dry_run"]:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"Wrote import report to {report_path}")

        self.print_summary(stats, options["dry_run"])

    def collect_pages(self, archive_dir: Path) -> list[PageCandidate]:
        pages_by_slug: dict[str, PageCandidate] = {}
        for json_path in sorted((archive_dir / "wp-json" / "wp" / "v2" / "pages").glob("*/index.html")):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            page = self.page_from_rest_payload(payload)
            if page:
                pages_by_slug[page.slug] = page

        for html_path in self.canonical_html_pages(archive_dir):
            html = html_path.read_text(encoding="utf-8", errors="replace")
            page = self.page_from_html(archive_dir, html_path, html)
            if page and page.slug not in pages_by_slug:
                pages_by_slug[page.slug] = page

        return sorted(pages_by_slug.values(), key=lambda page: (page.created_time, page.slug))

    def page_from_rest_payload(self, payload: dict) -> PageCandidate | None:
        title = self.rendered(payload.get("title", {})).strip()
        content = self.rendered(payload.get("content", {})).strip()
        if not title or not content:
            return None
        slug = self.slug_for_page(payload.get("slug", ""), title, payload.get("link", ""))
        return PageCandidate(
            title=title,
            slug=slug,
            content=content,
            created_time=self.parse_datetime(payload.get("date")),
            modified_time=self.parse_datetime(payload.get("modified")) if payload.get("modified") else None,
            members_only=bool(payload.get("content", {}).get("protected")),
            source_url=payload.get("link", ""),
        )

    def page_from_html(self, archive_dir: Path, html_path: Path, html: str) -> PageCandidate | None:
        if self.is_challenge_page(html):
            return None
        content = EntryContentParser.parse(html)
        title = HtmlTitleParser.parse(html)
        if not title or not content:
            return None
        title = re.sub(r"\s+[–-]\s+Impuls$", "", title).strip()
        slug = self.slug_for_local_path(archive_dir, html_path, title)
        return PageCandidate(
            title=title,
            slug=slug,
            content=content,
            created_time=self.modified_time(html_path),
            modified_time=self.modified_time(html_path),
            source_url=self.source_url_for_path(archive_dir, html_path),
        )

    def canonical_html_pages(self, archive_dir: Path) -> list[Path]:
        ignored_parts = {
            "wp-admin",
            "wp-content",
            "wp-includes",
            "wp-json",
            "feed",
            "comments",
            "category",
            "author",
            "blog",
        }
        pages = []
        for html_path in archive_dir.glob("**/index.html"):
            relative = html_path.relative_to(archive_dir)
            parts = set(relative.parts)
            if ignored_parts & parts:
                continue
            if any(part.startswith("__q") for part in relative.parts):
                continue
            if html_path == archive_dir / "index.html":
                continue
            pages.append(html_path)
        return sorted(pages)

    def collect_posts(self, archive_dir: Path) -> list[PostCandidate]:
        posts_by_slug: dict[str, PostCandidate] = {}
        for html_path in [archive_dir / "blog" / "index.html", archive_dir / "blog" / "page" / "2" / "index.html"]:
            if not html_path.exists():
                continue
            for post in BlogIndexParser.parse(html_path.read_text(encoding="utf-8", errors="replace")):
                posts_by_slug.setdefault(post.slug, post)
        return sorted(posts_by_slug.values(), key=lambda post: post.published_time)

    def collect_upload_paths(self, content_blobs: list[str]) -> list[str]:
        paths = set()
        for content in content_blobs:
            for match in UPLOAD_URL_RE.finditer(content):
                path = match.group(1) or match.group(2)
                if not path:
                    continue
                path = unquote(urlparse(path).path)
                if Path(path).suffix.lower() in MEDIA_EXTENSIONS:
                    paths.add(path)
        return sorted(paths)

    def import_media(
        self,
        archive_dir: Path,
        storage,
        media_prefix: str,
        upload_paths: list[str],
        dry_run: bool,
        stats: ImportStats,
    ) -> dict[str, str]:
        url_map = {}
        for upload_path in upload_paths:
            source = self.local_upload_path(archive_dir, upload_path)
            storage_name = self.storage_name_for_upload(media_prefix, upload_path)
            source_urls = self.upload_source_urls(upload_path)
            if storage.exists(storage_name):
                stats.media_existing += 1
                for source_url in source_urls:
                    url_map[source_url] = storage.url(storage_name)
                continue
            if not source.exists():
                stats.media_missing += 1
                stats.missing_media_paths.append(upload_path)
                continue
            if dry_run:
                stats.media_saved += 1
                for source_url in source_urls:
                    url_map[source_url] = f"DRY-RUN:{storage_name}"
                continue
            with source.open("rb") as source_file:
                saved_name = storage.save(storage_name, File(source_file, name=source.name))
            stats.media_saved += 1
            for source_url in source_urls:
                url_map[source_url] = storage.url(saved_name)
        return url_map

    def import_page(
        self,
        page: PageCandidate,
        url_map: dict[str, str],
        page_url_map: dict[str, str],
        post_url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        if options["dry_run"]:
            stats.pages_created += 1
            return
        existing = StaticPage.objects.filter(slug=page.slug).first()
        if existing and not options["update_existing"]:
            stats.skipped["existing_pages"] += 1
            return
        fields = {
            "title": page.title[:255],
            "content": self.prepare_content(page.content, url_map, page_url_map, post_url_map),
            "created_time": page.created_time,
            "modified_time": page.modified_time,
            "members_only": page.members_only,
        }
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.pages_updated += 1
        else:
            StaticPage.objects.create(slug=page.slug, **fields)
            stats.pages_created += 1

    def import_post(
        self,
        post: PostCandidate,
        author: Member | None,
        url_map: dict[str, str],
        page_url_map: dict[str, str],
        post_url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        if options["dry_run"]:
            stats.posts_created += 1
            stats.categories_created += int(bool(post.category_name))
            return
        existing = Post.objects.filter(slug=post.slug).first()
        if existing and not options["update_existing"]:
            stats.skipped["existing_posts"] += 1
            return
        category = self.category_for_post(post, options["dry_run"], stats)
        fields = {
            "title": post.title[:255],
            "content": self.prepare_content(post.content, url_map, page_url_map, post_url_map),
            "author": author,
            "created_time": post.published_time,
            "published_time": post.published_time,
            "modified_time": post.published_time,
            "category": category,
        }
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.save()
            stats.posts_updated += 1
        else:
            Post.objects.create(slug=post.slug, **fields)
            stats.posts_created += 1

    def import_navigation(
        self,
        archive_dir: Path,
        page_url_map: dict[str, str],
        post_url_map: dict[str, str],
        options,
        stats: ImportStats,
    ):
        homepage = archive_dir / "index.html"
        if not homepage.exists():
            self.stdout.write(self.style.WARNING("No Impuls homepage found for navigation import."))
            return
        nav_items = NavigationParser.parse(homepage.read_text(encoding="utf-8", errors="replace"))
        if not nav_items:
            self.stdout.write(self.style.WARNING("No WordPress navigation items found."))
            return
        if options["dry_run"]:
            stats.nav_categories_created += len([item for item in nav_items if item.level == 1])
            stats.nav_urls_created += len(nav_items)
            return
        if options["replace_nav"]:
            StaticUrl.objects.all().delete()
            StaticPageNav.objects.all().delete()

        current_category = None
        current_parent_url = None
        nav_element = 10
        dropdown_element = 10
        for item in nav_items:
            url = self.resolve_imported_url(item.href, page_url_map, post_url_map)
            if item.level == 1:
                has_children = self.nav_item_has_children(item, nav_items)
                current_category, created = StaticPageNav.objects.update_or_create(
                    category_name=item.title[:255],
                    defaults={
                        "nav_element": nav_element,
                        "use_category_url": not has_children,
                        "url": url if not has_children else "",
                    },
                )
                stats.nav_categories_created += int(created)
                nav_element += 10
                dropdown_element = 10
                current_parent_url = None
                if has_children and url:
                    current_parent_url, created = StaticUrl.objects.update_or_create(
                        category=current_category,
                        title=item.title[:255],
                        parent=None,
                        defaults={"url": url[:200], "dropdown_element": dropdown_element, "logged_in_only": False},
                    )
                    dropdown_element += 10
                    stats.nav_urls_created += int(created)
                continue
            if current_category is None:
                continue
            parent = current_parent_url if item.level > 2 else None
            lookup_category = current_category if parent is None else parent.category
            url_obj, created = StaticUrl.objects.update_or_create(
                category=lookup_category,
                parent=parent,
                title=item.title[:255],
                defaults={"url": url[:200], "dropdown_element": dropdown_element, "logged_in_only": False},
            )
            if item.level == 2:
                current_parent_url = url_obj
            dropdown_element += 10
            stats.nav_urls_created += int(created)

    def nav_item_has_children(self, item: NavCandidate, nav_items: list[NavCandidate]) -> bool:
        try:
            index = nav_items.index(item)
        except ValueError:
            return False
        return index + 1 < len(nav_items) and nav_items[index + 1].level > item.level

    def category_for_post(self, post: PostCandidate, dry_run: bool, stats: ImportStats):
        if not post.category_name:
            return None
        slug = post.category_slug or slugify(post.category_name)
        existing = Category.objects.filter(slug=slug).first()
        if existing or dry_run:
            stats.categories_created += int(existing is None and dry_run)
            return existing
        category = Category.objects.create(name=post.category_name[:255], slug=slug)
        stats.categories_created += 1
        return category

    def prepare_content(
        self,
        html: str,
        url_map: dict[str, str],
        page_url_map: dict[str, str],
        post_url_map: dict[str, str],
    ) -> str:
        content = html or ""
        content = UNWANTED_BLOCK_RE.sub("", content)
        content = UNWANTED_SINGLE_RE.sub("", content)
        content = WP_SHORTCODE_RE.sub("", content)
        for source_url, target_url in {**url_map, **page_url_map, **post_url_map}.items():
            content = content.replace(source_url, target_url)
            if source_url.startswith("http://"):
                content = content.replace("https://" + source_url[len("http://") :], target_url)
        return content.strip()

    def page_url_map(self, pages: list[PageCandidate]) -> dict[str, str]:
        mapping = {}
        for page in pages:
            target = reverse("staticpages:page", args=[page.slug])
            for source in self.source_url_candidates(page.source_url, page.slug):
                mapping[source] = target
        mapping["http://impuls.divanen.fi/"] = "/"
        mapping["https://impuls.divanen.fi/"] = "/"
        return mapping

    def post_url_map(self, posts: list[PostCandidate]) -> dict[str, str]:
        mapping = {}
        for post in posts:
            target = reverse("news:detail", args=[post.slug])
            for source in self.source_url_candidates(post.source_url, post.slug):
                mapping[source] = target
        return mapping

    def source_url_candidates(self, source_url: str, slug: str) -> list[str]:
        candidates = set()
        if source_url:
            candidates.add(source_url.rstrip("/"))
            candidates.add(source_url.rstrip("/") + "/")
        if slug:
            candidates.add(f"http://{IMPULS_HOST}/{slug}")
            candidates.add(f"http://{IMPULS_HOST}/{slug}/")
            candidates.add(f"https://{IMPULS_HOST}/{slug}")
            candidates.add(f"https://{IMPULS_HOST}/{slug}/")
        return sorted(candidates)

    def resolve_imported_url(self, href: str, page_url_map: dict[str, str], post_url_map: dict[str, str]) -> str:
        if not href or href == "#":
            return ""
        normalized = href.rstrip("/")
        if href in page_url_map or normalized in page_url_map:
            return page_url_map.get(href) or page_url_map[normalized]
        if href in post_url_map or normalized in post_url_map:
            return post_url_map.get(href) or post_url_map[normalized]
        parsed = urlparse(href)
        if parsed.netloc.lower() == IMPULS_HOST:
            path = parsed.path or "/"
            if path == "/":
                return "/"
            return path if path.endswith("/") else f"{path}/"
        return href

    def local_upload_path(self, archive_dir: Path, upload_path: str) -> Path:
        parts = [part for part in unquote(upload_path).split("/") if part]
        candidate = (archive_dir / Path(*parts)).resolve()
        try:
            candidate.relative_to(archive_dir.resolve())
        except ValueError:
            return archive_dir / "__rejected__"
        return candidate

    def storage_name_for_upload(self, media_prefix: str, upload_path: str) -> str:
        parts = [slugify(part) or "file" for part in unquote(upload_path).split("/") if part]
        if parts and "." in parts[-1]:
            stem, suffix = Path(parts[-1]).stem, Path(unquote(upload_path)).suffix.lower()
            parts[-1] = f"{stem}{suffix}"
        return "/".join([media_prefix, *parts])

    def upload_source_urls(self, upload_path: str) -> list[str]:
        return [
            upload_path,
            f"http://{IMPULS_HOST}{upload_path}",
            f"https://{IMPULS_HOST}{upload_path}",
        ]

    def rendered(self, value) -> str:
        if isinstance(value, dict):
            return unescape(value.get("rendered", ""))
        return unescape(str(value or ""))

    def slug_for_page(self, wp_slug: str, title: str, source_url: str) -> str:
        parsed = urlparse(source_url or "")
        path_slug = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
        source = path_slug or wp_slug or title
        if source == "impuls-2":
            source = "impuls"
        return slugify_max(source, STATICPAGE_SLUG_MAX_LENGTH) or "impuls"

    def slug_for_local_path(self, archive_dir: Path, html_path: Path, title: str) -> str:
        relative = html_path.relative_to(archive_dir)
        path = "/".join(relative.parts[:-1])
        source = path.split("/")[-1] if path else title
        return slugify_max(source, STATICPAGE_SLUG_MAX_LENGTH) or "impuls"

    def source_url_for_path(self, archive_dir: Path, html_path: Path) -> str:
        relative = html_path.relative_to(archive_dir)
        path = "/".join(relative.parts[:-1])
        return f"http://{IMPULS_HOST}/{path}" if path else f"http://{IMPULS_HOST}/"

    def parse_datetime(self, value: str | None) -> datetime:
        if not value:
            return timezone.now()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    def modified_time(self, path: Path) -> datetime:
        return timezone.make_aware(datetime.fromtimestamp(path.stat().st_mtime))

    def is_challenge_page(self, html: str) -> bool:
        return "Please wait while your request is being verified" in html

    def public_media_storage(self):
        if getattr(settings, "USE_S3", False):
            return storages["public_media"]
        return default_storage

    def get_or_create_author(self, username: str) -> Member:
        member = Member.objects.filter(username=username).first()
        if member:
            return member
        membership_type = MembershipType.objects.filter(pk=FRESHMAN).first() or MembershipType.objects.first()
        if membership_type is None:
            membership_type = MembershipType.objects.create(
                name="Imported",
                description="Created by the Impuls WordPress importer.",
                permission_profile=FRESHMAN,
            )
        return Member.objects.create(
            username=username[:20],
            first_name="WordPress",
            last_name="Import",
            membership_type=membership_type,
            is_active=False,
        )

    def print_summary(self, stats: ImportStats, dry_run: bool):
        prefix = "Dry-run summary" if dry_run else "Import summary"
        self.stdout.write(self.style.SUCCESS(prefix))
        self.stdout.write(
            f"  media saved/existing/missing: {stats.media_saved}/{stats.media_existing}/{stats.media_missing}"
        )
        self.stdout.write(f"  pages created/updated: {stats.pages_created}/{stats.pages_updated}")
        self.stdout.write(f"  posts created/updated: {stats.posts_created}/{stats.posts_updated}")
        self.stdout.write(f"  nav categories/urls created: {stats.nav_categories_created}/{stats.nav_urls_created}")
        if stats.skipped:
            self.stdout.write(f"  skipped: {dict(stats.skipped)}")


class HtmlTitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_title = False
        self.parts: list[str] = []

    @classmethod
    def parse(cls, html: str) -> str:
        parser = cls()
        parser.feed(html)
        return unescape("".join(parser.parts)).strip()

    def handle_starttag(self, tag, attrs):
        self.in_title = tag == "title"

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)


class EntryContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.capture_depth = 0
        self.parts: list[str] = []

    @classmethod
    def parse(cls, html: str) -> str:
        parser = cls()
        parser.feed(html)
        return "".join(parser.parts).strip()

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set(attrs_dict.get("class", "").split())
        if self.capture_depth:
            self.parts.append(self.get_starttag_text() or "")
            self.capture_depth += 1
        elif tag == "div" and "entry-content" in classes:
            self.capture_depth = 1
        self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.capture_depth:
            self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag):
        if self.capture_depth:
            self.capture_depth -= 1
            if self.capture_depth:
                self.parts.append(f"</{tag}>")
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.capture_depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.capture_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.capture_depth:
            self.parts.append(f"&#{name};")


class BlogIndexParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_article = False
        self.article_depth = 0
        self.article_parts: list[str] = []
        self.current_attrs: dict[str, str] = {}
        self.posts: list[PostCandidate] = []

    @classmethod
    def parse(cls, html: str) -> list[PostCandidate]:
        parser = cls()
        parser.feed(html)
        return parser.posts

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = set(attrs_dict.get("class", "").split())
        if tag == "article" and "post" in classes:
            self.in_article = True
            self.article_depth = 1
            self.article_parts = [self.get_starttag_text() or ""]
            return
        if self.in_article:
            self.article_depth += 1
            self.article_parts.append(self.get_starttag_text() or "")

    def handle_startendtag(self, tag, attrs):
        if self.in_article:
            self.article_parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag):
        if not self.in_article:
            return
        self.article_depth -= 1
        self.article_parts.append(f"</{tag}>")
        if self.article_depth <= 0:
            self.add_article("".join(self.article_parts))
            self.in_article = False

    def handle_data(self, data):
        if self.in_article:
            self.article_parts.append(data)

    def handle_entityref(self, name):
        if self.in_article:
            self.article_parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.in_article:
            self.article_parts.append(f"&#{name};")

    def add_article(self, html: str):
        title = unescape(
            strip_tags(self.first_match(r'<h2[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h2>', html))
        ).strip()
        title = re.sub(r"\s+", " ", title)
        if not title:
            return
        content = self.first_match(r'<div[^>]*class="[^"]*entry-post[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL).strip()
        category_html = self.first_match(r'<a[^>]*class="[^"]*post-cat[^"]*"[^>]*>(.*?)</a>', html)
        category_name = unescape(strip_tags(category_html)).strip()
        category_href = self.first_match(r'<a[^>]*class="[^"]*post-cat[^"]*"[^>]*href="([^"]+)"', html)
        category_slug = (
            urlparse(category_href).path.strip("/").split("/")[-1] if category_href else slugify(category_name)
        )
        source_url = self.first_match(r'<h2[^>]*class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]*href="([^"]+)"', html)
        published = self.first_match(r'<time[^>]*class="[^"]*published[^"]*"[^>]*datetime="([^"]+)"', html)
        posts_id_slug = self.first_match(r'<article[^>]*id="post-([^"]+)"', html)
        slug_source = title if not posts_id_slug else f"{title}-{posts_id_slug}"
        self.posts.append(
            PostCandidate(
                title=title,
                slug=slugify_max(slug_source, Post._meta.get_field("slug").max_length),  # type: ignore[arg-type]
                content=content,
                published_time=self.parse_datetime(published),
                category_name=category_name,
                category_slug=category_slug,
                source_url=source_url,
            )
        )

    def first_match(self, pattern: str, html: str, flags=0) -> str:
        match = re.search(pattern, html, flags | re.IGNORECASE)
        return unescape(match.group(1)) if match else ""

    def parse_datetime(self, value: str) -> datetime:
        if not value:
            return timezone.now()
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.in_menu = False
        self.completed_menu = False
        self.ul_depth = 0
        self.capture_anchor = False
        self.current_href = ""
        self.current_text: list[str] = []
        self.items: list[NavCandidate] = []

    @classmethod
    def parse(cls, html: str) -> list[NavCandidate]:
        parser = cls()
        parser.feed(html)
        return parser.items

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "ul" and attrs_dict.get("id") == "primary-menu" and not self.completed_menu:
            self.in_menu = True
            self.ul_depth = 1
            return
        if not self.in_menu:
            return
        if tag == "ul":
            self.ul_depth += 1
        elif tag == "a":
            self.capture_anchor = True
            self.current_href = attrs_dict.get("href", "")
            self.current_text = []

    def handle_endtag(self, tag):
        if not self.in_menu:
            return
        if tag == "a" and self.capture_anchor:
            title = unescape("".join(self.current_text)).strip()
            title = re.sub(r"\s+", " ", title)
            if title:
                self.items.append(NavCandidate(title=title, href=self.current_href, level=self.ul_depth))
            self.capture_anchor = False
        elif tag == "ul":
            self.ul_depth -= 1
            if self.ul_depth <= 0:
                self.in_menu = False
                self.completed_menu = True

    def handle_data(self, data):
        if self.capture_anchor:
            self.current_text.append(data)

    def handle_entityref(self, name):
        if self.capture_anchor:
            self.current_text.append(f"&{name};")

    def handle_charref(self, name):
        if self.capture_anchor:
            self.current_text.append(f"&#{name};")
