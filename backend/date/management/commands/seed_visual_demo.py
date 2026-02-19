from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.utils import timezone

from members.models import (
    FRESHMAN,
    ORDINARY_MEMBER,
    SENIOR_MEMBER,
    SUPPORTING_MEMBER,
    Functionary,
    FunctionaryRole,
    Member,
    MembershipType,
)


class Command(BaseCommand):
    help = (
        "Seed dynamic demo data for manual visual and feature checks. "
        "Only seeds models from enabled apps."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Flush database before seeding data.",
        )
        parser.add_argument(
            "--base-date",
            type=str,
            default=None,
            help="Date anchor in YYYY-MM-DD. Defaults to today in project timezone.",
        )
        parser.add_argument("--admin-username", type=str, default=None)
        parser.add_argument("--admin-password", type=str, default=None)
        parser.add_argument("--member-password", type=str, default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        if options["reset"]:
            self.stdout.write("Flushing database before demo seed...")
            call_command("flush", interactive=False, verbosity=options.get("verbosity", 1))

        anchor = self._resolve_anchor(options.get("base_date"))
        admin_username = options.get("admin_username") or os.environ.get(
            "DATE_DEMO_ADMIN_USERNAME",
            "admin",
        )
        admin_password = options.get("admin_password") or os.environ.get(
            "DATE_DEMO_ADMIN_PASSWORD",
            "admin",
        )
        member_password = options.get("member_password") or os.environ.get(
            "DATE_DEMO_MEMBER_PASSWORD",
            "member",
        )

        enabled = self._enabled_modules()
        memberships = self._seed_membership_types()
        users = self._seed_members(memberships, admin_username, admin_password, member_password)
        self._seed_functionaries(users, anchor)

        if enabled["staticpages"]:
            self._seed_staticpages(enabled, anchor)
        if enabled["news"]:
            self._seed_news(anchor, users["admin"])
        if enabled["events"]:
            self._seed_events(anchor, users)
        if enabled["ads"]:
            self._seed_ads()
        if enabled["social"]:
            self._seed_social()
        if enabled["polls"]:
            self._seed_polls(users)
        if enabled["ctf"]:
            self._seed_ctf(anchor, users)
        if enabled["lucia"]:
            self._seed_lucia()
        if enabled["alumni"]:
            self._seed_alumni()
        if enabled["archive"]:
            self._seed_archive(anchor)
        if enabled["publications"]:
            self._seed_publications(anchor)

        seeded_apps = ", ".join(sorted([name for name, is_enabled in enabled.items() if is_enabled]))
        self.stdout.write(self.style.SUCCESS("Demo seed completed successfully."))
        self.stdout.write(f"Enabled apps seeded: {seeded_apps}")
        self.stdout.write(f"Admin login: {admin_username} / {admin_password}")

    def _resolve_anchor(self, base_date: str | None) -> datetime:
        if not base_date:
            return timezone.now()

        try:
            parsed_date = datetime.strptime(base_date, "%Y-%m-%d").date()
        except ValueError as error:
            raise CommandError("--base-date must be in YYYY-MM-DD format.") from error

        return timezone.make_aware(
            datetime.combine(parsed_date, time(hour=12, minute=0)),
            timezone.get_current_timezone(),
        )

    def _enabled_modules(self) -> dict[str, bool]:
        module_names = [
            "staticpages",
            "news",
            "events",
            "ads",
            "social",
            "polls",
            "ctf",
            "lucia",
            "alumni",
            "archive",
            "publications",
        ]
        return {name: apps.is_installed(name) for name in module_names}

    def _seed_membership_types(self) -> dict[int, MembershipType]:
        specs = [
            (FRESHMAN, "Gulnabb", "Entry level member profile", FRESHMAN),
            (ORDINARY_MEMBER, "Ordinarie medlem", "Default active member profile", ORDINARY_MEMBER),
            (SUPPORTING_MEMBER, "Stodjande medlem", "Supporting member profile", SUPPORTING_MEMBER),
            (SENIOR_MEMBER, "Seniormedlem", "Senior member profile", SENIOR_MEMBER),
        ]
        types_by_id: dict[int, MembershipType] = {}
        for pk, name, description, permission_profile in specs:
            membership_type, _ = MembershipType.objects.update_or_create(
                pk=pk,
                defaults={
                    "name": name,
                    "description": description,
                    "permission_profile": permission_profile,
                },
            )
            types_by_id[pk] = membership_type
        return types_by_id

    def _seed_members(
        self,
        memberships: dict[int, MembershipType],
        admin_username: str,
        admin_password: str,
        member_password: str,
    ) -> dict[str, Member]:
        ordinary_membership = memberships[ORDINARY_MEMBER]
        freshman_membership = memberships[FRESHMAN]
        supporting_membership = memberships[SUPPORTING_MEMBER]

        admin, _ = Member.objects.update_or_create(
            username=admin_username,
            defaults={
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "User",
                "membership_type": ordinary_membership,
                "is_active": True,
            },
        )
        admin.is_superuser = True
        admin.membership_type = ordinary_membership
        admin.set_password(admin_password)
        admin.save()

        member, _ = Member.objects.update_or_create(
            username="member",
            defaults={
                "email": "member@example.com",
                "first_name": "Molly",
                "last_name": "Member",
                "membership_type": ordinary_membership,
                "is_active": True,
                "year_of_admission": timezone.now().year - 2,
            },
        )
        member.is_superuser = False
        member.membership_type = ordinary_membership
        member.set_password(member_password)
        member.save()

        freshman, _ = Member.objects.update_or_create(
            username="freshman",
            defaults={
                "email": "freshman@example.com",
                "first_name": "Freddy",
                "last_name": "Freshman",
                "membership_type": freshman_membership,
                "is_active": True,
                "year_of_admission": timezone.now().year,
            },
        )
        freshman.is_superuser = False
        freshman.membership_type = freshman_membership
        freshman.set_password(member_password)
        freshman.save()

        supporter, _ = Member.objects.update_or_create(
            username="supporter",
            defaults={
                "email": "supporter@example.com",
                "first_name": "Sasha",
                "last_name": "Supporter",
                "membership_type": supporting_membership,
                "is_active": True,
                "year_of_admission": timezone.now().year - 4,
            },
        )
        supporter.is_superuser = False
        supporter.membership_type = supporting_membership
        supporter.set_password(member_password)
        supporter.save()

        return {
            "admin": admin,
            "member": member,
            "freshman": freshman,
            "supporter": supporter,
        }

    def _seed_functionaries(self, users: dict[str, Member], anchor: datetime) -> None:
        chair, _ = self._upsert_by_lookup(
            FunctionaryRole,
            {"title": "Ordforande"},
            {"board": True},
        )
        secretary, _ = self._upsert_by_lookup(
            FunctionaryRole,
            {"title": "Sekreterare"},
            {"board": True},
        )
        host, _ = self._upsert_by_lookup(
            FunctionaryRole,
            {"title": "Evenemangsansvarig"},
            {"board": False},
        )

        current_year = anchor.year
        self._upsert_by_lookup(
            Functionary,
            {"member": users["member"], "functionary_role": chair, "year": current_year},
        )
        self._upsert_by_lookup(
            Functionary,
            {"member": users["freshman"], "functionary_role": secretary, "year": current_year},
        )
        self._upsert_by_lookup(
            Functionary,
            {"member": users["supporter"], "functionary_role": host, "year": current_year},
        )

    def _seed_staticpages(self, enabled: dict[str, bool], anchor: datetime) -> None:
        StaticPageNav = apps.get_model("staticpages", "StaticPageNav")
        StaticPage = apps.get_model("staticpages", "StaticPage")
        StaticUrl = apps.get_model("staticpages", "StaticUrl")

        page_specs = [
            {
                "slug": "om-oss",
                "title": "Om oss",
                "members_only": False,
                "content": (
                    "<p>Detta ar demosida med data for att validera layout, typografi och"
                    " innehall i den nya frontend implementationen.</p>"
                ),
            },
            {
                "slug": "styrelsen",
                "title": "Styrelsen",
                "members_only": False,
                "content": "<p>Kontakta styrelsen via e-post eller sociala kanaler.</p>",
            },
            {
                "slug": "foretagssamarbete",
                "title": "Foretagssamarbete",
                "members_only": False,
                "content": "<p>Vi valkomnar samarbeten kring evenemang och rekrytering.</p>",
            },
            {
                "slug": "intern-info",
                "title": "Intern info",
                "members_only": True,
                "content": "<p>Denna sida syns endast for inloggade medlemmar.</p>",
            },
        ]

        for page in page_specs:
            StaticPage.objects.update_or_create(
                slug=page["slug"],
                defaults={
                    "title": page["title"],
                    "content": page["content"],
                    "members_only": page["members_only"],
                    "created_time": anchor,
                },
            )

        nav_specs = [
            ("Foreningen", 10),
            ("Medlemmar", 20),
            ("Verksamhet", 30),
        ]
        if enabled["social"]:
            nav_specs.append(("Socialt", 40))

        nav_by_name = {}
        for category_name, nav_element in nav_specs:
            category, _ = self._upsert_by_lookup(
                StaticPageNav,
                {"category_name": category_name},
                {
                    "nav_element": nav_element,
                    "use_category_url": False,
                    "url": "",
                },
            )
            nav_by_name[category_name] = category

        url_specs: dict[str, list[tuple[str, str, bool]]] = {
            "Foreningen": [
                ("Om oss", "/pages/om-oss/", False),
                ("Styrelsen", "/pages/styrelsen/", False),
                ("Foretagssamarbete", "/pages/foretagssamarbete/", False),
            ],
            "Medlemmar": [
                ("Logga in", "/members/login/", False),
                ("Min profil", "/members/profile/", True),
                ("Funktionarer", "/members/functionaries/", False),
                ("Intern info", "/pages/intern-info/", True),
            ],
            "Verksamhet": [],
        }

        if enabled["news"]:
            url_specs["Verksamhet"].append(("Nyheter", "/news/", False))
        if enabled["events"]:
            url_specs["Verksamhet"].append(("Evenemang", "/events/", False))
        if enabled["polls"]:
            url_specs["Verksamhet"].append(("Polls", "/polls/", False))
        if enabled["archive"]:
            url_specs["Verksamhet"].append(("Arkiv", "/archive/", False))
        if enabled["ads"]:
            url_specs["Verksamhet"].append(("Partners", "/ads/", False))
        if enabled["publications"]:
            url_specs["Verksamhet"].append(("Publikationer", "/publications/", False))
        if enabled["ctf"]:
            url_specs["Verksamhet"].append(("CTF", "/ctf/", False))
        if enabled["lucia"]:
            url_specs["Verksamhet"].append(("Lucia", "/lucia/candidates/", False))
        if enabled["alumni"]:
            url_specs["Verksamhet"].append(("Alumni", "/alumni/signup/", False))

        if enabled["social"]:
            url_specs["Socialt"] = [
                ("Social", "/social/", False),
                ("Trakasseriombud", "/social/harassment/", False),
            ]

        for category_name, items in url_specs.items():
            category = nav_by_name.get(category_name)
            if not category:
                continue
            for index, (title, url, logged_in_only) in enumerate(items, start=1):
                self._upsert_by_lookup(
                    StaticUrl,
                    {"category": category, "title": title},
                    {
                        "url": url,
                        "logged_in_only": logged_in_only,
                        "dropdown_element": index * 10,
                    },
                )

    def _seed_news(self, anchor: datetime, author: Member) -> None:
        Category = apps.get_model("news", "Category")
        Post = apps.get_model("news", "Post")

        aa_category, _ = Category.objects.update_or_create(
            slug="albins-angels",
            defaults={"name": "Albins Angels"},
        )
        updates_category, _ = Category.objects.update_or_create(
            slug="funktionarsnytt",
            defaults={"name": "Funktionarsnytt"},
        )

        posts = [
            {
                "slug": "demo-startvecka-info",
                "title": "Startveckan ar igang",
                "content": (
                    "<p>Valkommen till en vecka fylld med aktiviteter, introduktion och"
                    " gemenskap. Vi ses pa campus under flera tillfallen.</p>"
                ),
                "published_time": anchor - timedelta(days=1),
                "category": None,
            },
            {
                "slug": "demo-foreningsmote",
                "title": "Inbjudan till foreningsmote",
                "content": (
                    "<p>Vi samlas for foreningsmote med fokus pa verksamhetsplan,"
                    " budget och kommande satsningar.</p>"
                ),
                "published_time": anchor - timedelta(days=3),
                "category": None,
            },
            {
                "slug": "demo-foretagspub",
                "title": "Foretagspub och mingel",
                "content": (
                    "<p>Traffa samarbetspartners och lar kanna studenter fran olika"
                    " arskurser under en avslappnad kvall.</p>"
                ),
                "published_time": anchor - timedelta(days=6),
                "category": None,
            },
            {
                "slug": "demo-aa-uppdatering",
                "title": "Albins Angels: veckans uppdatering",
                "content": "<p>Ny uppdatering med tips och pepp fran Albins Angels.</p>",
                "published_time": anchor - timedelta(days=2),
                "category": aa_category,
            },
            {
                "slug": "demo-funktionarsnytt",
                "title": "Funktionarsnytt for aktiva",
                "content": "<p>Info om funktionarsarbete, planering och ansvar.</p>",
                "published_time": anchor - timedelta(days=4),
                "category": updates_category,
            },
        ]

        for post in posts:
            Post.objects.update_or_create(
                slug=post["slug"],
                defaults={
                    "title": post["title"],
                    "content": post["content"],
                    "author": author,
                    "published": True,
                    "created_time": post["published_time"],
                    "published_time": post["published_time"],
                    "category": post["category"],
                },
            )

    def _seed_events(self, anchor: datetime, users: dict[str, Member]) -> None:
        Event = apps.get_model("events", "Event")
        EventAttendees = apps.get_model("events", "EventAttendees")
        EventRegistrationForm = apps.get_model("events", "EventRegistrationForm")

        def at(day_offset: int, hour: int, minute: int = 0) -> datetime:
            return (anchor + timedelta(days=day_offset)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        event_specs = [
            {
                "slug": "demo-ongoing-lunch",
                "title": "Lunchhang pa kansliet",
                "start": anchor - timedelta(hours=2),
                "end": anchor + timedelta(hours=2),
                "sign_up": False,
                "members_only": False,
                "passcode": "",
                "sign_up_max_participants": 0,
            },
            {
                "slug": "demo-kanslikaffe",
                "title": "Kanslikaffe",
                "start": at(1, 10, 0),
                "end": at(1, 12, 0),
                "sign_up": True,
                "members_only": False,
                "passcode": "",
                "sign_up_max_participants": 0,
            },
            {
                "slug": "demo-sits",
                "title": "Temasits med avec",
                "start": at(4, 19, 0),
                "end": at(4, 23, 30),
                "sign_up": True,
                "members_only": False,
                "passcode": "",
                "sign_up_avec": True,
                "sign_up_max_participants": 80,
            },
            {
                "slug": "demo-full-event",
                "title": "Workshop med begransade platser",
                "start": at(6, 17, 0),
                "end": at(6, 20, 0),
                "sign_up": True,
                "members_only": False,
                "passcode": "",
                "sign_up_max_participants": 2,
            },
            {
                "slug": "demo-members-only",
                "title": "Medlemskvall",
                "start": at(8, 18, 0),
                "end": at(8, 22, 0),
                "sign_up": True,
                "members_only": True,
                "passcode": "",
                "sign_up_max_participants": 35,
            },
            {
                "slug": "demo-passcode-event",
                "title": "Specialevent med passcode",
                "start": at(12, 18, 0),
                "end": at(12, 21, 0),
                "sign_up": False,
                "members_only": False,
                "passcode": "demo-passcode",
                "sign_up_max_participants": 0,
            },
            {
                "slug": "demo-recent-past",
                "title": "Senaste afterwork",
                "start": at(-6, 18, 0),
                "end": at(-6, 22, 0),
                "sign_up": False,
                "members_only": False,
                "passcode": "",
                "sign_up_max_participants": 0,
            },
        ]

        event_map: dict[str, Any] = {}
        for spec in event_specs:
            sign_up_opens = spec["start"] - timedelta(days=10)
            sign_up_deadline = spec["start"] - timedelta(hours=2)
            event, _ = Event.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "content": (
                        "<p>Detta ar ett demosatt evenemang for manuell validering av "
                        "kort, kalender och detaljvyer.</p>"
                    ),
                    "event_date_start": spec["start"],
                    "event_date_end": spec["end"],
                    "sign_up": spec.get("sign_up", True),
                    "sign_up_avec": spec.get("sign_up_avec", False),
                    "sign_up_max_participants": spec["sign_up_max_participants"],
                    "sign_up_members": sign_up_opens,
                    "sign_up_others": sign_up_opens,
                    "sign_up_deadline": sign_up_deadline,
                    "sign_up_cancelling": True,
                    "sign_up_cancelling_deadline": sign_up_deadline,
                    "author": users["admin"],
                    "published": True,
                    "members_only": spec["members_only"],
                    "passcode": spec["passcode"],
                    "captcha": False,
                    "redirect_link": "",
                    "parent": None,
                },
            )
            event_map[spec["slug"]] = event

        sits_event = event_map["demo-sits"]
        form_specs = [
            {
                "name": "Specialdieter",
                "type": "text",
                "required": False,
                "public_info": True,
                "choice_list": "",
                "hide_for_avec": False,
                "choice_number": 10,
            },
            {
                "name": "Dryckesval",
                "type": "select",
                "required": True,
                "public_info": True,
                "choice_list": "Alkoholfri,Vin,Ol",
                "hide_for_avec": False,
                "choice_number": 20,
            },
            {
                "name": "Sangonskemal",
                "type": "checkbox",
                "required": False,
                "public_info": False,
                "choice_list": "",
                "hide_for_avec": True,
                "choice_number": 30,
            },
        ]

        for spec in form_specs:
            EventRegistrationForm.objects.update_or_create(
                event=sits_event,
                name=spec["name"],
                defaults={
                    "type": spec["type"],
                    "required": spec["required"],
                    "public_info": spec["public_info"],
                    "choice_list": spec["choice_list"],
                    "hide_for_avec": spec["hide_for_avec"],
                    "choice_number": spec["choice_number"],
                },
            )

        full_event = event_map["demo-full-event"]
        full_attendees = [
            ("member@example.com", "Molly Member"),
            ("freshman@example.com", "Freddy Freshman"),
        ]
        for email, name in full_attendees:
            EventAttendees.objects.update_or_create(
                event=full_event,
                email=email,
                defaults={
                    "user": name,
                    "anonymous": False,
                    "time_registered": anchor - timedelta(days=1),
                    "preferences": {"Specialdieter": "", "Dryckesval": "Alkoholfri"},
                    "original_event": full_event,
                },
            )

        EventAttendees.objects.update_or_create(
            event=sits_event,
            email="supporter@example.com",
            defaults={
                "user": "Sasha Supporter",
                "anonymous": False,
                "time_registered": anchor - timedelta(hours=8),
                "preferences": {"Specialdieter": "Vegetarisk", "Dryckesval": "Vin"},
                "original_event": sits_event,
            },
        )

    def _seed_ads(self) -> None:
        AdUrl = apps.get_model("ads", "AdUrl")
        ad_specs = [
            (
                "https://albin-storage.cdn.datateknologerna.org/date/public/2021/partner-logos/aa-logo-small.png",
                "https://www.abo.fi",
            ),
            (
                "https://albin-storage.cdn.datateknologerna.org/date/public/2021/halarsponslogon/tfif-bla-logo-utan-text-digi.png",
                "https://www.turuntekniikan.fi",
            ),
            (
                "https://albin-storage.cdn.datateknologerna.org/date/public/2021/partner-logos/warkings-logo.png",
                "https://www.warkings.fi",
            ),
            (
                "https://albin-storage.cdn.datateknologerna.org/date/public/2021/partner-logos/elektroniikkakerho-logo.png",
                "https://www.abo.fi",
            ),
        ]
        for ad_url, company_url in ad_specs:
            self._upsert_by_lookup(
                AdUrl,
                {"ad_url": ad_url},
                {"company_url": company_url},
            )

    def _seed_social(self) -> None:
        IgUrl = apps.get_model("social", "IgUrl")
        HarassmentEmailRecipient = apps.get_model("social", "HarassmentEmailRecipient")

        ig_specs = [
            ("demo-ig-1", "/static/core/images/headerlogo.png"),
            ("demo-ig-2", "/static/core/images/footerlogo.png"),
            ("demo-ig-3", "/static/core/images/albins-angels.png"),
        ]
        for shortcode, url in ig_specs:
            self._upsert_by_lookup(
                IgUrl,
                {"shortcode": shortcode},
                {"url": url},
            )

        fallback_email = settings.CONTENT_VARIABLES.get("ASSOCIATION_EMAIL", "admin@example.com")
        self._upsert_by_lookup(
            HarassmentEmailRecipient,
            {"recipient_email": fallback_email},
            {"recipient_email": fallback_email},
        )

    def _seed_polls(self, users: dict[str, Member]) -> None:
        Question = apps.get_model("polls", "Question")
        Choice = apps.get_model("polls", "Choice")
        Vote = apps.get_model("polls", "Vote")

        question, _ = self._upsert_by_lookup(
            Question,
            {"question_text": "Vilket evenemang ser du mest fram emot?"},
            {
                "published": True,
                "show_results": True,
                "end_vote": False,
                "multiple_choice": False,
                "required_multiple_choices": None,
                "voting_options": 1,
            },
        )

        choice_specs = [
            ("Temasits", 12),
            ("Workshop", 9),
            ("Afterwork", 5),
        ]
        for choice_text, votes in choice_specs:
            self._upsert_by_lookup(
                Choice,
                {"question": question, "choice_text": choice_text},
                {"votes": votes},
            )

        for user_key in ("member", "freshman", "supporter"):
            user = users[user_key]
            if not Vote.objects.filter(question=question, user=user).exists():
                Vote.objects.create(question=question, user=user)

    def _seed_ctf(self, anchor: datetime, users: dict[str, Member]) -> None:
        Ctf = apps.get_model("ctf", "Ctf")
        Flag = apps.get_model("ctf", "Flag")

        ctf_event, _ = Ctf.objects.update_or_create(
            slug="demo-ctf",
            defaults={
                "title": "Demo CTF",
                "content": "<p>Los flaggor och testa CTF-flodet.</p>",
                "start_date": anchor - timedelta(days=1),
                "end_date": anchor + timedelta(days=14),
                "published": True,
            },
        )

        Flag.objects.update_or_create(
            slug="demo-ctf-flag-1",
            defaults={
                "ctf": ctf_event,
                "solver": users["member"],
                "title": "Introflagga",
                "flag": "DATE{demo-intro}",
                "solved_date": anchor - timedelta(hours=2),
                "clues": "<p>Las startsidan noggrant.</p>",
            },
        )
        Flag.objects.update_or_create(
            slug="demo-ctf-flag-2",
            defaults={
                "ctf": ctf_event,
                "solver": None,
                "title": "Kryptoflagga",
                "flag": "DATE{demo-crypto}",
                "solved_date": None,
                "clues": "<p>Titta pa logotypens metadata.</p>",
            },
        )

    def _seed_lucia(self) -> None:
        Candidate = apps.get_model("lucia", "Candidate")
        Candidate.objects.update_or_create(
            slug="demo-lucia-kandidat",
            defaults={
                "img_url": "https://albin-storage.cdn.datateknologerna.org/date/public/2021/partner-logos/aa-logo-small.png",
                "title": "Demo Kandidat",
                "content": "<p>Presentation av kandidat for visuell validering.</p>",
                "published": True,
                "poll_url": "https://example.com/lucia-vote",
            },
        )

    def _seed_alumni(self) -> None:
        AlumniEmailRecipient = apps.get_model("alumni", "AlumniEmailRecipient")
        recipient_email = settings.CONTENT_VARIABLES.get("ASSOCIATION_EMAIL", "admin@example.com")
        self._upsert_by_lookup(
            AlumniEmailRecipient,
            {"recipient_email": recipient_email},
            {"recipient_email": recipient_email},
        )

    def _seed_archive(self, anchor: datetime) -> None:
        Collection = apps.get_model("archive", "Collection")
        Document = apps.get_model("archive", "Document")

        doc_collection, _ = self._upsert_by_lookup(
            Collection,
            {"title": "Demo Dokument", "type": "Documents"},
            {"pub_date": anchor, "hide_for_gulis": False},
        )
        exam_collection, _ = self._upsert_by_lookup(
            Collection,
            {"title": "Demo Tenter", "type": "Exams"},
            {"pub_date": anchor - timedelta(days=30), "hide_for_gulis": False},
        )

        self._upsert_document(
            Document,
            doc_collection,
            "Demo Stadgar",
            "demo-stadgar.txt",
            b"Demo content for manual document checks.\n",
        )
        self._upsert_document(
            Document,
            exam_collection,
            "Demo Examen",
            "demo-exam.txt",
            b"Demo exam content for archive feature checks.\n",
        )

    def _upsert_document(
        self,
        document_model: Any,
        collection: Any,
        title: str,
        filename: str,
        content: bytes,
    ) -> None:
        document = document_model.objects.filter(collection=collection, title=title).first()
        if document is None:
            document = document_model(collection=collection, title=title)

        if not document.document:
            document.document.save(filename, ContentFile(content), save=False)
        document.collection = collection
        document.title = title
        document.save()

    def _upsert_by_lookup(
        self,
        model: Any,
        lookup: dict[str, Any],
        defaults: dict[str, Any] | None = None,
    ) -> tuple[Any, bool]:
        defaults = defaults or {}
        instance = model.objects.filter(**lookup).order_by("pk").first()
        if instance is None:
            return model.objects.create(**lookup, **defaults), True

        for field_name, value in defaults.items():
            setattr(instance, field_name, value)
        if defaults:
            instance.save()
        return instance, False

    def _seed_publications(self, anchor: datetime) -> None:
        PDFFile = apps.get_model("publications", "PDFFile")
        publication = PDFFile.objects.filter(slug="demo-stadgar-publikation").first()
        if publication is None:
            publication = PDFFile(slug="demo-stadgar-publikation")

        publication.title = "Demo Stadgar (Publikation)"
        publication.description = "Demo publication used for local feature checks."
        publication.publication_date = anchor.date()
        publication.is_public = True
        publication.requires_login = False

        if not publication.file:
            publication.file.save(
                "demo-stadgar.pdf",
                ContentFile(self._minimal_pdf_content()),
                save=False,
            )
        publication.save()

    def _minimal_pdf_content(self) -> bytes:
        return (
            b"%PDF-1.1\n"
            b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>endobj\n"
            b"4 0 obj<< /Length 44 >>stream\nBT /F1 12 Tf 40 120 Td (Demo publication) Tj ET\nendstream endobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000061 00000 n \n"
            b"0000000118 00000 n \n0000000205 00000 n \n"
            b"trailer<< /Root 1 0 R /Size 5 >>\nstartxref\n303\n%%EOF\n"
        )
