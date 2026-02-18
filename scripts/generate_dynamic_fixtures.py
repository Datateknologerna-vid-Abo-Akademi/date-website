import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

TEST_IMAGE_URL = "https://picsum.photos/800/600.jpg"
TEST_PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"


def dt(days=0, hours=0, minutes=0):
    """Return an ISO format datetime string with offset from now in UTC."""
    return (
        datetime.now(timezone.utc) + timedelta(days=days, hours=hours, minutes=minutes)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def d(days=0):
    """Return a date string with offset from now in UTC."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def download_file(url, path):
    """Download a file from URL to the specified path."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            with open(path, "wb") as f:
                f.write(response.read())
        print(f"Downloaded: {url} -> {path}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def generate():
    # Ensure media directories exist for test files
    os.makedirs("media/archive/test", exist_ok=True)
    os.makedirs("media/pdfs/test", exist_ok=True)

    # Download test files if they don't exist
    if not os.path.exists("media/archive/test/dummy.jpg"):
        download_file(TEST_IMAGE_URL, "media/archive/test/dummy.jpg")
    if not os.path.exists("media/pdfs/test/dummy.pdf"):
        download_file(TEST_PDF_URL, "media/pdfs/test/dummy.pdf")

    data = []

    # --- STATIC PAGES ---
    data.append(
        {
            "model": "staticpages.staticpagenav",
            "pk": 1,
            "fields": {"category_name": "Föreningen", "nav_element": 10},
        }
    )
    data.append(
        {
            "model": "staticpages.staticpagenav",
            "pk": 2,
            "fields": {"category_name": "Medlemmar", "nav_element": 20},
        }
    )
    data.append(
        {
            "model": "staticpages.staticpagenav",
            "pk": 3,
            "fields": {"category_name": "Evenemang", "nav_element": 30},
        }
    )
    data.append(
        {
            "model": "staticpages.staticpagenav",
            "pk": 4,
            "fields": {"category_name": "Arkiv", "nav_element": 40},
        }
    )
    data.append(
        {
            "model": "staticpages.staticpagenav",
            "pk": 5,
            "fields": {"category_name": "Externa", "nav_element": 50},
        }
    )

    data.append(
        {
            "model": "staticpages.staticpage",
            "pk": 1,
            "fields": {
                "title": "Om oss",
                "slug": "om-oss",
                "members_only": False,
                "created_time": dt(days=-10),
                "content": "<h1>Om Datateknologerna vid Åbo Akademi rf</h1><p>DaTe är en studentförening för de som studerar datateknik eller datavetenskap vid Åbo Akademi.</p><p><img src='https://via.placeholder.com/800x400' alt='Gängbild' style='width: 100%; height: auto;'/></p>",
            },
        }
    )
    data.append(
        {
            "model": "staticpages.staticpage",
            "pk": 2,
            "fields": {
                "title": "Styrelsen",
                "slug": "styrelsen",
                "members_only": False,
                "created_time": dt(days=-10),
                "content": "<h2>Styrelsen 2026</h2><p>Här hittar du årets styrelsemedlemmar och deras ansvarsområden.</p><ul><li><strong>Ordförande:</strong> Admin User</li><li><strong>Sekreterare:</strong> Molly Member</li></ul>",
            },
        }
    )

    # Static URLs
    urls = [
        ("Nyheter", "/news/", 1, 10, False),
        ("Om oss", "/pages/om-oss/", 1, 20, False),
        ("Styrelsen", "/pages/styrelsen/", 1, 30, False),
        ("Logga in", "/members/login/", 2, 10, False),
        ("Min profil", "/members/info/", 2, 20, True),
        ("Bli medlem", "/members/signup/", 2, 30, False),
        ("Trakasserianmälan", "/social/harassment/", 2, 40, False),
        ("Kommande evenemang", "/events/", 3, 10, False),
        ("Omröstningar", "/polls/", 3, 20, False),
        ("CTF", "/ctf/", 3, 30, True),
        ("Bilder", "/archive/pictures/", 4, 10, True),
        ("Dokument", "/archive/documents/", 4, 20, True),
        ("Tentarkiv", "/archive/exams/", 4, 30, True),
        ("DaTe GitHub", "https://github.com/datateknologerna", 5, 10, False),
        ("Publikationer", "/publications/", 5, 20, False),
        ("Alumniregistrering", "/alumni/signup/", 5, 30, False),
    ]
    for i, (title, url, cat, drop, login) in enumerate(urls, 1):
        data.append(
            {
                "model": "staticpages.staticurl",
                "pk": i,
                "fields": {
                    "title": title,
                    "url": url,
                    "category": cat,
                    "dropdown_element": drop,
                    "logged_in_only": login,
                },
            }
        )

    # --- NEWS ---
    news_posts = [
        (
            "Välkomna till vår nya hemsida!",
            "<p>Vi har äntligen lanserat vår nya hemsida. Hoppas ni gillar den!</p>",
            "ny-hemsida",
            -30,
        ),
        (
            "Kommande evenemang i februari",
            "<p>Håll utkik efter roliga saker som händer i februari!</p>",
            "februari-evenemang",
            -10,
        ),
        (
            "Styrelsens hälsning",
            "<p>Styrelsen ser fram emot ett spännande år!</p>",
            "styrelsens-halsning",
            -5,
        ),
        (
            "Lunchguide för teknologer",
            "<p>Här är de bästa lunchställena nära Aurum just nu...</p>",
            "lunchguide",
            -1,
        ),
    ]
    for i, (title, content, slug, days) in enumerate(news_posts, 1):
        data.append(
            {
                "model": "news.post",
                "pk": i,
                "fields": {
                    "title": title,
                    "content": content,
                    "slug": slug,
                    "author": 1,
                    "published": True,
                    "created_time": dt(days=days),
                    "published_time": dt(days=days),
                },
            }
        )

    # --- EVENTS ---
    # Past Event
    data.append(
        {
            "model": "events.event",
            "pk": 1,
            "fields": {
                "title": "Årsfest 2025",
                "content": "<p>En fantastisk fest!</p>",
                "slug": "arsfest-2025",
                "event_date_start": dt(days=-60, hours=18),
                "event_date_end": dt(days=-59, hours=4),
                "sign_up": False,
                "author": 1,
                "published": True,
            },
        }
    )
    # Active/Upcoming Event
    data.append(
        {
            "model": "events.event",
            "pk": 2,
            "fields": {
                "title": "Alla hjärtans dags-sitsit",
                "content": "<p>Välkommen på sitsit!</p>",
                "slug": "valentines-sitsit",
                "event_date_start": dt(days=7, hours=19),
                "event_date_end": dt(days=7, hours=23, minutes=59),
                "sign_up": True,
                "sign_up_max_participants": 80,
                "author": 1,
                "published": True,
                "sign_up_members": dt(days=-10),
                "sign_up_others": dt(days=-8),
                "sign_up_deadline": dt(days=3),
            },
        }
    )
    # Registration forms for event 2
    data.append(
        {
            "model": "events.eventregistrationform",
            "pk": 1,
            "fields": {
                "event": 2,
                "name": "Specialdieter",
                "type": "text",
                "required": False,
            },
        }
    )
    data.append(
        {
            "model": "events.eventregistrationform",
            "pk": 2,
            "fields": {
                "event": 2,
                "name": "Dryckesval",
                "type": "select",
                "choice_list": "Alkohol,Alkoholfritt",
                "required": True,
            },
        }
    )

    # --- POLLS ---
    data.append(
        {
            "model": "polls.question",
            "pk": 1,
            "fields": {
                "question_text": "Vad vill du ha för program?",
                "pub_date": dt(days=-5),
                "published": True,
                "show_results": True,
            },
        }
    )
    data.append(
        {
            "model": "polls.choice",
            "pk": 1,
            "fields": {"question": 1, "choice_text": "Brädspel", "votes": 12},
        }
    )
    data.append(
        {
            "model": "polls.choice",
            "pk": 2,
            "fields": {"question": 1, "choice_text": "Filmkväll", "votes": 5},
        }
    )

    # --- CTF ---
    data.append(
        {
            "model": "ctf.ctf",
            "pk": 1,
            "fields": {
                "title": "DaTe CTF 2026",
                "content": "<h1>CTF!</h1>",
                "slug": "date-ctf-2026",
                "published": True,
                "start_date": dt(days=-30),
                "end_date": dt(days=30),
                "pub_date": dt(days=-30),
            },
        }
    )
    data.append(
        {
            "model": "ctf.flag",
            "pk": 1,
            "fields": {
                "ctf": 1,
                "title": "Utmaning 1",
                "flag": "date{test}",
                "slug": "challenge-1",
                "clues": "Kolla källkoden",
            },
        }
    )

    # --- ARCHIVE ---
    data.append(
        {
            "model": "archive.collection",
            "pk": 1,
            "fields": {
                "title": "Årsfest 2025",
                "type": "Pictures",
                "pub_date": dt(days=-60),
                "hide_for_gulis": False,
            },
        }
    )
    data.append(
        {
            "model": "archive.collection",
            "pk": 2,
            "fields": {
                "title": "Mötesprotokoll 2026",
                "type": "Documents",
                "pub_date": dt(days=-30),
                "hide_for_gulis": False,
            },
        }
    )

    # Pictures using local paths
    for i in range(1, 4):
        data.append(
            {
                "model": "archive.picture",
                "pk": i,
                "fields": {
                    "collection": 1,
                    "image": "archive/test/dummy.jpg",
                    "favorite": (i == 1),
                },
            }
        )

    # --- PUBLICATIONS ---
    data.append(
        {
            "model": "publications.pdffile",
            "pk": 1,
            "fields": {
                "title": "Stadgar",
                "slug": "stadgar",
                "is_public": True,
                "requires_login": False,
                "file": "pdfs/test/dummy.pdf",
                "uploaded_at": dt(days=-100),
                "updated_at": dt(days=-100),
                "publication_date": d(-100),
            },
        }
    )

    # --- SOCIAL ---
    data.append(
        {
            "model": "social.harassmentemailrecipient",
            "pk": 1,
            "fields": {"recipient_email": "test-admin@example.com"},
        }
    )
    data.append(
        {
            "model": "alumni.alumniemailrecipient",
            "pk": 1,
            "fields": {"recipient_email": "alumni-test@example.com"},
        }
    )

    # --- BILLING ---
    data.append(
        {
            "model": "billing.eventbillingconfiguration",
            "pk": 1,
            "fields": {
                "event": 2,
                "due_date": d(days=14),
                "integration_type": 0,
                "price": "10.00",
                "price_selector": "",
            },
        }
    )

    with open("fixtures/dynamic.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Successfully generated fixtures/dynamic.json with dynamic dates.")


if __name__ == "__main__":
    generate()
