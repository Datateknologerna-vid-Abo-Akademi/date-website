from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = 'events'

    def ready(self):
        # Lets Pillow read iPhone HEIC/HEIF background pictures, which are then stored
        # as JPEG. gallery registers it too, but not every association installs gallery.
        import pillow_heif

        pillow_heif.register_heif_opener()
