from django.db import migrations, models
from django.utils.text import slugify


POST_SLUG_MAX_LENGTH = 50


def slug_with_suffix(base_slug, suffix):
    suffix_text = "-" + str(suffix)
    base_max_length = POST_SLUG_MAX_LENGTH - len(suffix_text)
    return base_slug[:base_max_length].rstrip("-") + suffix_text


def unique_slug_for_event(event, used_slugs):
    base_slug = slugify(event.title or "")[:POST_SLUG_MAX_LENGTH].strip("-")
    if not base_slug:
        base_slug = f"event-{event.pk}"

    slug = base_slug
    suffix = 1
    while slug in used_slugs:
        slug = slug_with_suffix(base_slug, suffix)
        suffix += 1
    used_slugs.add(slug)
    return slug


def backfill_blank_event_slugs(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    used_slugs = set(
        Event.objects.exclude(
            models.Q(slug__isnull=True) | models.Q(slug="")
        ).values_list("slug", flat=True)
    )

    blank_slug_events = Event.objects.filter(
        models.Q(slug__isnull=True) | models.Q(slug="")
    ).order_by("pk")

    for event in blank_slug_events:
        event.slug = unique_slug_for_event(event, used_slugs)
        event.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0019_alter_eventattendees_options_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_blank_event_slugs,
            migrations.RunPython.noop,
        ),
    ]
