import random

from django.utils import timezone
from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw

from archive.models import Collection, Picture

SEED_PREFIX = "[Seed] "

ALBUM_NAMES = [
    "Mottagningen", "Sittning", "Gasque", "Nollning",
    "Tentafest", "Pubrunda", "Sommarfest", "Vinterfest",
    "Kickoff", "Avslutning", "Jubileum", "Afterwork",
    "Pluggkväll", "Filmkväll", "Grillkväll", "Skidresa",
]


def _make_fake_image(index):
    """Generate a visually distinct fake JPEG (gradient + random shapes)."""
    width = 800
    height = random.randint(500, 1100)

    r1 = random.randint(30, 220)
    g1 = random.randint(30, 220)
    b1 = random.randint(30, 220)
    r2 = random.randint(30, 220)
    g2 = random.randint(30, 220)
    b2 = random.randint(30, 220)

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        t = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(
                int(r1 + (r2 - r1) * t),
                int(g1 + (g2 - g1) * t),
                int(b1 + (b2 - b1) * t),
            ),
        )

    for _ in range(random.randint(4, 10)):
        x0 = random.randint(0, width - 80)
        y0 = random.randint(0, height - 80)
        x1 = min(x0 + random.randint(40, 220), width - 1)
        y1 = min(y0 + random.randint(40, 220), height - 1)
        shape_color = (
            random.randint(80, 255),
            random.randint(80, 255),
            random.randint(80, 255),
        )
        if random.random() > 0.5:
            draw.ellipse([x0, y0, x1, y1], fill=shape_color)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=shape_color)

    output = BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)

    return InMemoryUploadedFile(
        output,
        "ImageField",
        f"seed_{index:04d}.jpg",
        "image/jpeg",
        output.getbuffer().nbytes,
        None,
    )


class Command(BaseCommand):
    help = "Seed the gallery with fake albums and generated images for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--albums",
            type=int,
            default=6,
            help="Number of albums to create (default: 6)",
        )
        parser.add_argument(
            "--images",
            type=int,
            default=100,
            help="Images per album (default: 100)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all previously seeded data before seeding",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        if not getattr(settings, 'DEVELOP', False):
            raise CommandError("seed_gallery must not be run outside of a development environment (DEVELOP must be True).")
        if getattr(settings, 'USE_S3', False):
            raise CommandError("seed_gallery must not be run with USE_S3=True — it would upload fake images to S3.")

        if options["clear"]:
            collections = list(Collection.objects.filter(title__startswith=SEED_PREFIX))
            count = len(collections)
            for collection in collections:
                for picture in collection.picture_set.all():
                    picture.delete()
                collection.delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} seeded album(s)."))

        album_count = options["albums"]
        image_count = options["images"]

        pool = ALBUM_NAMES * (album_count // len(ALBUM_NAMES) + 1)
        names = random.sample(pool, album_count)

        self.stdout.write(
            f"Seeding {album_count} album(s) × {image_count} image(s) each…"
        )

        for i, name in enumerate(names):
            year = random.randint(2021, 2025)
            pub_date = timezone.datetime(
                year,
                random.randint(1, 12),
                random.randint(1, 28),
                tzinfo=timezone.get_current_timezone(),
            )

            collection = Collection.objects.create(
                title=f"{SEED_PREFIX}{name} {year}",
                type="Pictures",
                pub_date=pub_date,
            )

            self.stdout.write(f'  [{i + 1}/{album_count}] "{collection.title}"', ending=" ")

            for j in range(image_count):
                fake_img = _make_fake_image(i * image_count + j)
                Picture(collection=collection, image=fake_img).save()
                self.stdout.write(".", ending="")
                self.stdout.flush()

            self.stdout.write(self.style.SUCCESS(" done"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {album_count} album(s) created."
                f" Run with --clear to remove them."
            )
        )
