from django.core.management.base import BaseCommand

from events.models import Event


class Command(BaseCommand):
    help = (
        "Record the dominant colour of event background pictures uploaded before the "
        "colour was stored on upload. Events that already have a colour are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Report the colours without saving them.")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = failed = 0
        for event in Event.objects.filter(background_image_color='').iterator():
            # The same rules Event.save() uses: which picture the page shows, and how
            # a stored picture is read.
            field_name = event.shown_background_picture_field
            if field_name is None:
                continue
            color = event.stored_background_picture_color(field_name)
            if not color:
                failed += 1
                self.stderr.write(f"Skipped {event.slug}: picture could not be read")
                continue
            if not dry_run:
                # update() rather than save(): no modified_time bump, no upload processing.
                # Only while the row still holds this picture and no colour: an editor
                # may have replaced it while it was being read, and save() then wrote
                # the new picture's colour.
                still_missing = Event.objects.filter(
                    pk=event.pk, background_image_color='', **{field_name: getattr(event, field_name).name}
                )
                if not still_missing.update(background_image_color=color):
                    self.stderr.write(f"Skipped {event.slug}: picture changed while it was read")
                    continue
            self.stdout.write(f"{event.slug}: {color}")
            updated += 1

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {updated} event(s); {failed} picture(s) could not be read."))
